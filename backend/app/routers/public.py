"""Login-free catalog and quote endpoints. Totals only ever come from the server."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Addon, Area, Booking, Package, Product, Venue, Zone
from app.schemas.public import (
    AddonOut,
    AreaOut,
    AreasOut,
    BookingCreatedOut,
    BookingIn,
    PackageOut,
    PaymentIn,
    PaymentInstructions,
    PaymentOut,
    ProductOut,
    PublicSettingsOut,
    QuoteIn,
    QuoteOut,
    TrackedAddonOut,
    TrackedBookingOut,
    TrackedItemOut,
    TrackIn,
    VenueOut,
    ZoneOut,
)
from app.services.bookings import (
    BookingClosed,
    BookingRejected,
    DuplicateReference,
    NewBooking,
    NewPayment,
    create_booking,
    find_booking,
    payment_summary,
    submit_payment,
)
from app.services.notify import (
    booking_to_business,
    booking_to_customer,
    payment_to_business,
    send_email,
)
from app.services.pricing import CatalogError, QuoteError, QuoteRequest
from app.services.quoting import compute_quote
from app.services.rate_limit import SlidingWindow
from app.services.settings_store import load_notification_email, load_public_settings

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
    active = set(await session.scalars(select(Product.id).where(Product.active)))
    # A new response, not an edit to package.rules: that relationship would delete what it no longer holds.
    return [
        PackageOut.model_validate(package).model_copy(
            update={"rules": [r for r in package.rules if r.product_id in active]}
        )
        for package in await session.scalars(stmt)
    ]


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
async def create_public_booking(
    body: BookingIn, request: Request, session: Session, background: BackgroundTasks
):
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
    business = await load_notification_email(session)
    background.add_task(send_email, booking_to_business(business, booking, body.name, body.phone))
    if body.email:
        background.add_task(send_email, booking_to_customer(body.email, booking, public))
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


async def _lookup(session: AsyncSession, request: Request, code: str, phone: str) -> Booking:
    """One answer for every miss, and only misses count towards the limit."""
    ip = _client_ip(request)
    if lookup_limiter.blocked(ip):
        raise _too_many()
    booking = await find_booking(session, code, phone)
    if booking is None:
        lookup_limiter.hit(ip)
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/track", response_model=TrackedBookingOut)
async def track(body: TrackIn, request: Request, session: Session):
    booking = await _lookup(session, request, body.code, body.phone)
    paid, pending, balance = payment_summary(booking.total, booking.payments)
    public = await load_public_settings(session)
    return TrackedBookingOut(
        code=booking.code,
        status=booking.status,
        is_rush=booking.is_rush,
        provisional=booking.delivery_fee_custom,
        event_type=booking.event_type,
        event_date=booking.event_date,
        start_time=booking.start_time,
        hours=booking.hours,
        guests=booking.guests,
        venue_name=booking.venue_name,
        venue_address=booking.venue_address,
        items=[
            TrackedItemOut(
                name_sw=item.product.name_sw,
                name_en=item.product.name_en,
                unit=item.product.unit,
                qty=item.qty,
                unit_price=item.unit_price,
                line_total=item.qty * item.unit_price,
            )
            for item in booking.items
        ],
        addons=[
            TrackedAddonOut(
                name_sw=line.addon.name_sw,
                name_en=line.addon.name_en,
                qty=line.qty,
                unit_price=line.unit_price,
                line_total=line.qty * line.unit_price,
            )
            for line in booking.addons
        ],
        subtotal=booking.subtotal,
        addons_total=booking.addons_total,
        delivery_fee=booking.delivery_fee,
        empties_deposit=booking.empties_deposit,
        total=booking.total,
        deposit_due=booking.deposit_due,
        balance_due_date=booking.balance_due_date,
        amount_paid=paid,
        amount_pending=pending,
        balance_due=balance,
        payments=[PaymentOut.model_validate(p) for p in booking.payments],
        payment_instructions=_payment_instructions(public),
    )


@router.post("/bookings/{code}/payments", response_model=PaymentOut, status_code=201)
async def submit_payment_reference(
    code: str, body: PaymentIn, request: Request, session: Session, background: BackgroundTasks
):
    booking = await _lookup(session, request, code, body.phone)
    new = NewPayment(
        kind=body.kind, method=body.method, amount=body.amount, reference=body.reference
    )
    try:
        payment = await submit_payment(session, booking, new)
    except DuplicateReference as exc:
        raise HTTPException(status_code=409, detail={"code": "duplicate_reference"}) from exc
    except BookingClosed as exc:
        raise HTTPException(status_code=409, detail={"code": "booking_closed"}) from exc
    business = await load_notification_email(session)
    background.add_task(send_email, payment_to_business(business, booking.code, payment))
    return payment
