"""Add-on capacity over a setup-to-collection window, and the rush/notice check."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Addon, Booking, BookingAddon
from app.services.pricing import PricingSettings, QuoteError

# Equipment is out from Confirmed until Returns are settled.
HOLDING_STATUSES = ("confirmed", "fully_paid", "delivered")

# Tanzania is UTC+3 all year. A fixed offset also avoids needing tzdata on Windows.
EAT = timezone(timedelta(hours=3))


def today_eat(now: datetime | None = None) -> date:
    """Today's date in Dar es Salaam, which is the owner's business day."""
    return (now or datetime.now(timezone.utc)).astimezone(EAT).date()


def is_rush(
    event_date: date, today: date, has_staff_addon: bool, settings: PricingSettings
) -> bool:
    """True when the event is closer than the applicable notice period."""
    days_ahead = (event_date - today).days
    if days_ahead < 0:
        raise QuoteError(f"Event date {event_date} is in the past")
    return days_ahead < (settings.notice_days_servers if has_staff_addon else settings.notice_days)


def _utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes (stored as UTC here); Postgres returns aware ones."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _peak(events: list[tuple[datetime, int]]) -> int:
    """Highest running total. Releases sort before holds at the same instant (half-open windows)."""
    peak = running = 0
    for _, change in sorted(events):
        running += change
        peak = max(peak, running)
    return peak


async def addon_availability(
    session: AsyncSession,
    addon_ids: Iterable[int],
    setup_at: datetime,
    collect_at: datetime,
    exclude_booking_id: int | None = None,
) -> dict[int, int | None]:
    """Free count per add-on across [setup_at, collect_at); None means unlimited."""
    ids = list(addon_ids)
    start, end = _utc(setup_at), _utc(collect_at)

    stmt = (
        select(BookingAddon.addon_id, BookingAddon.qty, Booking.setup_at, Booking.collect_at)
        .join(Booking)
        .where(
            BookingAddon.addon_id.in_(ids),
            Booking.status.in_(HOLDING_STATUSES),
            Booking.setup_at < end,
            Booking.collect_at > start,
        )
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(Booking.id != exclude_booking_id)

    events: dict[int, list[tuple[datetime, int]]] = defaultdict(list)
    for addon_id, qty, held_from, held_to in await session.execute(stmt):
        events[addon_id].append((max(_utc(held_from), start), qty))
        events[addon_id].append((min(_utc(held_to), end), -qty))

    capacities = await session.execute(
        select(Addon.id, Addon.owned_capacity).where(Addon.id.in_(ids))
    )
    return {
        addon_id: None if capacity is None else max(capacity - _peak(events[addon_id]), 0)
        for addon_id, capacity in capacities
    }
