"""Public endpoints on the seeded SQLite catalog; expected figures are hand-calculated."""

from datetime import date, timedelta

import pytest

FAR_AHEAD = 30


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def assert_no_cost(payload):
    assert not [k for k in walk_keys(payload) if "cost" in k.lower() or "margin" in k.lower()]


@pytest.fixture
async def ids(client):
    """Look ids up by name through the public endpoints, as the wizard would."""
    catalog = (await client.get("/public/catalog")).json()
    packages = (await client.get("/public/packages")).json()
    addons = (await client.get("/public/addons")).json()
    areas = (await client.get("/public/areas")).json()
    return {
        "products": {p["name_en"]: p["id"] for p in catalog},
        "packages": {p["slug"]: p["id"] for p in packages},
        "addons": {a["kind"]: a["id"] for a in addons},
        "areas": {a["name"]: a["id"] for z in areas["zones"] for a in z["areas"]},
    }


def body(ids, days=FAR_AHEAD, **overrides):
    event = date.today() + timedelta(days=days)
    values = {
        "event_date": event.isoformat(),
        "hours": 5,
        "guests": 300,
        "setup_at": f"{event}T15:00:00+03:00",
        "collect_at": f"{event + timedelta(days=1)}T09:00:00+03:00",
        "package_id": ids["packages"]["silver"],
        "area_id": ids["areas"]["Masaki"],
    }
    return {**values, **overrides}


async def test_catalog(client):
    res = await client.get("/public/catalog")
    assert res.status_code == 200
    products = res.json()
    assert len(products) == 14
    coke = next(p for p in products if p["name_en"] == "Coca-Cola 350ml")
    assert coke["tiers"] == [
        {"min_qty": 1, "unit_price": 16500},
        {"min_qty": 10, "unit_price": 16000},
        {"min_qty": 50, "unit_price": 15500},
    ]
    assert coke["returnable_glass"] is True
    assert coke["empties_deposit_per_unit"] == 6000
    assert_no_cost(products)


async def test_packages_in_sort_order(client):
    res = await client.get("/public/packages")
    assert res.status_code == 200
    packages = res.json()
    assert [p["slug"] for p in packages] == ["bronze", "silver", "gold", "premium"]
    assert packages[1]["base_hours"] == 5
    assert {r["qty_per_guest"] for r in packages[1]["rules"]} == {0.25, 0.5, 0.75, 1.0}
    assert_no_cost(packages)


async def test_addons_hide_capacity(client):
    res = await client.get("/public/addons")
    assert res.status_code == 200
    addons = res.json()
    assert {a["kind"] for a in addons} == {"cooler", "ice", "server", "bartender"}
    assert set(addons[0]) == {"id", "name_sw", "name_en", "kind", "price"}
    assert_no_cost(addons)


async def test_areas_group_under_zones(client):
    res = await client.get("/public/areas")
    assert res.status_code == 200
    data = res.json()
    assert len(data["zones"]) == 3
    zone_a = next(z for z in data["zones"] if z["delivery_fee"] == 25000)
    assert "Masaki" in [a["name"] for a in zone_a["areas"]]
    assert [v["name"] for v in data["venues"]] == [
        "Ukumbi wa Mfano Masaki",
        "Bustani ya Mfano Mbezi Beach",
    ]
    assert_no_cost(data)


async def test_inactive_rows_are_hidden(client, seeded_session, ids):
    from app.models import Product

    product = await seeded_session.get(Product, ids["products"]["Whisky 750ml"])
    product.active = False
    await seeded_session.commit()
    names = [p["name_en"] for p in (await client.get("/public/catalog")).json()]
    assert "Whisky 750ml" not in names


async def test_silver_quote_matches_hand_calculation(client, ids):
    res = await client.post("/public/quote", json=body(ids))
    assert res.status_code == 200
    q = res.json()
    lines = {line["name_en"]: line for line in q["lines"]}
    assert {name: (line["packs"], line["unit_price"], line["empties_deposit"]) for name, line in lines.items()} == {
        "Coca-Cola 350ml": (10, 16000, 60000),
        "Fanta Orange 350ml": (7, 16500, 42000),
        "Sprite 350ml": (4, 16500, 24000),
        "Water 500ml": (25, 6000, 0),
        "Kilimanjaro Lager 500ml": (12, 48500, 120000),
        "Safari Lager 500ml": (6, 52000, 60000),
    }
    assert q["subtotal"] == 1385500
    assert q["delivery_fee"] == 25000
    assert q["empties_deposit"] == 306000
    assert q["total"] == 1716500
    assert q["deposit_due"] == 858250
    event = date.today() + timedelta(days=FAR_AHEAD)
    assert q["balance_due_date"] == (event - timedelta(days=3)).isoformat()
    assert q["flags"]["min_order"] == 300000
    assert_no_cost(q)


