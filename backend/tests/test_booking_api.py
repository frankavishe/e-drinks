"""POST /public/bookings and GET /public/settings through the app."""

import pytest
from sqlalchemy import func, select

from app.models import Booking, Customer
from app.routers.public import booking_limiter
from tests.test_public_api import FAR_AHEAD, assert_no_cost, body, ids  # noqa: F401  (ids is a fixture)


async def booking_body(client, ids, days=FAR_AHEAD, **overrides):
    values = {
        "event_type": "wedding",
        "start_time": "16:00:00",
        "name": "Asha",
        "phone": "0712345678",
        "lang": "sw",
        "accept_policy": True,
        "age_confirmed": True,
    }
    quote_fields = {k: v for k, v in overrides.items() if k in QUOTE_FIELDS}
    quote_input = body(ids, days=days, **quote_fields)
    res = await client.post("/public/quote", json=quote_input)
    assert res.status_code == 200, res.text
    other = {k: v for k, v in overrides.items() if k not in QUOTE_FIELDS}
    return {**quote_input, **values, "expected_total": res.json()["total"], **other}


QUOTE_FIELDS = {"addons", "items", "package_id", "area_id", "custom_area"}


async def saved(seeded_session) -> int:
    return await seeded_session.scalar(select(func.count()).select_from(Booking))


async def test_public_settings(client):
    res = await client.get("/public/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["whatsapp_number"] == "255700000000"
    assert data["policy_text_sw"].startswith("Amana")
    assert set(data["payment_instructions"]) == {
        "mpesa_till", "tigopesa_lipa", "airtel_lipa", "bank_details",
    }
    assert "min_order" not in data
    assert "notification_email" not in data


async def test_create_booking(client, ids):
    res = await client.post("/public/bookings", json=await booking_body(client, ids))
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["code"].startswith("ED-")
    assert data["status"] == "request"
    assert data["is_rush"] is False
    assert data["provisional"] is False
    assert data["deposit_due"] == -(-data["total"] // 2)
    assert data["whatsapp_number"] == "255700000000"
    assert "mpesa_till" in data["payment_instructions"]
    assert_no_cost(data)


async def test_phone_is_stored_normalised(client, ids, seeded_session):
    await client.post(
        "/public/bookings", json=await booking_body(client, ids, phone="+255 712-345-678")
    )
    booking = await seeded_session.scalar(select(Booking))
    customer = await seeded_session.get(Customer, booking.customer_id)
    assert customer.phone == "255712345678"


@pytest.mark.parametrize(
    "bad",
    [
        {"accept_policy": False},
        {"age_confirmed": False},
        {"phone": "12345"},
        {"name": "   "},
        {"email": "not-an-email"},
        {"event_type": "party"},
        {"lang": "fr"},
        {"notes": "x" * 1001},
    ],
)
async def test_invalid_input_is_422(client, ids, seeded_session, bad):
    res = await client.post("/public/bookings", json=await booking_body(client, ids, **bad))
    assert res.status_code == 422
    assert await saved(seeded_session) == 0


async def test_missing_confirmations_are_422(client, ids, seeded_session):
    payload = await booking_body(client, ids)
    del payload["accept_policy"]
    res = await client.post("/public/bookings", json=payload)
    assert res.status_code == 422


async def test_venue_in_another_area_is_422(client, ids, seeded_session):
    areas = (await client.get("/public/areas")).json()
    other = next(v for v in areas["venues"] if v["area_id"] != ids["areas"]["Masaki"])
    res = await client.post(
        "/public/bookings", json=await booking_body(client, ids, venue_id=other["id"])
    )
    assert res.status_code == 422
    assert await saved(seeded_session) == 0


async def test_changed_total_is_409_with_the_new_quote(client, ids, seeded_session):
    payload = await booking_body(client, ids)
    actual = payload["expected_total"]
    res = await client.post("/public/bookings", json={**payload, "expected_total": actual + 1})
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["code"] == "quote_changed"
    assert detail["quote"]["total"] == actual
    assert_no_cost(detail)
    assert await saved(seeded_session) == 0


async def test_unavailable_addon_is_409(client, ids, seeded_session):
    payload = await booking_body(
        client, ids, addons=[{"addon_id": ids["addons"]["cooler"], "qty": 21}]
    )
    res = await client.post("/public/bookings", json=payload)
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["code"] == "addons_unavailable"
    assert detail["quote"]["flags"]["addons_unavailable"] == [ids["addons"]["cooler"]]
    assert await saved(seeded_session) == 0


async def test_below_minimum_is_409(client, ids, seeded_session):
    payload = await booking_body(
        client,
        ids,
        package_id=None,
        items=[{"product_id": ids["products"]["Coca-Cola 350ml"], "packs": 1}],
    )
    res = await client.post("/public/bookings", json=payload)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "below_minimum"
    assert await saved(seeded_session) == 0


async def test_creation_is_rate_limited(client, ids, seeded_session):
    payload = await booking_body(client, ids)
    for _ in range(booking_limiter.limit):
        assert (await client.post("/public/bookings", json=payload)).status_code == 201
    assert (await client.post("/public/bookings", json=payload)).status_code == 429
    assert await saved(seeded_session) == booking_limiter.limit


async def test_refused_bookings_do_not_use_up_the_limit(client, ids, seeded_session):
    payload = await booking_body(client, ids)
    wrong = {**payload, "expected_total": payload["expected_total"] + 1}
    for _ in range(booking_limiter.limit):
        assert (await client.post("/public/bookings", json=wrong)).status_code == 409
    assert (await client.post("/public/bookings", json=payload)).status_code == 201
