"""Login-free catalog and quote endpoints. Totals only ever come from the server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Addon, Area, Package, Product, Venue, Zone
from app.schemas.public import (
    AddonOut,
    AreaOut,
    AreasOut,
    PackageOut,
    ProductOut,
    QuoteIn,
    QuoteOut,
    VenueOut,
    ZoneOut,
)
from app.services.catalog_loader import load_catalog
from app.services.pricing import CatalogError, QuoteError, QuoteRequest, build_quote
from app.services.settings_store import load_pricing_settings

router = APIRouter(prefix="/public", tags=["public"])

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
    req = _to_request(body)
    loaded_catalog = await load_catalog(session)
    settings = await load_pricing_settings(session)
    try:
        result = build_quote(req, loaded_catalog, settings, availability={}, is_rush=False)
    except (QuoteError, CatalogError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuoteOut.model_validate(result)
