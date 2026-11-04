"""Login-free catalog and quote endpoints. Totals only ever come from the server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Addon, Area, Package, Product, Venue, Zone
from app.schemas.public import (
    AddonOut,
    AreaOut,
    AreasOut,
    BookingCreatedOut,
    BookingIn,
    PackageOut,
    PaymentInstructions,
    ProductOut,
    PublicSettingsOut,
    QuoteIn,
    QuoteOut,
    VenueOut,
    ZoneOut,
)
from app.services.bookings import BookingRejected, NewBooking, create_booking
from app.services.pricing import CatalogError, QuoteError, QuoteRequest
from app.services.quoting import compute_quote
from app.services.rate_limit import SlidingWindow
from app.services.settings_store import load_public_settings

router = APIRouter(prefix="/public", tags=["public"])

booking_limiter = SlidingWindow(limit=10, window_seconds=600)
lookup_limiter = SlidingWindow(limit=20, window_seconds=600)

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/catalog", response_model=list[ProductOut])
async def catalog(session: Session):
    stmt = (
        select(Product).where(Product.active).options(selectinload(Product.tiers)).order_by(Product.id)
    )
    return (await session.scalars(stmt)).all()


@router.get("/packages", response_model=list[PackageOut])
async def packages(session: Session):
    stmt = (
        select(Package)
        .where(Package.active)
        .options(selectinload(Package.rules))
        .order_by(Package.sort_order, Package.id)
    )
    return (await session.scalars(stmt)).all()


@router.get("/addons", response_model=list[AddonOut])
async def addons(session: Session):
    return (await session.scalars(select(Addon).where(Addon.active).order_by(Addon.id))).all()


@router.get("/areas", response_model=AreasOut)
async def areas(session: Session):
    zones = (await session.scalars(select(Zone).order_by(Zone.id))).all()
    all_areas = (await session.scalars(select(Area).order_by(Area.name))).all()
    venues = (await session.scalars(select(Venue).order_by(Venue.id))).all()
    return AreasOut(
        zones=[
            ZoneOut(
                id=zone.id,
                name=zone.name,
                delivery_fee=zone.delivery_fee,
                areas=[AreaOut.model_validate(a) for a in all_areas if a.zone_id == zone.id],
            )
            for zone in zones
        ],
        venues=[VenueOut.model_validate(v) for v in venues],
    )


def _to_request(body: QuoteIn) -> QuoteRequest:
    return QuoteRequest(
        event_date=body.event_date,
        hours=body.hours,
        guests=body.guests,
        setup_at=body.setup_at,
        collect_at=body.collect_at,
        package_id=body.package_id,
        overrides=body.overrides or {},
        items=tuple((i.product_id, i.packs) for i in body.items or ()),
        addons=tuple((a.addon_id, a.qty) for a in body.addons),
        area_id=body.area_id,
        custom_area=body.custom_area,
    )


@router.post("/quote", response_model=QuoteOut)
async def quote(body: QuoteIn, session: Session):
    try:
        result = await compute_quote(session, _to_request(body))
    except (QuoteError, CatalogError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(result)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many() -> HTTPException:
    return HTTPException(status_code=429, detail="Too many attempts, try again later")


def _payment_instructions(public: dict[str, str]) -> PaymentInstructions:
    return PaymentInstructions(
        mpesa_till=public["mpesa_till"],
        tigopesa_lipa=public["tigopesa_lipa"],
        airtel_lipa=public["airtel_lipa"],
        bank_details=public["bank_details"],
    )


@router.get("/settings", response_model=PublicSettingsOut)
async def public_settings(session: Session):
    public = await load_public_settings(session)
    return PublicSettingsOut(
        business_name=public["business_name"],
        whatsapp_number=public["whatsapp_number"],
        policy_text_sw=public["policy_text_sw"],
        policy_text_en=public["policy_text_en"],
        payment_instructions=_payment_instructions(public),
    )


@router.post("/bookings", response_model=BookingCreatedOut, status_code=201)
async def create_public_booking(body: BookingIn, request: Request, session: Session):
    ip = _client_ip(request)
    if booking_limiter.blocked(ip):
        raise _too_many()
    new = NewBooking(
        request=_to_request(body),
        expected_total=body.expected_total,
        event_type=body.event_type,
        start_time=body.start_time,
        name=body.name,
        phone=body.phone,
        email=body.email,
        notes=body.notes,
        lang=body.lang,
        venue_id=body.venue_id,
        venue_name=body.venue_name,
        venue_address=body.venue_address,
    )
    try:
        booking = await create_booking(session, new)
    except BookingRejected as exc:
        quote_out = QuoteOut.model_validate(exc.quote).model_dump(mode="json")
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "quote": quote_out}
        ) from exc
    except (QuoteError, CatalogError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    booking_limiter.hit(ip)

    public = await load_public_settings(session)
    return BookingCreatedOut(
        code=booking.code,
        status=booking.status,
        is_rush=booking.is_rush,
        provisional=booking.delivery_fee_custom,
        total=booking.total,
        deposit_due=booking.deposit_due,
        balance_due_date=booking.balance_due_date,
        payment_instructions=_payment_instructions(public),
        whatsapp_number=public["whatsapp_number"],
    )
