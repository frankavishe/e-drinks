"""Read side of the admin area: finding bookings and working out figures about them."""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Booking, BookingAddon, BookingItem, Customer, Payment, Profile
from app.services.bookings import FINISHED_STATUSES

UPCOMING_DAYS = 14

_FOR_ROW = (selectinload(Booking.customer), selectinload(Booking.payments))
_FOR_DETAIL = (
    *_FOR_ROW,
    selectinload(Booking.items).selectinload(BookingItem.product),
    selectinload(Booking.addons).selectinload(BookingAddon.addon),
    selectinload(Booking.history),
)


@dataclass(frozen=True)
class BookingFilters:
    q: str = ""
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    rush: bool | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class Financials:
    goods_total: int
    revenue: int
    profit: int


def _search(q: str):
    """Number or name as typed; phone by its digits, so 07xx, 2557xx and +255 7xx all match."""
    conditions = [Booking.code.icontains(q, autoescape=True), Customer.name.icontains(q, autoescape=True)]
    digits = re.sub(r"\D", "", q).lstrip("0")
    if digits:
        conditions.append(Customer.phone.contains(digits, autoescape=True))
    return or_(*conditions)


def _conditions(filters: BookingFilters) -> list:
    conditions = []
    q = filters.q.strip()
    if q:
        conditions.append(_search(q))
    if filters.status is not None:
        conditions.append(Booking.status == filters.status)
    if filters.date_from is not None:
        conditions.append(Booking.event_date >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(Booking.event_date <= filters.date_to)
    if filters.rush is not None:
        conditions.append(Booking.is_rush.is_(filters.rush))
    return conditions


async def list_bookings(session: AsyncSession, filters: BookingFilters) -> tuple[int, list[Booking]]:
    """(matches in total, this page), latest event first."""
    conditions = _conditions(filters)
    total = await session.scalar(
        select(func.count(Booking.id)).join(Booking.customer).where(*conditions)
    )
    rows = await session.scalars(
        select(Booking)
        .join(Booking.customer)
        .where(*conditions)
        .options(*_FOR_ROW)
        .order_by(Booking.event_date.desc(), Booking.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
        .execution_options(populate_existing=True)
    )
    return total, list(rows)


async def calendar_bookings(session: AsyncSession, first: date, last: date) -> list[Booking]:
    """Bookings with an event from first to last, earliest first. Cancelled ones are left out."""
    rows = await session.scalars(
        select(Booking)
        .where(Booking.event_date >= first, Booking.event_date <= last, Booking.status != "cancelled")
        .options(selectinload(Booking.customer))
        .order_by(Booking.event_date, Booking.start_time, Booking.id)
    )
    return list(rows)


async def overview(session: AsyncSession, today: date) -> tuple[list[Booking], list[Booking]]:
    """(today's events, those in the next UPCOMING_DAYS days). Finished bookings are left out."""
    rows = list(await session.scalars(
        select(Booking)
        .where(
            Booking.status.not_in(FINISHED_STATUSES),
            Booking.event_date >= today,
            Booking.event_date <= today + timedelta(days=UPCOMING_DAYS),
        )
        .options(*_FOR_ROW)
        .order_by(Booking.event_date, Booking.start_time, Booking.id)
        .execution_options(populate_existing=True)
    ))
    return [b for b in rows if b.event_date == today], [b for b in rows if b.event_date > today]


async def load_booking(session: AsyncSession, booking_id: int, *, lock: bool = False) -> Booking | None:
    """The booking with everything the detail screen shows. `lock` holds its row until commit."""
    stmt = (
        select(Booking)
        .where(Booking.id == booking_id)
        .options(*_FOR_DETAIL)
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def actor_names(session: AsyncSession, booking: Booking) -> dict[uuid.UUID, str]:
    """Names of the people who confirmed payments or changed the stage."""
    ids = {p.confirmed_by for p in booking.payments} | {h.changed_by for h in booking.history}
    ids.discard(None)
    if not ids:
        return {}
    return dict((await session.execute(select(Profile.id, Profile.name).where(Profile.id.in_(ids)))).all())


def financials(booking: Booking) -> Financials:
    """From the booking's snapshots. The empties deposit is refundable, so it isn't revenue."""
    goods_total = sum(item.qty * item.unit_cost for item in booking.items)
    revenue = booking.subtotal + booking.addons_total + booking.delivery_fee
    return Financials(goods_total=goods_total, revenue=revenue, profit=revenue - goods_total)


def refunded_total(payments: Iterable[Payment]) -> int:
    return sum(p.amount for p in payments if p.kind == "refund" and p.status == "confirmed")
