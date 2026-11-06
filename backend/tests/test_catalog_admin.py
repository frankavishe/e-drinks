"""Catalog, zone, venue and settings management, through the app with real signed tokens."""

from datetime import date, datetime, time, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import (
    Addon,
    Area,
    Booking,
    BookingAddon,
    BookingItem,
    Customer,
    Package,
    PackageRule,
    PriceTier,
    Product,
    PurchaseNeed,
    Setting,
    StockLevel,
    StockMovement,
    Venue,
    Zone,
)
from tests.test_admin_api import assert_staff_safe, book, jwt_secret, owner, planner, staff  # noqa: F401
from tests.test_public_api import body, ids  # noqa: F401

NEW_PRODUCT = {
    "name_sw": "Soda Mpya",
    "name_en": "New Soda",
    "category": "soft",
    "unit": "kreti ya 24",
    "units_per_pack": 24,
    "is_alcohol": False,
    "cost_price": 9000,
    "returnable_glass": False,
    "empties_deposit_per_unit": 0,
    "tiers": [{"min_qty": 1, "unit_price": 12000}],
}

NEW_PACKAGE = {
    "slug": "mpya",
    "name_sw": "Mpya",
    "name_en": "New",
    "base_hours": 5,
    "rules": [],  # filled in by the test: it needs a real product id
}

NEW_ADDON = {
    "name_sw": "Meza",
    "name_en": "Table",
    "kind": "cooler",
    "price": 5000,
    "owned_capacity": 4,
    "replacement_cost": 70000,
}


def refused(res, code):
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == code


async def first_id(session, model):
    return await session.scalar(select(model.id).order_by(model.id).limit(1))


@pytest_asyncio.fixture
async def unused_product(client, owner):
    res = await client.post("/admin/products", json=NEW_PRODUCT, headers=owner)
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest_asyncio.fixture
async def booking_row(seeded_session):
    customer = Customer(name="Asha", phone="255711111111")
    seeded_session.add(customer)
    await seeded_session.flush()
    booking = Booking(
        code="ED-CAT-0001",
        customer_id=customer.id,
        event_type="wedding",
        event_date=date(2030, 1, 12),
        start_time=time(16),
        hours=5,
        guests=100,
        setup_at=datetime(2030, 1, 12, 6, tzinfo=timezone.utc),
        collect_at=datetime(2030, 1, 12, 18, tzinfo=timezone.utc),
    )
    seeded_session.add(booking)
    await seeded_session.commit()
    return booking


# Who may do what


WRITES = [
    ("post", "/admin/products"),
    ("patch", "/admin/products/1"),
    ("delete", "/admin/products/1"),
    ("put", "/admin/products/1/tiers"),
    ("post", "/admin/packages"),
    ("patch", "/admin/packages/1"),
    ("delete", "/admin/packages/1"),
    ("put", "/admin/packages/1/rules"),
    ("post", "/admin/addons"),
    ("patch", "/admin/addons/1"),
    ("delete", "/admin/addons/1"),
    ("post", "/admin/zones"),
    ("patch", "/admin/zones/1"),
    ("delete", "/admin/zones/1"),
    ("post", "/admin/areas"),
    ("patch", "/admin/areas/1"),
    ("delete", "/admin/areas/1"),
    ("post", "/admin/venues"),
    ("patch", "/admin/venues/1"),
    ("delete", "/admin/venues/1"),
    ("put", "/admin/settings"),
]

READS = ["products", "packages", "addons", "zones", "venues", "settings"]


@pytest.mark.parametrize("method,path", WRITES)
async def test_staff_are_refused_every_write(client, staff, method, path):
    kwargs = {} if method == "delete" else {"json": {}}
    res = await client.request(method, path, headers=staff, **kwargs)
    assert res.status_code == 403, res.text


@pytest.mark.parametrize("name", READS)
async def test_staff_read_without_cost_fields(client, staff, name):
    res = await client.get(f"/admin/{name}", headers=staff)
    assert res.status_code == 200, res.text
    assert res.json()
    assert_staff_safe(res.json())


