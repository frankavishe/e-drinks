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


# --- Actions: payments and stages (US2) ---


DEPOSIT_BODY = {"phone": "0712345678", "kind": "deposit", "method": "mpesa", "reference": "dep1"}


@pytest.fixture
def opened(client, staff, book):
    """A booking with a pending deposit for its exact amount; returns (detail, url)."""

    async def _opened(**kwargs):
        code = await book(**kwargs)
        booking_id = await _row_id(client, staff, code)
        url = f"/admin/bookings/{booking_id}"
        detail = (await client.get(url, headers=staff)).json()
        res = await client.post(
            f"/public/bookings/{code}/payments", json={**DEPOSIT_BODY, "amount": detail["deposit_due"]}
        )
        assert res.status_code == 201, res.text
        return (await client.get(url, headers=staff)).json(), url

    return _opened


def _refused(res, code: str) -> None:
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == code


async def test_deposit_then_confirmed_end_to_end(client, staff, opened):
    detail, url = await opened()
    moves = {m["to"]: m for m in detail["allowed_moves"]}
    assert moves["confirmed"]["allowed"] is False
    assert moves["confirmed"]["reason"] == "deposit_not_paid"

    _refused(await client.post(f"{url}/stage", json={"to": "confirmed"}, headers=staff), "deposit_not_paid")

    payment_id = detail["payments"][0]["id"]
    res = await client.post(f"/admin/payments/{payment_id}/confirm", headers=staff)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["payments"][0]["status"] == "confirmed"
    assert data["payments"][0]["confirmed_by_name"] == "Amina"
    assert data["payments"][0]["confirmed_at"] is not None
    assert data["amount_paid"] == data["deposit_due"]
    assert {m["to"]: m for m in data["allowed_moves"]}["confirmed"]["allowed"] is True

    res = await client.post(f"{url}/stage", json={"to": "confirmed", "note": "Paid"}, headers=staff)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "confirmed"
    last = res.json()["history"][-1]
    assert (last["to_status"], last["changed_by_name"], last["note"]) == ("confirmed", "Amina", "Paid")


async def test_second_confirm_is_a_conflict(client, staff, opened):
    detail, _ = await opened()
    confirm = f"/admin/payments/{detail['payments'][0]['id']}/confirm"
    assert (await client.post(confirm, headers=staff)).status_code == 200
    _refused(await client.post(confirm, headers=staff), "already_confirmed")


async def test_unknown_payment_is_404(client, staff):
    assert (await client.post("/admin/payments/99999/confirm", headers=staff)).status_code == 404
    assert (await client.post("/admin/payments/99999/reject", headers=staff)).status_code == 404


async def test_reject_payment_and_refusal_when_the_stage_needs_it(client, staff, owner, opened):
    detail, url = await opened()
    payment_id = detail["payments"][0]["id"]
    await client.post(f"/admin/payments/{payment_id}/confirm", headers=staff)
    await client.post(f"{url}/stage", json={"to": "confirmed"}, headers=staff)

    reject = f"/admin/payments/{payment_id}/reject"
    _refused(await client.post(reject, headers=staff), "payment_needed_by_stage")

    res = await client.post(f"{url}/stage", json={"to": "request", "note": "Wrong reference"}, headers=owner)
    assert res.status_code == 200, res.text
    res = await client.post(reject, headers=staff)
    assert res.status_code == 200, res.text
    assert res.json()["payments"][0]["status"] == "rejected"
    assert res.json()["amount_paid"] == 0


async def test_moving_back_is_owner_only_with_a_note(client, staff, owner, book, seeded_session):
    code = await book()
    await _set_status(seeded_session, code, "confirmed")
    url = f"/admin/bookings/{await _row_id(client, staff, code)}"

    _refused(await client.post(f"{url}/stage", json={"to": "request", "note": "x"}, headers=staff), "owner_only")
    _refused(await client.post(f"{url}/stage", json={"to": "request"}, headers=owner), "note_required")

    staff_moves = (await client.get(url, headers=staff)).json()["allowed_moves"]
    owner_moves = (await client.get(url, headers=owner)).json()["allowed_moves"]
    assert {m["to"]: m["reason"] for m in staff_moves}["request"] == "owner_only"
    assert next(m for m in staff_moves if m["to"] == "request")["back"] is True
    assert {m["to"]: m["allowed"] for m in owner_moves}["request"] is True


