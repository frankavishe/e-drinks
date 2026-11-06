"""GET /admin/calendar: each EAT day's bookings and add-on usage. Booking times are stored in UTC."""

from datetime import date, datetime, time, timedelta, timezone
from itertools import count

import pytest
import pytest_asyncio

from app.config import get_settings
from app.models import Addon, Booking, BookingAddon, Customer
from tests.test_admin_api import _headers, assert_staff_safe
from tests.test_auth import SECRET

_codes = count(1)

SATURDAY = date(2026, 12, 12)


def utc(day, hour):
    return datetime(2026, 12, day, hour, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", SECRET)


@pytest_asyncio.fixture
async def staff(seeded_session):
    return await _headers(seeded_session, "staff", "Amina")


@pytest_asyncio.fixture
async def customer(seeded_session):
    person = Customer(name="Asha", phone="255711111111")
    seeded_session.add(person)
    await seeded_session.commit()
    return person


@pytest_asyncio.fixture
async def cooler(seeded_session):
    addon = Addon(name_sw="Jokofu", name_en="Cooler", kind="cooler", price=15000, owned_capacity=5)
    seeded_session.add(addon)
    await seeded_session.commit()
    return addon


@pytest_asyncio.fixture
async def ice(seeded_session):
    addon = Addon(name_sw="Barafu", name_en="Ice", kind="ice", price=5000, owned_capacity=None)
    seeded_session.add(addon)
    await seeded_session.commit()
    return addon


@pytest.fixture
def place(seeded_session, customer):
    """A booking with an explicit equipment window, by default the morning to the evening of the 12th."""

    async def _place(
        addons=(),
        status="confirmed",
        event_date=SATURDAY,
        setup_at=None,
        collect_at=None,
        start_time=time(16),
    ):
        booking = Booking(
            code=f"ED-CAL-{next(_codes):04d}",
            customer_id=customer.id,
            event_type="wedding",
            event_date=event_date,
            start_time=start_time,
            hours=5,
            guests=100,
            setup_at=setup_at or utc(12, 6),
            collect_at=collect_at or utc(12, 18),
            status=status,
            addons=[
                BookingAddon(addon_id=addon.id, qty=qty, unit_price=addon.price) for addon, qty in addons
            ],
        )
        seeded_session.add(booking)
        await seeded_session.commit()
        return booking

    return _place


@pytest.fixture
def calendar(client, staff):
    """The days in the range, keyed by ISO date."""

    async def _calendar(first=SATURDAY, last=SATURDAY):
        res = await client.get(
            "/admin/calendar", params={"from": first.isoformat(), "to": last.isoformat()}, headers=staff
        )
        assert res.status_code == 200, res.text
        return {day["date"]: day for day in res.json()["days"]}

    return _calendar


def committed(day, addon) -> int | None:
    return next((a["committed"] for a in day["addons"] if a["addon_id"] == addon.id), None)


async def test_every_day_in_range_appears_in_order(client, staff):
    res = await client.get("/admin/calendar", params={"from": "2026-12-30", "to": "2027-01-02"}, headers=staff)
    assert res.status_code == 200
    days = res.json()["days"]
    assert [d["date"] for d in days] == ["2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"]
    assert all(d["bookings"] == [] and d["addons"] == [] for d in days)


async def test_two_bookings_on_one_day_appear_and_combine(calendar, place, cooler):
    first = await place(addons=[(cooler, 3)], start_time=time(18))
    second = await place(addons=[(cooler, 1)], start_time=time(11))

    day = (await calendar())["2026-12-12"]

    assert [b["code"] for b in day["bookings"]] == [second.code, first.code]  # by start time
    assert day["bookings"][0] == {
        "id": second.id,
        "code": second.code,
        "status": "confirmed",
        "is_rush": False,
        "customer_name": "Asha",
        "start_time": "11:00:00",
    }
    assert day["addons"] == [
        {"addon_id": cooler.id, "name_sw": "Jokofu", "name_en": "Cooler", "committed": 4, "owned": 5}
    ]


async def test_multi_day_window_counts_on_each_day_it_touches(calendar, place, cooler):
    await place(addons=[(cooler, 2)], setup_at=utc(11, 6), collect_at=utc(13, 6))

    days = await calendar(date(2026, 12, 10), date(2026, 12, 14))

    assert committed(days["2026-12-10"], cooler) is None
    assert committed(days["2026-12-11"], cooler) == 2
    assert committed(days["2026-12-12"], cooler) == 2
    assert committed(days["2026-12-13"], cooler) == 2
    assert committed(days["2026-12-14"], cooler) is None
    # The booking itself sits on its event date only.
    assert len(days["2026-12-12"]["bookings"]) == 1
    assert days["2026-12-11"]["bookings"] == []


async def test_a_request_appears_but_holds_nothing(calendar, place, cooler):
    booking = await place(addons=[(cooler, 3)], status="request")

    day = (await calendar())["2026-12-12"]

    assert [b["code"] for b in day["bookings"]] == [booking.code]
    assert day["addons"] == []


async def test_a_cancelled_booking_appears_nowhere(calendar, place, cooler):
    await place(addons=[(cooler, 3)], status="cancelled")

    day = (await calendar())["2026-12-12"]

    assert day["bookings"] == []
    assert day["addons"] == []


@pytest.mark.parametrize("status", ["returns_settled", "closed"])
async def test_a_finished_booking_stays_listed_but_has_released_its_equipment(
    calendar, place, cooler, status
):
    booking = await place(addons=[(cooler, 3)], status=status)

    day = (await calendar())["2026-12-12"]

    assert [b["code"] for b in day["bookings"]] == [booking.code]
    assert day["addons"] == []


async def test_non_overlapping_bookings_on_one_day_peak_rather_than_sum(calendar, place, cooler):
    await place(addons=[(cooler, 3)], setup_at=utc(12, 6), collect_at=utc(12, 10))
    await place(addons=[(cooler, 4)], setup_at=utc(12, 10), collect_at=utc(12, 14))

    day = (await calendar())["2026-12-12"]

    assert committed(day, cooler) == 4


async def test_a_day_starts_at_midnight_in_dar_es_salaam(calendar, place, cooler):
    """22:00 UTC on the 11th is already 01:00 on the 12th in EAT."""
    await place(addons=[(cooler, 2)], setup_at=utc(11, 22), collect_at=utc(11, 23))

    days = await calendar(date(2026, 12, 11), date(2026, 12, 12))

    assert committed(days["2026-12-11"], cooler) is None
    assert committed(days["2026-12-12"], cooler) == 2


async def test_a_window_ending_exactly_at_eat_midnight_stays_off_the_next_day(calendar, place, cooler):
    """21:00 UTC on the 12th is midnight between the 12th and the 13th in EAT."""
    await place(addons=[(cooler, 2)], setup_at=utc(12, 6), collect_at=utc(12, 21))

    days = await calendar(date(2026, 12, 12), date(2026, 12, 13))

    assert committed(days["2026-12-12"], cooler) == 2
    assert committed(days["2026-12-13"], cooler) is None


async def test_usage_above_capacity_is_reported_as_it_is(calendar, place, cooler):
    await place(addons=[(cooler, 4)])
    await place(addons=[(cooler, 4)])

    day = (await calendar())["2026-12-12"]

    assert committed(day, cooler) == 8


async def test_unlimited_addon_reports_null_owned(calendar, place, ice):
    await place(addons=[(ice, 9)])

    day = (await calendar())["2026-12-12"]

    assert day["addons"] == [
        {"addon_id": ice.id, "name_sw": "Barafu", "name_en": "Ice", "committed": 9, "owned": None}
    ]


async def test_only_addons_in_use_that_day_are_listed(calendar, place, cooler, ice):
    await place(addons=[(cooler, 1)])

    day = (await calendar())["2026-12-12"]

    assert [a["addon_id"] for a in day["addons"]] == [cooler.id]


async def test_a_booking_outside_the_range_is_left_out(calendar, place, cooler):
    await place(
        addons=[(cooler, 1)],
        event_date=SATURDAY + timedelta(days=7),
        setup_at=utc(19, 6),
        collect_at=utc(19, 18),
    )

    day = (await calendar())["2026-12-12"]

    assert day["bookings"] == []
    assert day["addons"] == []


async def test_range_of_62_days_is_allowed(client, staff):
    res = await client.get("/admin/calendar", params={"from": "2026-11-01", "to": "2027-01-01"}, headers=staff)
    assert res.status_code == 200
    assert len(res.json()["days"]) == 62


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-11-01", "to": "2027-01-02"},  # 63 days
        {"from": "2026-12-02", "to": "2026-12-01"},  # backwards
        {"from": "2026-12-01"},
        {"to": "2026-12-01"},
        {"from": "not-a-date", "to": "2026-12-01"},
    ],
)
async def test_bad_ranges_are_refused(client, staff, params):
    assert (await client.get("/admin/calendar", params=params, headers=staff)).status_code == 422


async def test_staff_see_no_cost_keys(client, staff, place, cooler):
    await place(addons=[(cooler, 1)])
    res = await client.get("/admin/calendar", params={"from": "2026-12-12", "to": "2026-12-12"}, headers=staff)
    assert res.json()["days"][0]["addons"]
    assert_staff_safe(res.json())


async def test_owner_gets_the_calendar(client, seeded_session):
    owner = await _headers(seeded_session, "owner", "Frank")
    res = await client.get("/admin/calendar", params={"from": "2026-12-12", "to": "2026-12-12"}, headers=owner)
    assert res.status_code == 200


async def test_calendar_needs_a_login(client):
    res = await client.get("/admin/calendar", params={"from": "2026-12-12", "to": "2026-12-12"})
    assert res.status_code == 401


async def test_calendar_refuses_planners(client, seeded_session):
    planner = await _headers(seeded_session, "planner", "Paul")
    res = await client.get("/admin/calendar", params={"from": "2026-12-12", "to": "2026-12-12"}, headers=planner)
    assert res.status_code == 403