@pytest.mark.parametrize("name", READS)
async def test_planners_and_strangers_get_nothing(client, planner, name):
    assert (await client.get(f"/admin/{name}", headers=planner)).status_code == 403
    assert (await client.get(f"/admin/{name}")).status_code == 401


async def test_owner_sees_cost_fields(client, owner):
    products = (await client.get("/admin/products", headers=owner)).json()
    addons = (await client.get("/admin/addons", headers=owner)).json()
    coke = next(p for p in products if p["name_en"] == "Coca-Cola 350ml")
    cooler = next(a for a in addons if a["kind"] == "cooler")
    assert coke["cost_price"] == 13000
    assert cooler["replacement_cost"] == 150000


async def test_staff_see_inactive_products(client, seeded_session, staff):
    product_id = await first_id(seeded_session, Product)
    (await seeded_session.get(Product, product_id)).active = False
    await seeded_session.commit()
    rows = (await client.get("/admin/products", headers=staff)).json()
    assert next(p for p in rows if p["id"] == product_id)["active"] is False


# Tiers


@pytest.mark.parametrize(
    "tiers",
    [
        [],
        [{"min_qty": 10, "unit_price": 100}],
        [{"min_qty": 1, "unit_price": 100}, {"min_qty": 1, "unit_price": 90}],
        [{"min_qty": 1, "unit_price": -1}],
    ],
    ids=["empty", "lowest_not_one", "repeated", "negative_price"],
)
async def test_bad_tiers_are_refused_and_change_nothing(client, seeded_session, owner, tiers):
    product_id = await first_id(seeded_session, Product)
    before = (await client.get("/admin/products", headers=owner)).json()
    refused(await client.put(f"/admin/products/{product_id}/tiers", json=tiers, headers=owner), "invalid_tiers")
    refused(await client.post("/admin/products", json={**NEW_PRODUCT, "tiers": tiers}, headers=owner), "invalid_tiers")
    assert (await client.get("/admin/products", headers=owner)).json() == before


async def test_tiers_replace_the_whole_set_in_order(client, seeded_session, owner):
    product_id = await first_id(seeded_session, Product)
    res = await client.put(
        f"/admin/products/{product_id}/tiers",
        json=[{"min_qty": 20, "unit_price": 100}, {"min_qty": 1, "unit_price": 150}],
        headers=owner,
    )
    assert res.status_code == 200, res.text
    assert res.json()["tiers"] == [{"min_qty": 1, "unit_price": 150}, {"min_qty": 20, "unit_price": 100}]
    rows = await seeded_session.scalars(select(PriceTier).where(PriceTier.product_id == product_id))
    assert len(rows.all()) == 2


# Products


async def test_new_product_is_public_with_a_stock_row(client, seeded_session, unused_product):
    assert await seeded_session.get(StockLevel, unused_product) is not None
    catalog = (await client.get("/public/catalog")).json()
    assert "New Soda" in [p["name_en"] for p in catalog]


async def test_new_product_needs_tiers(client, owner):
    payload = {k: v for k, v in NEW_PRODUCT.items() if k != "tiers"}
    assert (await client.post("/admin/products", json=payload, headers=owner)).status_code == 422


