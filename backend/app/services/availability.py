"""Add-on capacity over a setup-to-collection window, usage per day, and the rush/notice check."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

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


def _clipped(
    held_from: datetime, held_to: datetime, qty: int, start: datetime, end: datetime
) -> list[tuple[datetime, int]]:
    """The hold and release of a hold inside [start, end); nothing if it doesn't touch that window."""
    held_from, held_to = _utc(held_from), _utc(held_to)
    if held_from >= end or held_to <= start:
        return []
    return [(max(held_from, start), qty), (min(held_to, end), -qty)]


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
        events[addon_id].extend(_clipped(held_from, held_to, qty, start, end))

    capacities = await session.execute(
        select(Addon.id, Addon.owned_capacity).where(Addon.id.in_(ids))
    )
    return {
        addon_id: None if capacity is None else max(capacity - _peak(events[addon_id]), 0)
        for addon_id, capacity in capacities
    }


@dataclass(frozen=True)
class DayAddonUsage:
    addon_id: int
    name_sw: str
    name_en: str
    committed: int
    owned: int | None


def _eat_midnight(day: date) -> datetime:
    """The start of a Dar es Salaam day, in UTC as bookings are stored."""
    return datetime.combine(day, time.min, tzinfo=EAT).astimezone(timezone.utc)


async def daily_usage(
    session: AsyncSession, first: date, last: date
) -> dict[date, list[DayAddonUsage]]:
    """Each add-on's peak on each EAT day from first to last. Only add-ons in use that day are listed."""
    stmt = (
        select(
            Addon.id,
            Addon.name_sw,
            Addon.name_en,
            Addon.owned_capacity,
            BookingAddon.qty,
            Booking.setup_at,
            Booking.collect_at,
        )
        .select_from(BookingAddon)
        .join(Booking, BookingAddon.booking_id == Booking.id)
        .join(Addon, BookingAddon.addon_id == Addon.id)
        .where(
            Booking.status.in_(HOLDING_STATUSES),
            Booking.setup_at < _eat_midnight(last + timedelta(days=1)),
            Booking.collect_at > _eat_midnight(first),
        )
        .order_by(Addon.id)
    )
    holds: dict[tuple[int, str, str, int | None], list[tuple[datetime, datetime, int]]] = defaultdict(list)
    for addon_id, name_sw, name_en, owned, qty, held_from, held_to in await session.execute(stmt):
        holds[(addon_id, name_sw, name_en, owned)].append((held_from, held_to, qty))

    usage: dict[date, list[DayAddonUsage]] = {}
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        start, end = _eat_midnight(day), _eat_midnight(day + timedelta(days=1))
        usage[day] = []
        for (addon_id, name_sw, name_en, owned), addon_holds in holds.items():
            events = [
                event
                for held_from, held_to, qty in addon_holds
                for event in _clipped(held_from, held_to, qty, start, end)
            ]
            committed = _peak(events)
            if committed:
                usage[day].append(DayAddonUsage(addon_id, name_sw, name_en, committed, owned))
    return usage
