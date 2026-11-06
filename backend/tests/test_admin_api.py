"""The /admin endpoints through the app, with real signed login tokens."""

import re
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.main import app as fastapi_app
from app.models import Booking, BookingItem, BookingStatusHistory, Payment, Product, Profile
from app.services.availability import today_eat
from tests.test_auth import SECRET, make_token
from tests.test_booking_api import booking_body
from tests.test_public_api import ids, walk_keys  # noqa: F401  (ids is a fixture)


def assert_staff_safe(payload):
    """SC-003: nothing a staff member receives may name cost, profit or margin."""
    forbidden = ("cost", "profit", "margin", "goods_total", "revenue", "financials")
    assert not [k for k in walk_keys(payload) if any(word in k.lower() for word in forbidden)]


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", SECRET)


async def _headers(session, role: str, name: str) -> dict[str, str]:
    uid = uuid.uuid4()
    session.add(Profile(id=uid, role=role, name=name))
    await session.commit()
    return {"Authorization": f"Bearer {make_token(uid)}"}


@pytest.fixture
async def staff(seeded_session):
    return await _headers(seeded_session, "staff", "Amina")


@pytest.fixture
async def owner(seeded_session):
    return await _headers(seeded_session, "owner", "Frank")


@pytest.fixture
async def planner(seeded_session):
    return await _headers(seeded_session, "planner", "Paul")


@pytest.fixture
def book(client, ids):
    """Create a booking through the public API; returns its code."""

    async def _book(days=30, phone="0712345678", name="Asha", **overrides):
        payload = await booking_body(client, ids, days=days, name=name, phone=phone, **overrides)
        res = await client.post("/public/bookings", json=payload)
        assert res.status_code == 201, res.text
        return res.json()["code"]

    return _book


async def _booking(session, code: str) -> Booking:
    return await session.scalar(select(Booking).where(Booking.code == code))


async def _set_status(session, code: str, status: str) -> None:
    (await _booking(session, code)).status = status
    await session.commit()


async def _row_id(client, staff, code: str) -> int:
    rows = (await client.get("/admin/bookings", params={"q": code}, headers=staff)).json()["items"]
    return next(r["id"] for r in rows if r["code"] == code)


def _codes(rows) -> list[str]:
    return [r["code"] for r in rows]


# --- Access (FR-001) ---


async def test_me_needs_a_login(client):
    assert (await client.get("/admin/me")).status_code == 401


async def test_me_refuses_planners(client, planner):
    assert (await client.get("/admin/me", headers=planner)).status_code == 403


async def test_me_returns_the_staff_profile(client, staff):
    res = await client.get("/admin/me", headers=staff)
    assert res.status_code == 200
    assert (res.json()["role"], res.json()["name"]) == ("staff", "Amina")


async def test_me_returns_the_owner_profile(client, owner):
    res = await client.get("/admin/me", headers=owner)
    assert res.status_code == 200
    assert (res.json()["role"], res.json()["name"]) == ("owner", "Frank")


def _admin_routes():
    """Every /admin route the app publishes, so a route added later is covered automatically."""
    routes = [
        (method.upper(), re.sub(r"\{\w+\}", "1", path))
        for path, operations in fastapi_app.openapi()["paths"].items()
        if path.startswith("/admin")
        for method in operations
    ]
    assert len(routes) >= 5  # guards these checks against passing on an empty list
    return routes


async def test_every_admin_route_needs_a_login(client):
    for method, path in _admin_routes():
        assert (await client.request(method, path)).status_code == 401, f"{method} {path}"


async def test_every_admin_route_refuses_planners(client, planner):
    for method, path in _admin_routes():
        res = await client.request(method, path, headers=planner)
        assert res.status_code == 403, f"{method} {path}"


# --- Today and Upcoming ---


async def test_overview_splits_today_and_upcoming(client, staff, book):
    today = await book(days=0)
    soon = await book(days=3)
    limit = await book(days=14)
    later = await book(days=15)

    res = await client.get("/admin/overview", headers=staff)

    assert res.status_code == 200
    data = res.json()
    assert _codes(data["today"]) == [today]
    assert _codes(data["upcoming"]) == [soon, limit]
    assert later not in _codes(data["upcoming"])


@pytest.mark.parametrize("status", ["cancelled", "closed"])
async def test_overview_leaves_out_finished_bookings(client, staff, book, seeded_session, status):
    code = await book(days=3)
    await _set_status(seeded_session, code, status)
    data = (await client.get("/admin/overview", headers=staff)).json()
    assert data["upcoming"] == []


async def test_row_shows_stage_rush_and_money(client, staff, book):
    code = await book(days=1)  # inside the notice period
    row = (await client.get("/admin/overview", headers=staff)).json()["upcoming"][0]
    assert row["code"] == code
    assert row["status"] == "request"
    assert row["is_rush"] is True
    assert row["rush_approved"] is False
    assert row["provisional"] is False
    assert row["customer_name"] == "Asha"
    assert row["customer_phone"] == "255712345678"
    assert row["total"] > 0
    assert row["amount_paid"] == 0
    assert row["amount_pending"] == 0