async def test_patch_changes_only_what_was_sent(client, unused_product, owner):
    res = await client.patch(f"/admin/products/{unused_product}", json={"cost_price": 9500}, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["cost_price"] == 9500
    assert res.json()["name_en"] == "New Soda"


async def test_null_clears_only_nullable_fields(client, unused_product, owner):
    url = f"/admin/products/{unused_product}"
    await client.patch(url, json={"image_url": "https://example.test/a.png"}, headers=owner)
    res = await client.patch(url, json={"image_url": None, "name_en": None}, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["image_url"] is None
    assert res.json()["name_en"] == "New Soda"


@pytest.mark.parametrize(
    "patch",
    [{"units_per_pack": 0}, {"cost_price": -1}, {"image_url": "javascript:alert(1)"}, {"name_en": ""}],
    ids=["no_units", "negative_cost", "script_url", "blank_name"],
)
async def test_bad_product_input_is_rejected(client, unused_product, owner, patch):
    assert (await client.patch(f"/admin/products/{unused_product}", json=patch, headers=owner)).status_code == 422


async def test_unknown_records_are_404(client, owner):
    for method, path in WRITES:
        if not path.endswith("/1") or method != "delete":
            continue
        res = await client.delete(path.replace("/1", "/99999"), headers=owner)
        assert res.status_code == 404, path


async def test_unused_product_can_be_deleted_with_its_stock_row(client, seeded_session, unused_product, owner):
    res = await client.delete(f"/admin/products/{unused_product}", headers=owner)
    assert res.status_code == 204, res.text
    assert await seeded_session.get(Product, unused_product) is None
    assert await seeded_session.get(StockLevel, unused_product) is None


async def test_product_in_a_package_is_in_use(client, seeded_session, owner):
    product_id = await seeded_session.scalar(select(PackageRule.product_id).limit(1))
    refused(await client.delete(f"/admin/products/{product_id}", headers=owner), "in_use")


async def test_product_on_a_booking_is_in_use(client, seeded_session, booking_row, unused_product, owner):
    seeded_session.add(BookingItem(booking_id=booking_row.id, product_id=unused_product, qty=1, unit_price=1))
    await seeded_session.commit()
    refused(await client.delete(f"/admin/products/{unused_product}", headers=owner), "in_use")


async def test_product_with_stock_history_is_in_use(client, seeded_session, unused_product, owner):
    seeded_session.add(StockMovement(product_id=unused_product, qty=1, type="purchase"))
    await seeded_session.commit()
    refused(await client.delete(f"/admin/products/{unused_product}", headers=owner), "in_use")


@pytest.mark.parametrize("field", ["on_hand", "reserved"])
async def test_product_with_stock_is_in_use(client, seeded_session, unused_product, owner, field):
    setattr(await seeded_session.get(StockLevel, unused_product), field, 3)
    await seeded_session.commit()
    refused(await client.delete(f"/admin/products/{unused_product}", headers=owner), "in_use")
    assert await seeded_session.get(Product, unused_product) is not None


async def test_product_on_the_purchase_list_is_in_use(client, seeded_session, booking_row, unused_product, owner):
    seeded_session.add(
        PurchaseNeed(product_id=unused_product, booking_id=booking_row.id, qty=1, needed_by=date(2030, 1, 10))
    )
    await seeded_session.commit()
    refused(await client.delete(f"/admin/products/{unused_product}", headers=owner), "in_use")


# Packages


async def test_package_rules_round_trip_exactly(client, unused_product, owner):
    rules = [{"product_id": unused_product, "qty_per_guest": "0.125", "per_hour": True}]
    res = await client.post("/admin/packages", json={**NEW_PACKAGE, "rules": rules}, headers=owner)
    assert res.status_code == 201, res.text
    assert res.json()["rules"] == rules
    assert res.json()["active"] is True


async def test_rules_replace_the_whole_set(client, seeded_session, unused_product, owner):
    package_id = await first_id(seeded_session, Package)
    rules = [{"product_id": unused_product, "qty_per_guest": "1.000", "per_hour": False}]
    res = await client.put(f"/admin/packages/{package_id}/rules", json=rules, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["rules"] == rules


@pytest.mark.parametrize("kind", ["empty", "repeated", "unknown"])
async def test_bad_rules_are_refused(client, seeded_session, unused_product, owner, kind):
    rule = {"product_id": unused_product, "qty_per_guest": "1.000", "per_hour": False}
    rules = {"empty": [], "repeated": [rule, rule], "unknown": [{**rule, "product_id": 99999}]}[kind]
    package_id = await first_id(seeded_session, Package)
    refused(await client.put(f"/admin/packages/{package_id}/rules", json=rules, headers=owner), "invalid_rules")
    refused(await client.post("/admin/packages", json={**NEW_PACKAGE, "rules": rules}, headers=owner), "invalid_rules")


@pytest.mark.parametrize("qty", ["0", "-1", "0.1234"])
async def test_rule_quantity_must_be_positive_with_three_places(client, seeded_session, unused_product, owner, qty):
    package_id = await first_id(seeded_session, Package)
    rules = [{"product_id": unused_product, "qty_per_guest": qty, "per_hour": False}]
    assert (await client.put(f"/admin/packages/{package_id}/rules", json=rules, headers=owner)).status_code == 422


async def test_repeated_slug_is_refused(client, seeded_session, unused_product, owner):
    rules = [{"product_id": unused_product, "qty_per_guest": "1.000", "per_hour": False}]
    refused(
        await client.post("/admin/packages", json={**NEW_PACKAGE, "slug": "gold", "rules": rules}, headers=owner),
        "already_exists",
    )
    bronze = await seeded_session.scalar(select(Package.id).where(Package.slug == "bronze"))
    refused(await client.patch(f"/admin/packages/{bronze}", json={"slug": "gold"}, headers=owner), "already_exists")


async def test_a_package_may_keep_its_own_slug(client, seeded_session, owner):
    bronze = await seeded_session.scalar(select(Package.id).where(Package.slug == "bronze"))
    res = await client.patch(f"/admin/packages/{bronze}", json={"slug": "bronze", "name_en": "B"}, headers=owner)
    assert res.status_code == 200, res.text


async def test_package_on_a_booking_is_in_use(client, seeded_session, booking_row, owner):
    package_id = await first_id(seeded_session, Package)
    booking_row.package_id = package_id
    await seeded_session.commit()
    refused(await client.delete(f"/admin/packages/{package_id}", headers=owner), "in_use")


async def test_unused_package_can_be_deleted_with_its_rules(client, seeded_session, owner):
    package_id = await first_id(seeded_session, Package)
    assert (await client.delete(f"/admin/packages/{package_id}", headers=owner)).status_code == 204
    left = await seeded_session.scalars(select(PackageRule).where(PackageRule.package_id == package_id))
    assert left.all() == []


# Add-ons


async def test_addon_create_edit_and_unlimited(client, owner):
    res = await client.post("/admin/addons", json=NEW_ADDON, headers=owner)
    assert res.status_code == 201, res.text
    res = await client.patch(f"/admin/addons/{res.json()['id']}", json={"owned_capacity": None}, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["owned_capacity"] is None


async def test_addon_kind_must_be_known(client, owner):
    res = await client.post("/admin/addons", json={**NEW_ADDON, "kind": "tent"}, headers=owner)
    assert res.status_code == 422


async def test_addon_on_a_booking_is_in_use(client, seeded_session, booking_row, owner):
    addon_id = await first_id(seeded_session, Addon)
    seeded_session.add(BookingAddon(booking_id=booking_row.id, addon_id=addon_id, qty=1, unit_price=1))
    await seeded_session.commit()
    refused(await client.delete(f"/admin/addons/{addon_id}", headers=owner), "in_use")


async def test_unused_addon_can_be_deleted(client, seeded_session, owner):
    addon_id = await first_id(seeded_session, Addon)
    assert (await client.delete(f"/admin/addons/{addon_id}", headers=owner)).status_code == 204


# Zones, areas, venues


async def test_zones_list_their_areas(client, staff):
    zones = (await client.get("/admin/zones", headers=staff)).json()
    masaki = next(z for z in zones if any(a["name"] == "Masaki" for a in z["areas"]))
    assert masaki["delivery_fee"] == 25000


async def test_zone_area_venue_lifecycle(client, owner):
    zone = await client.post("/admin/zones", json={"name": "Zone D", "delivery_fee": 80000}, headers=owner)
    assert zone.status_code == 201, zone.text
    zone_id = zone.json()["id"]
    area = await client.post("/admin/areas", json={"name": "Chanika", "zone_id": zone_id}, headers=owner)
    assert area.status_code == 201, area.text
    area_id = area.json()["id"]
    venue = await client.post(
        "/admin/venues", json={"name": "Ukumbi", "area_id": area_id, "address": "Barabara"}, headers=owner
    )
    assert venue.status_code == 201, venue.text
    venue_id = venue.json()["id"]

    refused(await client.delete(f"/admin/zones/{zone_id}", headers=owner), "in_use")
    refused(await client.delete(f"/admin/areas/{area_id}", headers=owner), "in_use")
    assert (await client.delete(f"/admin/venues/{venue_id}", headers=owner)).status_code == 204
    assert (await client.delete(f"/admin/areas/{area_id}", headers=owner)).status_code == 204
    assert (await client.delete(f"/admin/zones/{zone_id}", headers=owner)).status_code == 204


async def test_area_on_a_booking_is_in_use(client, seeded_session, booking_row, owner):
    zone_id = await first_id(seeded_session, Zone)
    area = Area(name="Bila Ukumbi", zone_id=zone_id)
    seeded_session.add(area)
    await seeded_session.flush()
    booking_row.area_id = area.id
    await seeded_session.commit()
    refused(await client.delete(f"/admin/areas/{area.id}", headers=owner), "in_use")


async def test_venue_on_a_booking_is_in_use(client, seeded_session, booking_row, owner):
    venue_id = await first_id(seeded_session, Venue)
    booking_row.venue_id = venue_id
    await seeded_session.commit()
    refused(await client.delete(f"/admin/venues/{venue_id}", headers=owner), "in_use")


async def test_repeated_area_name_is_refused(client, seeded_session, owner):
    zone_id = await first_id(seeded_session, Zone)
    refused(await client.post("/admin/areas", json={"name": "Masaki", "zone_id": zone_id}, headers=owner), "already_exists")
    sinza = await seeded_session.scalar(select(Area.id).where(Area.name == "Sinza"))
    refused(await client.patch(f"/admin/areas/{sinza}", json={"name": "Masaki"}, headers=owner), "already_exists")


async def test_parents_must_exist(client, owner):
    assert (await client.post("/admin/areas", json={"name": "X", "zone_id": 99999}, headers=owner)).status_code == 404
    res = await client.post("/admin/venues", json={"name": "X", "area_id": 99999, "address": ""}, headers=owner)
    assert res.status_code == 404


async def test_venues_show_their_area(client, staff):
    venues = (await client.get("/admin/venues", headers=staff)).json()
    assert {"id", "name", "area_id", "address"} <= set(venues[0])
    assert "lat" not in venues[0]


# Settings


async def test_settings_read_as_a_full_map(client, staff):
    data = (await client.get("/admin/settings", headers=staff)).json()
    assert data["business_name"] == "e-drinks"
    assert data["min_order"] == "300000"


async def test_settings_change_only_what_was_sent(client, owner):
    res = await client.put("/admin/settings", json={"business_name": "Vinywaji"}, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["business_name"] == "Vinywaji"
    assert res.json()["min_order"] == "300000"


@pytest.mark.parametrize(
    "change",
    [
        {"nonsense": "1"},
        {"min_order": "abc"},
        {"min_order": ""},
        {"min_order": "-1"},
        {"min_order": "1.5"},
        {"notice_days": "٣"},
        {"deposit_percent": "101"},
        {"balance_due_days": "366"},
        {"notice_days": "99999999"},
        {"min_order": "9999999999999"},
    ],
    ids=[
        "unknown", "words", "blank", "negative", "fraction", "non_ascii_digit", "over_100",
        "balance_days_too_long", "notice_days_too_long", "too_many_digits",
    ],
)
async def test_bad_settings_are_refused(client, owner, change):
    refused(await client.put("/admin/settings", json=change, headers=owner), "invalid_setting")


async def test_longest_allowed_balance_days_still_quotes(client, owner, ids):
    assert (await client.put("/admin/settings", json={"balance_due_days": "365"}, headers=owner)).status_code == 200
    assert (await client.post("/public/quote", json=body(ids))).status_code == 200


async def test_one_bad_setting_saves_nothing(client, owner):
    res = await client.put("/admin/settings", json={"business_name": "Vinywaji", "min_order": "x"}, headers=owner)
    refused(res, "invalid_setting")
    assert (await client.get("/admin/settings", headers=owner)).json()["business_name"] == "e-drinks"


async def test_a_missing_setting_row_can_be_saved(client, seeded_session, owner):
    await seeded_session.delete(await seeded_session.get(Setting, "tin"))
    await seeded_session.commit()
    assert (await client.get("/admin/settings", headers=owner)).json()["tin"] == ""
    res = await client.put("/admin/settings", json={"tin": "123"}, headers=owner)
    assert res.json()["tin"] == "123"


async def test_changed_minimum_reaches_the_next_quote(client, owner, ids):
    await client.put("/admin/settings", json={"min_order": "999999999"}, headers=owner)
    quote = (await client.post("/public/quote", json=body(ids))).json()
    assert quote["flags"]["below_minimum"] is True


# What the changes reach


async def test_price_change_reaches_a_new_quote_and_not_a_booking(client, seeded_session, owner, ids, book):
    code = await book()
    booking = await seeded_session.scalar(select(Booking).where(Booking.code == code))
    total = booking.total

    coke = ids["products"]["Coca-Cola 350ml"]
    res = await client.put(f"/admin/products/{coke}/tiers", json=[{"min_qty": 1, "unit_price": 99000}], headers=owner)
    assert res.status_code == 200, res.text

    quote = (await client.post("/public/quote", json=body(ids))).json()
    assert next(line for line in quote["lines"] if line["product_id"] == coke)["unit_price"] == 99000
    assert quote["total"] > total

    await seeded_session.refresh(booking)
    assert booking.total == total
    item = await seeded_session.scalar(
        select(BookingItem).where(BookingItem.booking_id == booking.id, BookingItem.product_id == coke)
    )
    assert item.unit_price != 99000


async def test_deactivated_product_leaves_public_views_and_can_return(client, owner, ids):
    coke = ids["products"]["Coca-Cola 350ml"]
    silver = ids["packages"]["silver"]

    async def rule_products():
        packages = (await client.get("/public/packages")).json()
        return [r["product_id"] for r in next(p for p in packages if p["id"] == silver)["rules"]]

    assert coke in await rule_products()
    assert (await client.patch(f"/admin/products/{coke}", json={"active": False}, headers=owner)).status_code == 200

    catalog = (await client.get("/public/catalog")).json()
    assert coke not in [p["id"] for p in catalog]
    assert coke not in await rule_products()
    quote = (await client.post("/public/quote", json=body(ids))).json()
    assert coke not in [line["product_id"] for line in quote["lines"]]

    # Hiding a rule must not delete it.
    assert (await client.patch(f"/admin/products/{coke}", json={"active": True}, headers=owner)).status_code == 200
    assert coke in await rule_products()


async def test_deactivated_addon_and_package_leave_public_views(client, owner, ids):
    cooler = ids["addons"]["cooler"]
    silver = ids["packages"]["silver"]
    await client.patch(f"/admin/addons/{cooler}", json={"active": False}, headers=owner)
    await client.patch(f"/admin/packages/{silver}", json={"active": False}, headers=owner)
    assert cooler not in [a["id"] for a in (await client.get("/public/addons")).json()]
    assert silver not in [p["id"] for p in (await client.get("/public/packages")).json()]


async def test_changed_delivery_fee_reaches_a_new_quote(client, seeded_session, owner, ids):
    zone_id = await seeded_session.scalar(select(Area.zone_id).where(Area.id == ids["areas"]["Masaki"]))
    await client.patch(f"/admin/zones/{zone_id}", json={"delivery_fee": 31000}, headers=owner)
    quote = (await client.post("/public/quote", json=body(ids))).json()
    assert quote["delivery_fee"] == 31000