async def test_quote_needs_no_login(client, ids):
    res = await client.post("/public/quote", json=body(ids))
    assert "authorization" not in {k.lower() for k in res.request.headers}
    assert res.status_code == 200


async def test_unknown_package_is_422_naming_it(client, ids):
    res = await client.post("/public/quote", json=body(ids, package_id=99999))
    assert res.status_code == 422
    assert "99999" in res.json()["detail"]


# --- T017: custom orders and validation ------------------------------------------------------


def custom_body(ids, **overrides):
    coke = ids["products"]["Coca-Cola 350ml"]
    beer = ids["products"]["Kilimanjaro Lager 500ml"]
    values = {
        "package_id": None,
        "items": [{"product_id": coke, "packs": 12}, {"product_id": beer, "packs": 3}],
    }
    return body(ids, **{**values, **overrides})


async def test_custom_quote_matches_hand_calculation(client, ids):
    res = await client.post("/public/quote", json=custom_body(ids))
    assert res.status_code == 200
    q = res.json()
    assert q["subtotal"] == 342000  # 12 x 16,000 + 3 x 50,000
    assert q["empties_deposit"] == 102000  # 12 x 6,000 + 3 x 10,000
    assert q["total"] == 469000  # + 25,000 delivery
    assert q["deposit_due"] == 234500
    assert q["flags"]["below_minimum"] is False
    assert {line["source"] for line in q["lines"]} == {"custom"}


async def test_override_through_the_api(client, ids):
    coke = ids["products"]["Coca-Cola 350ml"]
    res = await client.post("/public/quote", json=body(ids, overrides={str(coke): 14}))
    assert res.status_code == 200
    line = next(line for line in res.json()["lines"] if line["product_id"] == coke)
    assert (line["packs"], line["line_total"]) == (14, 224000)


async def test_below_minimum_is_a_flag_not_an_error(client, ids):
    water = ids["products"]["Water 500ml"]
    res = await client.post(
        "/public/quote", json=custom_body(ids, items=[{"product_id": water, "packs": 1}])
    )
    assert res.status_code == 200
    assert res.json()["flags"]["below_minimum"] is True


async def test_inactive_product_in_a_custom_order_is_422(client, seeded_session, ids):
    from app.models import Product

    water = ids["products"]["Water 500ml"]
    (await seeded_session.get(Product, water)).active = False
    await seeded_session.commit()
    res = await client.post(
        "/public/quote", json=custom_body(ids, items=[{"product_id": water, "packs": 1}])
    )
    assert res.status_code == 422
    assert str(water) in res.json()["detail"]


async def test_inactive_product_is_left_out_of_a_package_quote(client, seeded_session, ids):
    from app.models import Product

    water = ids["products"]["Water 500ml"]
    (await seeded_session.get(Product, water)).active = False
    await seeded_session.commit()
    res = await client.post("/public/quote", json=body(ids))
    assert res.status_code == 200
    assert water not in [line["product_id"] for line in res.json()["lines"]]


@pytest.mark.parametrize(
    "change",
    [
        {"guests": 0},
        {"guests": -5},
        {"hours": 0},
        {"hours": 25},
        {"package_id": None},  # neither package nor items
        {"items": [{"product_id": 1, "packs": 1}]},  # both package and items
        {"package_id": None, "items": []},
        {"package_id": None, "items": [{"product_id": 1, "packs": 0}]},
        {"package_id": None, "items": [{"product_id": 99999, "packs": 1}]},
        {"package_id": None, "items": [{"product_id": 1, "packs": 1}, {"product_id": 1, "packs": 2}]},
        {"overrides": {"1": -1}},
        {"overrides": {"99999": 1}},
        {"package_id": None, "items": [{"product_id": 1, "packs": 1}], "overrides": {"1": 2}},
        {"addons": [{"addon_id": 1, "qty": 0}]},
        {"addons": [{"addon_id": 1, "qty": 11}, {"addon_id": 1, "qty": 11}]},  # would dodge capacity
        {"setup_at": "2030-01-01T15:00:00"},  # no timezone
        {"collect_at": "2030-01-01T15:00:00"},  # no timezone
    ],
)
async def test_invalid_quote_is_422(client, ids, change):
    assert (await client.post("/public/quote", json=body(ids, **change))).status_code == 422


@pytest.mark.parametrize("hours_later", [0, -1])
async def test_collection_must_follow_setup(client, ids, hours_later):
    res = await client.post(
        "/public/quote",
        json=body(
            ids,
            setup_at="2030-01-01T15:00:00+03:00",
            collect_at=f"2030-01-01T{15 + hours_later}:00:00+03:00",
        ),
    )
    assert res.status_code == 422