# --- Search and filters ---


async def test_search_by_number(client, staff, book):
    first = await book()
    await book(phone="0755000111", name="Baraka")
    res = await client.get("/admin/bookings", params={"q": first.lower()}, headers=staff)
    assert _codes(res.json()["items"]) == [first]


@pytest.mark.parametrize("phone", ["0755000111", "255755000111", "+255 755 000 111", "755000"])
async def test_search_by_phone_in_any_format(client, staff, book, phone):
    await book()
    wanted = await book(phone="0755000111", name="Baraka")
    res = await client.get("/admin/bookings", params={"q": phone}, headers=staff)
    assert _codes(res.json()["items"]) == [wanted]


async def test_search_by_name(client, staff, book):
    await book()
    wanted = await book(phone="0755000111", name="Baraka")
    res = await client.get("/admin/bookings", params={"q": "bara"}, headers=staff)
    assert _codes(res.json()["items"]) == [wanted]


async def test_search_treats_wildcards_as_text(client, staff, book):
    await book()
    res = await client.get("/admin/bookings", params={"q": "%"}, headers=staff)
    assert res.json()["items"] == []


async def test_filter_by_stage(client, staff, book, seeded_session):
    await book()
    wanted = await book(phone="0755000111")
    await _set_status(seeded_session, wanted, "confirmed")
    res = await client.get("/admin/bookings", params={"status": "confirmed"}, headers=staff)
    assert _codes(res.json()["items"]) == [wanted]


async def test_unknown_stage_is_rejected(client, staff):
    res = await client.get("/admin/bookings", params={"status": "nonsense"}, headers=staff)
    assert res.status_code == 422


async def test_filter_by_date_range_includes_both_ends(client, staff, book):
    start = await book(days=10)
    end = await book(days=12)
    await book(days=9)
    await book(days=13)
    params = {
        "date_from": (today_eat() + timedelta(days=10)).isoformat(),
        "date_to": (today_eat() + timedelta(days=12)).isoformat(),
    }
    res = await client.get("/admin/bookings", params=params, headers=staff)
    assert sorted(_codes(res.json()["items"])) == sorted([start, end])


async def test_filter_by_rush(client, staff, book):
    rush = await book(days=1)
    normal = await book(days=30)
    yes = await client.get("/admin/bookings", params={"rush": "true"}, headers=staff)
    no = await client.get("/admin/bookings", params={"rush": "false"}, headers=staff)
    assert _codes(yes.json()["items"]) == [rush]
    assert _codes(no.json()["items"]) == [normal]


async def test_paging_reports_the_full_total(client, staff, book):
    for days in (20, 21, 22):
        await book(days=days)
    res = await client.get("/admin/bookings", params={"limit": 2, "offset": 2}, headers=staff)
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1


# --- Booking detail ---


async def test_detail_shows_the_whole_booking(client, staff, book, ids, seeded_session):
    code = await book(addons=[{"addon_id": ids["addons"]["cooler"], "qty": 2}])
    await client.post(
        f"/public/bookings/{code}/payments",
        json={"phone": "0712345678", "kind": "deposit", "method": "mpesa", "amount": 1000, "reference": "abc1"},
    )
    booking_id = await _row_id(client, staff, code)

    res = await client.get(f"/admin/bookings/{booking_id}", headers=staff)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["code"] == code
    assert data["customer_phone"] == "255712345678"
    assert data["balance_due"] == data["total"]
    assert data["amount_pending"] == 1000
    assert data["refund_due"] is None
    assert data["refunded"] == 0
    item = data["items"][0]
    assert item["line_total"] == item["qty"] * item["unit_price"]
    assert data["addons"][0]["qty"] == 2
    assert data["payments"][0]["reference"] == "ABC1"
    assert data["payments"][0]["status"] == "pending"
    assert data["payments"][0]["confirmed_by_name"] is None
    assert [h["to_status"] for h in data["history"]] == ["request"]


async def test_detail_names_who_acted(client, staff, book, seeded_session):
    code = await book()
    booking = await _booking(seeded_session, code)
    actor = await seeded_session.scalar(select(Profile).where(Profile.name == "Amina"))
    seeded_session.add_all([
        BookingStatusHistory(booking_id=booking.id, from_status="request", to_status="quoted", changed_by=actor.id),
        Payment(booking_id=booking.id, kind="deposit", method="mpesa", amount=5, reference="R1",
                status="confirmed", confirmed_by=actor.id),
    ])
    await seeded_session.commit()

    data = (await client.get(f"/admin/bookings/{booking.id}", headers=staff)).json()

    assert data["history"][-1]["changed_by_name"] == "Amina"
    assert data["payments"][0]["confirmed_by_name"] == "Amina"
    assert data["amount_paid"] == 5


