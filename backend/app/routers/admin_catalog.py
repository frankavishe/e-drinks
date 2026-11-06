"""Catalog, zones, venues and settings. Included into the admin router, which gates every route here to staff
and owner; each write also requires the owner."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_role
from app.db import Base, get_session
from app.models import Addon, Area, Package, PackageRule, PriceTier, Product, Profile, StockLevel, Venue, Zone
from app.schemas.admin_catalog import (
    AddonCreate,
    AddonOwnerOut,
    AddonPatch,
    AddonStaffOut,
    AreaAdminOut,
    AreaIn,
    AreaPatch,
    PackageAdminOut,
    PackageIn,
    PackagePatch,
    ProductIn,
    ProductOwnerOut,
    ProductPatch,
    ProductStaffOut,
    RuleIn,
    TierIn,
    VenueAdminOut,
    VenueIn,
    VenuePatch,
    ZoneAdminOut,
    ZoneIn,
    ZonePatch,
)
from app.services.catalog_admin import (
    apply_patch,
    commit_or_refuse,
    delete_record,
    ensure_unique,
    load_settings,
    update_settings,
    validate_rules,
    validate_tiers,
)

router = APIRouter(tags=["admin catalog"])

Session = Annotated[AsyncSession, Depends(get_session)]
Actor = Annotated[Profile, Depends(require_role("staff", "owner"))]
OWNER_ONLY = [Depends(require_role("owner"))]


async def _found(session: AsyncSession, model: type[Base], record_id: int):
    record = await session.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Not found")
    return record


async def _delete(session: AsyncSession, model: type[Base], record_id: int) -> None:
    await delete_record(session, await _found(session, model, record_id))


def _patch_values(body) -> dict:
    return body.model_dump(exclude_unset=True)


# Products


async def _product(session: AsyncSession, product_id: int) -> Product:
    product = await session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.tiers))
        .execution_options(populate_existing=True)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Not found")
    return product


def _tiers(tiers: list[TierIn]) -> list[PriceTier]:
    validate_tiers((tier.min_qty, tier.unit_price) for tier in tiers)
    return [PriceTier(min_qty=tier.min_qty, unit_price=tier.unit_price) for tier in tiers]


@router.get("/products", response_model=list[ProductOwnerOut | ProductStaffOut])
async def get_products(session: Session, actor: Actor):
    """The owner's class only for the owner; everyone else gets the one with no cost field."""
    out = ProductOwnerOut if actor.role == "owner" else ProductStaffOut
    rows = await session.scalars(select(Product).options(selectinload(Product.tiers)).order_by(Product.id))
    return [out.model_validate(row) for row in rows]


@router.post("/products", response_model=ProductOwnerOut, status_code=201, dependencies=OWNER_ONLY)
async def create_product(body: ProductIn, session: Session):
    tiers = _tiers(body.tiers)
    product = Product(**body.model_dump(exclude={"tiers"}), tiers=tiers)
    session.add(product)
    await session.flush()
    session.add(StockLevel(product_id=product.id, on_hand=0))
    await session.commit()
    return await _product(session, product.id)


@router.patch("/products/{product_id}", response_model=ProductOwnerOut, dependencies=OWNER_ONLY)
async def patch_product(product_id: int, body: ProductPatch, session: Session):
    apply_patch(await _product(session, product_id), _patch_values(body), nullable={"image_url"})
    await session.commit()
    return await _product(session, product_id)


@router.put("/products/{product_id}/tiers", response_model=ProductOwnerOut, dependencies=OWNER_ONLY)
async def put_tiers(product_id: int, body: list[TierIn], session: Session):
    product = await _product(session, product_id)
    product.tiers = _tiers(body)
    await session.commit()
    return await _product(session, product_id)


@router.delete("/products/{product_id}", status_code=204, dependencies=OWNER_ONLY)
async def delete_product(product_id: int, session: Session):
    await _delete(session, Product, product_id)


# Packages


async def _package(session: AsyncSession, package_id: int) -> Package:
    package = await session.scalar(
        select(Package)
        .where(Package.id == package_id)
        .options(selectinload(Package.rules))
        .execution_options(populate_existing=True)
    )
    if package is None:
        raise HTTPException(status_code=404, detail="Not found")
    return package


async def _rules(session: AsyncSession, rules: list[RuleIn]) -> list[PackageRule]:
    await validate_rules(session, (rule.product_id for rule in rules))
    return [PackageRule(**rule.model_dump()) for rule in rules]


@router.get("/packages", response_model=list[PackageAdminOut])
async def get_packages(session: Session):
    stmt = select(Package).options(selectinload(Package.rules)).order_by(Package.sort_order, Package.id)
    return (await session.scalars(stmt)).all()


@router.post("/packages", response_model=PackageAdminOut, status_code=201, dependencies=OWNER_ONLY)
async def create_package(body: PackageIn, session: Session):
    rules = await _rules(session, body.rules)
    await ensure_unique(session, Package.slug, body.slug)
    package = Package(**body.model_dump(exclude={"rules"}), rules=rules)
    session.add(package)
    await commit_or_refuse(session, "already_exists")
    return await _package(session, package.id)


@router.patch("/packages/{package_id}", response_model=PackageAdminOut, dependencies=OWNER_ONLY)
async def patch_package(package_id: int, body: PackagePatch, session: Session):
    package = await _package(session, package_id)
    await ensure_unique(session, Package.slug, body.slug, package_id)
    apply_patch(package, _patch_values(body))
    await commit_or_refuse(session, "already_exists")
    return await _package(session, package_id)