async def test_unknown_stage_is_invalid_input(client, staff, book):
    url = f"/admin/bookings/{await _row_id(client, staff, await book())}"
    assert (await client.post(f"{url}/stage", json={"to": "nonsense"}, headers=staff)).status_code == 422


async def test_stage_cannot_be_used_to_cancel(client, staff, book):
    url = f"/admin/bookings/{await _row_id(client, staff, await book())}"
    _refused(await client.post(f"{url}/stage", json={"to": "cancelled"}, headers=staff), "invalid_move")


async def test_actions_on_an_unknown_booking_are_404(client, staff):
    url = "/admin/bookings/99999"
    responses = [
        await client.post(f"{url}/stage", json={"to": "quoted"}, headers=staff),
        await client.get(f"{url}/cancel-preview", headers=staff),
        await client.post(f"{url}/cancel", json={}, headers=staff),
        await client.post(f"{url}/date-change", json={"new_date": "2030-01-01"}, headers=staff),
        await client.post(f"{url}/rush", json={"approve": True}, headers=staff),
        await client.post(f"{url}/delivery-fee", json={"fee": 1}, headers=staff),
        await client.post(f"{url}/refunds", json={"amount": 1, "method": "cash"}, headers=staff),
    ]
    for res in responses:
        assert res.status_code == 404, res.request.url


# --- Cancel and refund over HTTP ---


async def _confirmed_deposit(client, staff, opened, **kwargs):
    detail, url = await opened(**kwargs)
    res = await client.post(f"/admin/payments/{detail['payments'][0]['id']}/confirm", headers=staff)
    assert res.status_code == 200, res.text
    return res.json(), url


async def test_cancel_ten_days_out_shows_half_the_deposit(client, staff, opened):
    detail, url = await _confirmed_deposit(client, staff, opened, days=10)

    preview = await client.get(f"{url}/cancel-preview", headers=staff)
    assert preview.status_code == 200, preview.text
    half = detail["deposit_due"] // 2
    assert preview.json() == {"days_ahead": 10, "paid": detail["deposit_due"], "refund_due": half}

    res = await client.post(f"{url}/cancel", json={"note": "Changed plans"}, headers=staff)
    assert res.status_code == 200, res.text
    data = res.json()
    assert (data["status"], data["refund_due"], data["refunded"]) == ("cancelled", half, 0)
    assert data["allowed_moves"] == []


async def test_cancel_is_refused_with_a_payment_pending(client, staff, opened):
    _, url = await opened()
    _refused(await client.post(f"{url}/cancel", json={}, headers=staff), "pending_payments")


async def test_cancel_preview_of_a_finished_booking_is_refused(client, staff, opened):
    _, url = await _confirmed_deposit(client, staff, opened)
    await client.post(f"{url}/cancel", json={}, headers=staff)
    _refused(await client.get(f"{url}/cancel-preview", headers=staff), "booking_finished")


async def test_refund_records_up_to_what_is_due(client, staff, opened):
    detail, url = await _confirmed_deposit(client, staff, opened, days=10)
    half = detail["deposit_due"] // 2
    await client.post(f"{url}/cancel", json={}, headers=staff)
    refunds = f"{url}/refunds"

    res = await client.post(refunds, json={"amount": half, "method": "mpesa", "reference": "rf1"}, headers=staff)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["refunded"] == half
    refund = data["payments"][-1]
    assert (refund["kind"], refund["status"], refund["reference"]) == ("refund", "confirmed", "RF1")
    assert refund["confirmed_by_name"] == "Amina"
    assert data["amount_paid"] == detail["deposit_due"]  # refunds aren't payments towards the order

    _refused(await client.post(refunds, json={"amount": 1, "method": "cash"}, headers=staff), "refund_exceeds_due")


@pytest.mark.parametrize(
    "bad", [{"amount": 0, "method": "cash"}, {"amount": 1, "method": "cheque"}, {"amount": 1}]
)
async def test_refund_input_is_validated(client, staff, opened, bad):
    _, url = await _confirmed_deposit(client, staff, opened)
    await client.post(f"{url}/cancel", json={}, headers=staff)
    assert (await client.post(f"{url}/refunds", json=bad, headers=staff)).status_code == 422


# --- Date change, rush and delivery fee over HTTP ---


