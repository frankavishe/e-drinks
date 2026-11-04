"""Add-on availability over setup-to-collection windows. Booking times are stored in UTC."""

from datetime import date, datetime, time, timedelta, timezone
from itertools import count

import pytest
import pytest_asyncio

from app.models import Addon, Booking, BookingAddon, Customer
from app.services.availability import addon_availability, is_rush, today_eat
from app.services.pricing import PricingSettings, QuoteError

EAT = timezone(timedelta(hours=3))
_codes = count(1)


def at(day, hour):
    return datetime(2026, 12, day, hour, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def cooler(session):
    addon = Addon(name_sw="Jokofu", name_en="Cooler", kind="cooler", price=15000, owned_capacity=10)
    session.add(addon)
    session.add(Customer(id=1, name="Asha", phone="255700000001"))
    await session.commit()
    return addon


async def hold(session, addon, qty, setup_at, collect_at, status="confirmed"):
    booking = Booking(
        code=f"ED-2026-{next(_codes):04d}",
        customer_id=1,
        event_type="wedding",
        event_date=date(2026, 12, 12),
        start_time=time(15),
        hours=5,
        guests=100,
        setup_at=setup_at,
        collect_at=collect_at,
        status=status,
        addons=[BookingAddon(addon_id=addon.id, qty=qty, unit_price=addon.price)],
    )
    session.add(booking)
    await session.commit()
    return booking


async def free(session, addon, setup_at, collect_at, **kwargs):
    result = await addon_availability(session, [addon.id], setup_at, collect_at, **kwargs)
    return result[addon.id]


async def test_no_bookings_leaves_full_capacity(session, cooler):
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 10


async def test_overlapping_confirmed_booking_reduces_free_count(session, cooler):
    await hold(session, cooler, 7, at(12, 10), at(12, 16))
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 3


async def test_touching_windows_do_not_conflict(session, cooler):
    await hold(session, cooler, 7, at(12, 8), at(12, 12))  # ends as we start
    await hold(session, cooler, 7, at(12, 20), at(12, 23))  # starts as we end
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 10


async def test_separate_windows_do_not_conflict(session, cooler):
    await hold(session, cooler, 7, at(10, 8), at(10, 12))
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 10


@pytest.mark.parametrize("status", ["confirmed", "fully_paid", "delivered"])
async def test_statuses_that_hold_equipment(session, cooler, status):
    await hold(session, cooler, 4, at(12, 10), at(12, 16), status=status)
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 6


@pytest.mark.parametrize("status", ["request", "quoted", "returns_settled", "closed", "cancelled"])
async def test_statuses_that_do_not_hold_equipment(session, cooler, status):
    await hold(session, cooler, 4, at(12, 10), at(12, 16), status=status)
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 10


async def test_bookings_that_do_not_overlap_each_other_count_as_the_peak(session, cooler):
    await hold(session, cooler, 4, at(11, 18), at(11, 22))  # Friday night
    await hold(session, cooler, 5, at(12, 8), at(12, 12))  # Saturday morning
    assert await free(session, cooler, at(11, 12), at(12, 20)) == 5


async def test_back_to_back_bookings_count_as_the_peak(session, cooler):
    await hold(session, cooler, 4, at(12, 8), at(12, 12))
    await hold(session, cooler, 5, at(12, 12), at(12, 16))
    assert await free(session, cooler, at(12, 6), at(12, 20)) == 5


async def test_bookings_that_overlap_each_other_add_up(session, cooler):
    await hold(session, cooler, 4, at(12, 8), at(12, 14))
    await hold(session, cooler, 5, at(12, 12), at(12, 16))
    assert await free(session, cooler, at(12, 6), at(12, 20)) == 1


async def test_overlap_before_our_window_opens_does_not_count(session, cooler):
    # These two only overlap each other from 08:00 to 10:00, before the window opens at 11:00.
    await hold(session, cooler, 4, at(12, 6), at(12, 13))
    await hold(session, cooler, 5, at(12, 8), at(12, 10))
    assert await free(session, cooler, at(12, 11), at(12, 20)) == 6


async def test_next_morning_collection_is_one_continuous_window(session, cooler):
    await hold(session, cooler, 6, at(13, 7), at(13, 11))  # after midnight, before we collect
    assert await free(session, cooler, at(12, 15), at(13, 9)) == 4


async def test_exclude_booking_id_ignores_that_booking(session, cooler):
    booking = await hold(session, cooler, 7, at(12, 10), at(12, 16))
    assert await free(session, cooler, at(12, 12), at(12, 20), exclude_booking_id=booking.id) == 10


async def test_unlimited_capacity_is_none(session, cooler):
    ice = Addon(name_sw="Barafu", name_en="Ice", kind="ice", price=3000, owned_capacity=None)
    session.add(ice)
    await session.commit()
    assert await free(session, ice, at(12, 12), at(12, 20)) is None


async def test_overbooked_addon_reports_zero_not_negative(session, cooler):
    await hold(session, cooler, 12, at(12, 10), at(12, 16))
    assert await free(session, cooler, at(12, 12), at(12, 20)) == 0


async def test_window_in_another_offset_is_compared_as_the_same_instant(session, cooler):
    await hold(session, cooler, 7, at(12, 8), at(12, 12))  # ends 12:00 UTC = 15:00 EAT
    touching = datetime(2026, 12, 12, 15, tzinfo=EAT)
    overlapping = datetime(2026, 12, 12, 14, tzinfo=EAT)
    end = datetime(2026, 12, 12, 23, tzinfo=EAT)
    assert await free(session, cooler, touching, end) == 10
    assert await free(session, cooler, overlapping, end) == 3


# --- T022: rush requests ---------------------------------------------------------------------

TODAY = date(2026, 12, 1)
RUSH_SETTINGS = PricingSettings(notice_days=3, notice_days_servers=7)


@pytest.mark.parametrize(
    ("days_ahead", "has_staff", "expected"),
    [
        (0, False, True),
        (2, False, True),  # notice - 1
        (3, False, False),  # exactly the notice
        (8, False, False),
        (5, True, True),
        (6, True, True),  # server notice - 1
        (7, True, False),  # exactly the server notice
        (8, True, False),
    ],
)
def test_is_rush_at_the_boundaries(days_ahead, has_staff, expected):
    event = TODAY + timedelta(days=days_ahead)
    assert is_rush(event, TODAY, has_staff, RUSH_SETTINGS) is expected


def test_is_rush_uses_the_notice_settings():
    event = TODAY + timedelta(days=5)
    assert is_rush(event, TODAY, False, PricingSettings(notice_days=6)) is True
    assert is_rush(event, TODAY, True, PricingSettings(notice_days_servers=4)) is False


def test_past_event_date_is_rejected():
    with pytest.raises(QuoteError, match="past"):
        is_rush(TODAY - timedelta(days=1), TODAY, False, RUSH_SETTINGS)


def test_today_is_the_date_in_dar_es_salaam():
    # 22:00 UTC is already 01:00 the next day in East Africa Time.
    assert today_eat(datetime(2026, 12, 1, 22, tzinfo=timezone.utc)) == date(2026, 12, 2)
    assert today_eat(datetime(2026, 12, 1, 20, tzinfo=timezone.utc)) == date(2026, 12, 1)