@router.put("/packages/{package_id}/rules", response_model=PackageAdminOut, dependencies=OWNER_ONLY)
async def put_rules(package_id: int, body: list[RuleIn], session: Session):
    package = await _package(session, package_id)
    package.rules = await _rules(session, body)
    await session.commit()
    return await _package(session, package_id)


@router.delete("/packages/{package_id}", status_code=204, dependencies=OWNER_ONLY)
async def delete_package(package_id: int, session: Session):
    await _delete(session, Package, package_id)


# Add-ons


@router.get("/addons", response_model=list[AddonOwnerOut | AddonStaffOut])
async def get_addons(session: Session, actor: Actor):
    out = AddonOwnerOut if actor.role == "owner" else AddonStaffOut
    return [out.model_validate(row) for row in await session.scalars(select(Addon).order_by(Addon.id))]


@router.post("/addons", response_model=AddonOwnerOut, status_code=201, dependencies=OWNER_ONLY)
async def create_addon(body: AddonCreate, session: Session):
    addon = Addon(**body.model_dump())
    session.add(addon)
    await session.commit()
    return addon


@router.patch("/addons/{addon_id}", response_model=AddonOwnerOut, dependencies=OWNER_ONLY)
async def patch_addon(addon_id: int, body: AddonPatch, session: Session):
    addon = await _found(session, Addon, addon_id)
    apply_patch(addon, _patch_values(body), nullable={"owned_capacity"})
    await session.commit()
    return addon


@router.delete("/addons/{addon_id}", status_code=204, dependencies=OWNER_ONLY)
async def delete_addon(addon_id: int, session: Session):
    await _delete(session, Addon, addon_id)


# Zones and areas


def _zone_out(zone: Zone, areas: list[Area]) -> ZoneAdminOut:
    return ZoneAdminOut(
        id=zone.id,
        name=zone.name,
        delivery_fee=zone.delivery_fee,
        areas=[AreaAdminOut.model_validate(area) for area in areas if area.zone_id == zone.id],
    )


async def _areas(session: AsyncSession) -> list[Area]:
    return list(await session.scalars(select(Area).order_by(Area.name)))


@router.get("/zones", response_model=list[ZoneAdminOut])
async def get_zones(session: Session):
    areas = await _areas(session)
    return [_zone_out(zone, areas) for zone in await session.scalars(select(Zone).order_by(Zone.id))]


@router.post("/zones", response_model=ZoneAdminOut, status_code=201, dependencies=OWNER_ONLY)
async def create_zone(body: ZoneIn, session: Session):
    zone = Zone(**body.model_dump())
    session.add(zone)
    await session.commit()
    return _zone_out(zone, [])


@router.patch("/zones/{zone_id}", response_model=ZoneAdminOut, dependencies=OWNER_ONLY)
async def patch_zone(zone_id: int, body: ZonePatch, session: Session):
    zone = await _found(session, Zone, zone_id)
    apply_patch(zone, _patch_values(body))
    await session.commit()
    return _zone_out(zone, await _areas(session))


@router.delete("/zones/{zone_id}", status_code=204, dependencies=OWNER_ONLY)
async def delete_zone(zone_id: int, session: Session):
    await _delete(session, Zone, zone_id)


@router.post("/areas", response_model=AreaAdminOut, status_code=201, dependencies=OWNER_ONLY)
async def create_area(body: AreaIn, session: Session):
    await _found(session, Zone, body.zone_id)
    await ensure_unique(session, Area.name, body.name)
    area = Area(**body.model_dump())
    session.add(area)
    await commit_or_refuse(session, "already_exists")
    return area


@router.patch("/areas/{area_id}", response_model=AreaAdminOut, dependencies=OWNER_ONLY)
async def patch_area(area_id: int, body: AreaPatch, session: Session):
    area = await _found(session, Area, area_id)
    if body.zone_id is not None:
        await _found(session, Zone, body.zone_id)
    await ensure_unique(session, Area.name, body.name, area_id)
    apply_patch(area, _patch_values(body))
    await commit_or_refuse(session, "already_exists")
    return area


@router.delete("/areas/{area_id}", status_code=204, dependencies=OWNER_ONLY)
async def delete_area(area_id: int, session: Session):
    await _delete(session, Area, area_id)


# Venues


@router.get("/venues", response_model=list[VenueAdminOut])
async def get_venues(session: Session):
    return (await session.scalars(select(Venue).order_by(Venue.name))).all()


@router.post("/venues", response_model=VenueAdminOut, status_code=201, dependencies=OWNER_ONLY)
async def create_venue(body: VenueIn, session: Session):
    await _found(session, Area, body.area_id)
    venue = Venue(**body.model_dump())
    session.add(venue)
    await session.commit()
    return venue


@router.patch("/venues/{venue_id}", response_model=VenueAdminOut, dependencies=OWNER_ONLY)
async def patch_venue(venue_id: int, body: VenuePatch, session: Session):
    venue = await _found(session, Venue, venue_id)
    if body.area_id is not None:
        await _found(session, Area, body.area_id)
    apply_patch(venue, _patch_values(body))
    await session.commit()
    return venue


@router.delete("/venues/{venue_id}", status_code=204, dependencies=OWNER_ONLY)
async def delete_venue(venue_id: int, session: Session):
    await _delete(session, Venue, venue_id)


# Settings


@router.get("/settings", response_model=dict[str, str])
async def get_settings_map(session: Session):
    return await load_settings(session)


@router.put("/settings", response_model=dict[str, str], dependencies=OWNER_ONLY)
async def put_settings(body: dict[str, str], session: Session):
    return await update_settings(session, body)