async def test_detail_of_unknown_booking_is_404(client, staff):
    assert (await client.get("/admin/bookings/99999", headers=staff)).status_code == 404


# --- EFD number and notes (FR-011) ---


async def test_patch_saves_efd_and_notes(client, staff, book):
    booking_id = await _row_id(client, staff, await book())
    res = await client.patch(
        f"/admin/bookings/{booking_id}",
        json={"efd_receipt_no": " EFD-77 ", "internal_notes": "Gate code 1234"},
        headers=staff,
    )
    assert res.status_code == 200, res.text
    assert res.json()["efd_receipt_no"] == "EFD-77"
    assert res.json()["internal_notes"] == "Gate code 1234"


async def test_patch_changes_only_what_was_sent(client, staff, book):
    booking_id = await _row_id(client, staff, await book())
    url = f"/admin/bookings/{booking_id}"
    await client.patch(url, json={"efd_receipt_no": "EFD-1", "internal_notes": "Keep me"}, headers=staff)
    res = await client.patch(url, json={"efd_receipt_no": "EFD-2"}, headers=staff)
    assert res.json()["efd_receipt_no"] == "EFD-2"
    assert res.json()["internal_notes"] == "Keep me"


async def test_patch_leaves_the_customers_notes_alone(client, staff, book, seeded_session):
    code = await book(notes="Please call first")
    booking_id = await _row_id(client, staff, code)
    res = await client.patch(f"/admin/bookings/{booking_id}", json={"internal_notes": "x"}, headers=staff)
    assert res.json()["notes"] == "Please call first"


async def test_patch_rejects_an_overlong_efd_number(client, staff, book):
    booking_id = await _row_id(client, staff, await book())
    res = await client.patch(f"/admin/bookings/{booking_id}", json={"efd_receipt_no": "x" * 61}, headers=staff)
    assert res.status_code == 422


async def test_patch_of_unknown_booking_is_404(client, staff):
    assert (await client.patch("/admin/bookings/99999", json={}, headers=staff)).status_code == 404


async def test_customers_never_see_internal_notes(client, staff, book):
    code = await book()
    booking_id = await _row_id(client, staff, code)
    await client.patch(f"/admin/bookings/{booking_id}", json={"internal_notes": "SECRET-NOTE"}, headers=staff)
    res = await client.post("/public/track", json={"code": code, "phone": "0712345678"})
    assert res.status_code == 200
    assert "internal_notes" not in res.json()
    assert "SECRET-NOTE" not in res.text


# --- Role boundary (FR-010, SC-003) ---


async def test_staff_booking_responses_hold_no_cost_or_profit(client, staff, book, ids):
    code = await book(days=1, addons=[{"addon_id": ids["addons"]["cooler"], "qty": 1}])
    booking_id = await _row_id(client, staff, code)
    url = f"/admin/bookings/{booking_id}"
    responses = [
        await client.get("/admin/me", headers=staff),
        await client.get("/admin/overview", headers=staff),
        await client.get("/admin/bookings", headers=staff),
        await client.get(url, headers=staff),
        await client.patch(url, json={"internal_notes": "x"}, headers=staff),
    ]
    for res in responses:
        assert res.status_code == 200, res.text
        assert_staff_safe(res.json())


async def test_owner_sees_snapshotted_cost_and_profit(client, owner, book, seeded_session):
    code = await book()
    booking = await _booking(seeded_session, code)
    items = (await seeded_session.scalars(
        select(BookingItem).where(BookingItem.booking_id == booking.id)
    )).all()
    goods = sum(i.qty * i.unit_cost for i in items)
    assert goods > 0

    product = await seeded_session.get(Product, items[0].product_id)  # a later change must not count
    product.cost_price += 999_999
    await seeded_session.commit()

    data = (await client.get(f"/admin/bookings/{booking.id}", headers=owner)).json()

    revenue = booking.subtotal + booking.addons_total + booking.delivery_fee
    assert data["financials"] == {"goods_total": goods, "revenue": revenue, "profit": revenue - goods}


async def test_profit_leaves_out_the_refundable_empties_deposit(client, owner, book, seeded_session):
    code = await book()
    booking = await _booking(seeded_session, code)
    assert booking.empties_deposit > 0
    data = (await client.get(f"/admin/bookings/{booking.id}", headers=owner)).json()
    assert data["financials"]["revenue"] == data["total"] - booking.empties_deposit


async def test_owner_patch_also_returns_financials(client, owner, book):
    booking_id = await _row_id(client, owner, await book())
    res = await client.patch(f"/admin/bookings/{booking_id}", json={"internal_notes": "x"}, headers=owner)
    assert "financials" in res.json()