async def test_date_change_then_exception(client, staff, owner, book):
    url = f"/admin/bookings/{await _row_id(client, staff, await book())}/date-change"
    first = (today_eat() + timedelta(days=35)).isoformat()
    second = (today_eat() + timedelta(days=40)).isoformat()

    res = await client.post(url, json={"new_date": first}, headers=staff)
    assert res.status_code == 200, res.text
    assert (res.json()["event_date"], res.json()["date_changes_used"]) == (first, 1)

    _refused(await client.post(url, json={"new_date": second}, headers=staff), "date_change_used")
    exception = {"new_date": second, "exception": True, "note": "Bereavement"}
    _refused(await client.post(url, json=exception, headers=staff), "owner_only")
    _refused(await client.post(url, json={**exception, "note": ""}, headers=owner), "note_required")

    res = await client.post(url, json=exception, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["event_date"] == second


async def test_rush_approve_and_decline(client, staff, book):
    url = f"/admin/bookings/{await _row_id(client, staff, await book(days=1))}/rush"
    res = await client.post(url, json={"approve": True}, headers=staff)
    assert res.status_code == 200, res.text
    assert res.json()["rush_approved"] is True

    other_code = await book(days=2, phone="0755000111")
    other = f"/admin/bookings/{await _row_id(client, staff, other_code)}/rush"
    res = await client.post(other, json={"approve": False, "note": "No stock"}, headers=staff)
    assert res.status_code == 200, res.text
    assert (res.json()["status"], res.json()["refund_due"]) == ("cancelled", 0)


async def test_rush_on_a_normal_booking_is_refused(client, staff, book):
    url = f"/admin/bookings/{await _row_id(client, staff, await book())}/rush"
    _refused(await client.post(url, json={"approve": True}, headers=staff), "not_rush")


async def test_delivery_fee_updates_the_totals(client, staff, book):
    code = await book(area_id=None, custom_area="Bagamoyo")
    url = f"/admin/bookings/{await _row_id(client, staff, code)}"
    before = (await client.get(url, headers=staff)).json()
    assert before["provisional"] is True
    assert {m["to"]: m["reason"] for m in before["allowed_moves"]}["quoted"] == "provisional"

    res = await client.post(f"{url}/delivery-fee", json={"fee": 50_000}, headers=staff)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["provisional"] is False
    assert data["delivery_fee"] == 50_000
    assert data["total"] == before["total"] + 50_000
    assert data["deposit_due"] == -(-data["total"] // 2)
    tracked = (await client.post("/public/track", json={"code": code, "phone": "0712345678"})).json()
    assert (tracked["provisional"], tracked["total"]) == (False, data["total"])


async def test_negative_delivery_fee_is_invalid(client, staff, book):
    code = await book(area_id=None, custom_area="Bagamoyo")
    url = f"/admin/bookings/{await _row_id(client, staff, code)}/delivery-fee"
    assert (await client.post(url, json={"fee": -1}, headers=staff)).status_code == 422


# --- Role boundary across every action (SC-003) ---


async def test_action_responses_keep_cost_and_profit_from_staff(client, staff, owner, opened, book):
    detail, url = await opened(days=20)
    payment = f"/admin/payments/{detail['payments'][0]['id']}"
    rush_code = await book(days=1, phone="0755000111")
    rush_url = f"/admin/bookings/{await _row_id(client, staff, rush_code)}"
    fee_code = await book(phone="0755000222", area_id=None, custom_area="Bagamoyo")
    fee_url = f"/admin/bookings/{await _row_id(client, staff, fee_code)}"
    new_date = (today_eat() + timedelta(days=45)).isoformat()

    responses = [
        await client.post(f"{payment}/confirm", headers=staff),
        await client.post(f"{url}/stage", json={"to": "confirmed"}, headers=staff),
        await client.post(f"{url}/date-change", json={"new_date": new_date}, headers=staff),
        await client.get(f"{url}/cancel-preview", headers=staff),
        await client.post(f"{url}/cancel", json={}, headers=staff),
        await client.post(f"{url}/refunds", json={"amount": 1, "method": "cash"}, headers=staff),
        await client.post(f"{rush_url}/rush", json={"approve": True}, headers=staff),
        await client.post(f"{fee_url}/delivery-fee", json={"fee": 1000}, headers=staff),
    ]
    for res in responses:
        assert res.status_code in (200, 201), res.text
        assert_staff_safe(res.json())

    res = await client.post(f"{rush_url}/rush", json={"approve": True}, headers=owner)
    assert "financials" in res.json()
