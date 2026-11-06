"""Rules for editing the catalog, zones, venues and settings. A refusal is raised before anything is written."""

import re
from collections.abc import Iterable
from dataclasses import fields

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Base
from app.models import (
    Addon,
    Area,
    Booking,
    BookingAddon,
    BookingItem,
    Package,
    PackageRule,
    Product,
    PurchaseNeed,
    Setting,
    StockLevel,
    StockMovement,
    Venue,
    Zone,
)
from app.seed import SETTINGS
from app.services.booking_flow import StageRefused
from app.services.pricing import PricingSettings

PRICING_KEYS = {f.name for f in fields(PricingSettings)}
# Dates are worked out from these, so an absurd value would break every quote.
DAY_COUNT_KEYS = {"notice_days", "notice_days_servers", "balance_due_days"}
MAX_DAYS = 365
MAX_PERCENT = 100

# What stops a record being deleted. Deactivating is the way out for products, packages and add-ons.
REFERENCES = {
    Product: (BookingItem.product_id, PackageRule.product_id, StockMovement.product_id, PurchaseNeed.product_id),
    Package: (Booking.package_id,),
    Addon: (BookingAddon.addon_id,),
    Zone: (Area.zone_id,),
    Area: (Venue.area_id, Booking.area_id),
    Venue: (Booking.venue_id,),
}


class CatalogRefused(StageRefused):
    """A catalog rule said no. Handled like any other refusal: a 409 with a code the UI translates."""


def validate_tiers(tiers: Iterable[tuple[int, int]]) -> None:
    """(min_qty, unit_price) pairs. A lowest tier above 1 would make small orders impossible to price."""
    pairs = list(tiers)
    quantities = [min_qty for min_qty, _ in pairs]
    if (
        not pairs
        or min(quantities) != 1
        or len(set(quantities)) != len(quantities)
        or any(price < 0 for _, price in pairs)
    ):
        raise CatalogRefused("invalid_tiers")


async def validate_rules(session: AsyncSession, product_ids: Iterable[int]) -> None:
    ids = list(product_ids)
    if not ids or len(set(ids)) != len(ids):
        raise CatalogRefused("invalid_rules")
    known = await session.scalars(select(Product.id).where(Product.id.in_(ids)))
    if len(known.all()) != len(ids):
        raise CatalogRefused("invalid_rules")


async def ensure_unique(session: AsyncSession, column, value: str | None, own_id: int | None = None) -> None:
    """For a friendly refusal; `commit_or_refuse` still catches two people saving at once."""
    if value is None:
        return
    model = column.class_
    found = await session.scalar(select(model.id).where(column == value, model.id != own_id).limit(1))
    if found is not None:
        raise CatalogRefused("already_exists")


async def commit_or_refuse(session: AsyncSession, code: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise CatalogRefused(code) from exc


def apply_patch(record: Base, values: dict, nullable: Iterable[str] = ()) -> None:
    """Null means "not sent", except on a field where null is a real value."""
    for key, value in values.items():
        if value is not None or key in nullable:
            setattr(record, key, value)


async def delete_record(session: AsyncSession, record: Base) -> None:
    for column in REFERENCES[type(record)]:
        if await session.scalar(select(column).where(column == record.id).limit(1)) is not None:
            raise CatalogRefused("in_use")
    if isinstance(record, Product):
        stock = await session.get(StockLevel, record.id)
        if stock is not None:
            if stock.on_hand or stock.reserved:
                raise CatalogRefused("in_use")
            await session.delete(stock)
    await session.delete(record)
    await commit_or_refuse(session, "in_use")


async def load_settings(session: AsyncSession) -> dict[str, str]:
    """Every known setting as a string; a missing key reads as blank."""
    rows = await session.execute(select(Setting.key, Setting.value).where(Setting.key.in_(SETTINGS)))
    return {**dict.fromkeys(SETTINGS, ""), **{key: value for key, value in rows}}


def _valid_setting(key: str, value: str) -> bool:
    if key not in SETTINGS:
        return False
    if key not in PRICING_KEYS:
        return True
    # Not str.isdigit(): that accepts digits from other scripts. Twelve digits is well past any real amount.
    if not re.fullmatch(r"[0-9]{1,12}", value):
        return False
    number = int(value)
    if key == "deposit_percent":
        return number <= MAX_PERCENT
    return key not in DAY_COUNT_KEYS or number <= MAX_DAYS


async def update_settings(session: AsyncSession, changes: dict[str, str]) -> dict[str, str]:
    if not all(_valid_setting(key, value) for key, value in changes.items()):
        raise CatalogRefused("invalid_setting")
    for key, value in changes.items():
        row = await session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    await session.commit()
    return await load_settings(session)
