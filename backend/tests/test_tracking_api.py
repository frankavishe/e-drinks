"""POST /public/track and POST /public/bookings/{code}/payments through the app."""

import pytest
from sqlalchemy import select

from app.models import Booking, Payment
from app.routers.public import lookup_limiter
from tests.test_booking_api import booking_body
from tests.test_public_api import assert_no_cost, ids  # noqa: F401  (ids is a fixture)

PHONE = "0712345678"


@pytest.fixture
async def code(client, ids):
    res = await client.post("/public/bookings", json=await booking_body(client, ids))
    assert res.status_code == 201, res.text
    return res.json()["code"]


def payment_body(**overrides):
    values = {
        "phone": PHONE, "kind": "deposit", "method": "mpesa", "amount": 903250, "reference": "abc123",
    }
    return {**values, **overrides}


@pytest.mark.parametrize("phone", [PHONE, "255712345678", "+255712345678"])
async def test_track_shows_the_booking(client, code, phone):
    res = await client.post("/public/track", json={"code": code, "phone": phone})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["code"] == code
    assert data["status"] == "request"
    assert data["event_type"] == "wedding"
    assert data["guests"] == 300
    assert {i["name_en"]: i["qty"] for i in data["items"]}["Coca-Cola 350ml"] == 10
    coke = next(i for i in data["items"] if i["name_en"] == "Coca-Cola 350ml")
    assert coke["line_total"] == coke["qty"] * coke["unit_price"]
    assert data["amount_paid"] == 0
    assert data["balance_due"] == data["total"]
    assert data["payments"] == []
    assert "mpesa_till" in data["payment_instructions"]
    assert_no_cost(data)


async def test_track_shows_addons_without_cost(client, ids):
    payload = await booking_body(client, ids, addons=[{"addon_id": ids["addons"]["cooler"], "qty": 6}])
    created = (await client.post("/public/bookings", json=payload)).json()
    data = (await client.post("/public/track", json={"code": created["code"], "phone": PHONE})).json()
    assert [(a["name_en"], a["qty"], a["line_total"]) for a in data["addons"]] == [
        ("Ice cooler", 6, 90000)
    ]
    assert_no_cost(data)


async def test_track_shows_saved_prices_after_a_catalog_change(client, code, seeded_session):
    from app.models import PriceTier

    for tier in (await seeded_session.scalars(select(PriceTier))).all():
        tier.unit_price = 1
    await seeded_session.commit()
    data = (await client.post("/public/track", json={"code": code, "phone": PHONE})).json()
    coke = next(i for i in data["items"] if i["name_en"] == "Coca-Cola 350ml")
    assert coke["unit_price"] == 16000


async def test_not_found_responses_are_identical(client, code):
    wrong_phone = await client.post("/public/track", json={"code": code, "phone": "0799999999"})
    bad_phone = await client.post("/public/track", json={"code": code, "phone": "nonsense"})
    unknown = await client.post("/public/track", json={"code": "ED-1999-0001", "phone": PHONE})
    assert wrong_phone.status_code == bad_phone.status_code == unknown.status_code == 404
    assert wrong_phone.json() == bad_phone.json() == unknown.json()


async def test_submitted_reference_shows_as_pending(client, code):
    res = await client.post(f"/public/bookings/{code}/payments", json=payment_body())
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "pending"
    assert res.json()["reference"] == "ABC123"
    assert_no_cost(res.json())

    data = (await client.post("/public/track", json={"code": code, "phone": PHONE})).json()
    assert [p["reference"] for p in data["payments"]] == ["ABC123"]
    assert data["amount_pending"] == 903250
    assert data["amount_paid"] == 0
    assert data["balance_due"] == data["total"]


async def test_duplicate_reference_is_409(client, code):
    await client.post(f"/public/bookings/{code}/payments", json=payment_body())
    res = await client.post(f"/public/bookings/{code}/payments", json=payment_body(reference="ABC123"))
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "duplicate_reference"


async def test_double_tap_race_is_409_and_saves_once(client, code, seeded_session, monkeypatch):
    """Simulate both requests passing the read check: the index decides."""
    await client.post(f"/public/bookings/{code}/payments", json=payment_body())
    monkeypatch.setattr("app.services.bookings._reference_in_use", _never_in_use)
    res = await client.post(f"/public/bookings/{code}/payments", json=payment_body())
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "duplicate_reference"
    assert len((await seeded_session.scalars(select(Payment))).all()) == 1


async def _never_in_use(*_args) -> bool:
    return False


async def test_closed_booking_is_409(client, code, seeded_session):
    booking = await seeded_session.scalar(select(Booking).where(Booking.code == code))
    booking.status = "cancelled"
    await seeded_session.commit()
    res = await client.post(f"/public/bookings/{code}/payments", json=payment_body())
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "booking_closed"


async def test_payment_with_wrong_phone_is_404_and_saves_nothing(client, code, seeded_session):
    res = await client.post(
        f"/public/bookings/{code}/payments", json=payment_body(phone="0799999999")
    )
    assert res.status_code == 404
    assert (await seeded_session.scalars(select(Payment))).all() == []


@pytest.mark.parametrize(
    "bad",
    [
        {"amount": 0},
        {"amount": -5},
        {"kind": "refund"},
        {"kind": "damage"},
        {"method": "cash"},
        {"reference": "   "},
        {"reference": "x" * 81},
    ],
)
async def test_invalid_payment_is_422(client, code, bad):
    res = await client.post(f"/public/bookings/{code}/payments", json=payment_body(**bad))
    assert res.status_code == 422


async def test_failed_lookups_are_rate_limited(client, code):
    wrong = {"code": code, "phone": "0799999999"}
    for _ in range(lookup_limiter.limit):
        assert (await client.post("/public/track", json=wrong)).status_code == 404
    assert (await client.post("/public/track", json=wrong)).status_code == 429
    # Blocked means blocked, even with the right details.
    right = {"code": code, "phone": PHONE}
    assert (await client.post("/public/track", json=right)).status_code == 429


async def test_failed_payment_lookups_share_the_limit(client, code):
    res = None
    for _ in range(lookup_limiter.limit + 1):
        res = await client.post(
            f"/public/bookings/{code}/payments", json=payment_body(phone="0799999999")
        )
    assert res.status_code == 429


async def test_successful_lookups_do_not_count(client, code):
    right = {"code": code, "phone": PHONE}
    for _ in range(lookup_limiter.limit + 5):
        assert (await client.post("/public/track", json=right)).status_code == 200
