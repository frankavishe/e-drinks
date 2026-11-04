"""Pure pricing tests. Every expected figure is worked out by hand from the fixture below."""

from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

import pytest

from app.services.pricing import (
    AddonInfo,
    Catalog,
    CatalogError,
    PackageInfo,
    PricingSettings,
    ProductInfo,
    QuoteError,
    QuoteRequest,
    build_quote,
    has_staff_addon,
    package_quantities,
    tier_price,
)

EAT = timezone(timedelta(hours=3))
TIERS = ((1, 1000), (10, 900), (50, 800))

SODA = ProductInfo(1, "Soda", "Soda", "crate", 24, ((1, 16500), (10, 16000), (50, 15500)), True, 6000)
WATER = ProductInfo(2, "Maji", "Water", "pack", 12, ((1, 6500), (10, 6000), (50, 5500)))
BEER = ProductInfo(3, "Bia", "Beer", "crate", 25, ((1, 50000), (10, 48500), (50, 47000)), True, 10000)
WINE = ProductInfo(4, "Divai", "Wine", "case", 12, ((1, 216000), (10, 210000), (50, 204000)))

PACKAGE = PackageInfo(
    id=1,
    base_hours=5,
    rules=(
        (1, Fraction(3, 4), False),  # soda: 0.75 bottles per guest, flat
        (2, Fraction(1), True),  # water: 1 per guest per 5 h, scales with hours
        (3, Fraction(1), False),  # beer: 1 per guest, flat
    ),
)

COOLER = AddonInfo(1, "Jokofu", "Cooler", "cooler", 15000, 20)
ICE = AddonInfo(2, "Barafu", "Ice", "ice", 3000, None)
SERVER = AddonInfo(3, "Mhudumu", "Server", "server", 40000, 10)
BARTENDER = AddonInfo(4, "Bartender", "Bartender", "bartender", 80000, 3)

CATALOG = Catalog(
    products={p.id: p for p in (SODA, WATER, BEER, WINE)},
    packages={1: PACKAGE},
    addons={a.id: a for a in (COOLER, ICE, SERVER, BARTENDER)},
    area_fees={7: 25000, 8: 60000},
)
SETTINGS = PricingSettings()
EVENT = date(2026, 12, 12)


def request(**overrides) -> QuoteRequest:
    values = {
        "event_date": EVENT,
        "hours": 5,
        "guests": 300,
        "setup_at": datetime(2026, 12, 12, 15, tzinfo=EAT),
        "collect_at": datetime(2026, 12, 13, 9, tzinfo=EAT),
        "package_id": 1,
        "area_id": 7,
    }
    return QuoteRequest(**{**values, **overrides})


def custom(*items, **overrides) -> QuoteRequest:
    return request(package_id=None, items=tuple(items), **overrides)


def quote(req, catalog=CATALOG, settings=SETTINGS, availability=None, is_rush=False):
    return build_quote(req, catalog, settings, availability=availability or {}, is_rush=is_rush)


# --- T008: package rounding and hour scaling -------------------------------------------------


def packs_for(guests, hours, package=PACKAGE, products=CATALOG.products):
    return package_quantities(package, guests, hours, products)


def test_rounds_up_to_whole_packs():
    assert packs_for(300, 5)[1] == 10  # 225 bottles / 24 = 9.375


def test_exact_multiple_stays_exact():
    assert packs_for(300, 5)[3] == 12  # 300 bottles / 25 = 12 exactly


def test_fraction_math_does_not_add_a_pack():
    # In floats 300 x 0.1 is 30.000000000000004, which would round up to a second pack of 30.
    product = ProductInfo(5, "x", "x", "u", 30, TIERS)
    package = PackageInfo(2, 5, ((5, Fraction(1, 10), False),))
    assert packs_for(300, 5, package, {5: product})[5] == 1


def test_per_hour_rule_scales_with_event_length():
    assert packs_for(300, 10)[2] == 50  # 600 bottles / 12, double the 25 at base hours


def test_non_per_hour_rule_ignores_event_length():
    assert packs_for(300, 10)[1] == 10
    assert packs_for(300, 10)[3] == 12


def test_inactive_product_is_skipped():
    products = {k: v for k, v in CATALOG.products.items() if k != 3}
    assert 3 not in packs_for(300, 5, products=products)


# --- T009: tier selection --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("qty", "price"), [(1, 1000), (9, 1000), (10, 900), (49, 900), (50, 800), (500, 800)]
)
def test_tier_selection(qty, price):
    assert tier_price(ProductInfo(9, "x", "x", "u", 1, TIERS), qty) == price


def test_no_tier_for_quantity_is_a_catalog_error():
    product = ProductInfo(9, "x", "Thing", "u", 1, ((10, 900),))
    with pytest.raises(CatalogError, match="Thing"):
        tier_price(product, 9)


# --- T010: delivery, empties, totals, deposit, balance date ----------------------------------


def test_package_quote_lines():
    lines = {line.product_id: line for line in quote(request()).lines}
    assert (lines[1].packs, lines[1].unit_price, lines[1].line_total) == (10, 16000, 160000)
    assert (lines[2].packs, lines[2].unit_price, lines[2].line_total) == (25, 6000, 150000)
    assert (lines[3].packs, lines[3].unit_price, lines[3].line_total) == (12, 48500, 582000)
    assert lines[1].source == "package"
    assert (lines[1].name_sw, lines[1].name_en, lines[1].unit) == ("Soda", "Soda", "crate")


def test_zone_delivery_fee():
    assert quote(request()).delivery_fee == 25000
    assert quote(request(area_id=8)).delivery_fee == 60000


def test_unknown_area_is_rejected():
    with pytest.raises(QuoteError, match="99"):
        quote(request(area_id=99))


def test_unknown_or_inactive_package_is_rejected():
    with pytest.raises(QuoteError, match="99"):
        quote(request(package_id=99))


def test_empties_deposit_only_on_returnable_products():
    q = quote(request())
    lines = {line.product_id: line for line in q.lines}
    assert lines[1].empties_deposit == 60000  # 10 x 6,000
    assert lines[2].empties_deposit == 0  # plastic water
    assert lines[3].empties_deposit == 120000  # 12 x 10,000
    assert q.empties_deposit == 180000


def test_total_is_the_sum_of_its_parts():
    q = quote(request())
    assert q.subtotal == 892000  # 160,000 + 150,000 + 582,000
    assert q.total == 892000 + 25000 + 180000


def test_deposit_is_half_of_an_even_total():
    assert quote(request()).deposit_due == 548500  # 1,097,000 / 2


def test_deposit_rounds_up_on_an_odd_total():
    # 1 pack priced 1,001 with a 2,000 fee: total 3,001, half is 1,500.5.
    product = ProductInfo(1, "x", "x", "u", 1, ((1, 1001),))
    package = PackageInfo(1, 5, ((1, Fraction(1), False),))
    catalog = Catalog(products={1: product}, packages={1: package}, area_fees={7: 2000})
    assert quote(request(guests=1), catalog=catalog).deposit_due == 1501


def test_deposit_percent_comes_from_settings():
    q = quote(request(), settings=PricingSettings(deposit_percent=30))
    assert q.deposit_due == 329100  # 30% of 1,097,000


def test_balance_due_date_is_three_days_before_the_event():
    assert quote(request()).balance_due_date == date(2026, 12, 9)


def test_balance_due_days_come_from_settings():
    q = quote(request(), settings=PricingSettings(balance_due_days=5))
    assert q.balance_due_date == date(2026, 12, 7)


# --- T015: custom orders, overrides, minimum order -------------------------------------------


def test_custom_items_use_tier_prices():
    q = quote(custom((1, 12), (3, 3)))
    lines = {line.product_id: line for line in q.lines}
    assert (lines[1].packs, lines[1].unit_price, lines[1].line_total) == (12, 16000, 192000)
    assert (lines[3].packs, lines[3].unit_price, lines[3].line_total) == (3, 50000, 150000)
    assert lines[1].source == "custom"
    assert q.subtotal == 342000
    assert q.empties_deposit == 72000 + 30000


def test_custom_item_unknown_or_inactive_product_is_rejected():
    with pytest.raises(QuoteError, match="99"):
        quote(custom((99, 1)))


def test_override_replaces_a_package_line_and_reprices_its_tier():
    lines = {line.product_id: line for line in quote(request(overrides={1: 9})).lines}
    assert (lines[1].packs, lines[1].unit_price, lines[1].line_total) == (9, 16500, 148500)
    assert lines[1].source == "package"
    assert lines[1].empties_deposit == 54000


def test_override_zero_removes_the_line():
    q = quote(request(overrides={1: 0}))
    assert 1 not in {line.product_id for line in q.lines}
    assert q.subtotal == 150000 + 582000


def test_override_for_a_product_outside_the_package_adds_it():
    lines = {line.product_id: line for line in quote(request(overrides={4: 2})).lines}
    assert (lines[4].packs, lines[4].unit_price, lines[4].source) == (2, 216000, "custom")
    assert len(lines) == 4


def test_override_for_unknown_or_inactive_product_is_rejected():
    with pytest.raises(QuoteError, match="99"):
        quote(request(overrides={99: 1}))


def _one_product_catalog(price, deposit=0, fee=0):
    product = ProductInfo(1, "x", "x", "u", 1, ((1, price),), deposit > 0, deposit)
    return Catalog(products={1: product}, area_fees={7: fee})


def test_below_minimum_flag_and_amount():
    flags = quote(custom((1, 1)), catalog=_one_product_catalog(299999)).flags
    assert flags.below_minimum is True
    assert flags.min_order == 300000


def test_exactly_the_minimum_is_not_below():
    assert quote(custom((1, 1)), catalog=_one_product_catalog(300000)).flags.below_minimum is False


def test_delivery_and_empties_do_not_count_toward_the_minimum():
    catalog = _one_product_catalog(299999, deposit=50000, fee=60000)
    q = quote(custom((1, 1)), catalog=catalog)
    assert q.total == 409999
    assert q.flags.below_minimum is True


def test_below_minimum_still_returns_a_full_quote():
    q = quote(custom((1, 1)), catalog=_one_product_catalog(1000))
    assert q.total == 1000
    assert q.deposit_due == 500


# --- T020: add-on pricing and availability ---------------------------------------------------


def test_addon_lines_are_priced_per_unit():
    q = quote(request(addons=((1, 6), (3, 4))), availability={1: 20, 3: 10})
    lines = {line.addon_id: line for line in q.addon_lines}
    assert (lines[1].qty, lines[1].unit_price, lines[1].line_total) == (6, 15000, 90000)
    assert (lines[3].qty, lines[3].unit_price, lines[3].line_total) == (4, 40000, 160000)  # per shift
    assert (lines[1].name_sw, lines[1].name_en) == ("Jokofu", "Cooler")
    assert q.addons_total == 250000
    assert q.total == 1097000 + 250000
    assert q.deposit_due == 673500


def test_addon_within_free_count_is_ok():
    q = quote(request(addons=((1, 3),)), availability={1: 3})
    assert (q.addon_lines[0].ok, q.addon_lines[0].available) == (True, 3)
    assert q.flags.addons_unavailable == ()


def test_addon_above_free_count_is_flagged_with_the_free_count():
    q = quote(request(addons=((1, 4),)), availability={1: 3})
    assert (q.addon_lines[0].ok, q.addon_lines[0].available) == (False, 3)
    assert q.flags.addons_unavailable == (1,)


def test_total_is_still_computed_when_an_addon_is_short():
    q = quote(request(addons=((1, 4),)), availability={1: 3})
    assert q.addons_total == 60000
    assert q.total == 1097000 + 60000


def test_unlimited_addon_is_always_ok():
    q = quote(request(addons=((2, 500),)), availability={2: None})
    assert (q.addon_lines[0].ok, q.addon_lines[0].available) == (True, None)


def test_unknown_or_inactive_addon_is_rejected():
    with pytest.raises(QuoteError, match="99"):
        quote(request(addons=((99, 1),)))


def test_addons_count_toward_the_minimum():
    catalog = Catalog(
        products={1: ProductInfo(1, "x", "x", "u", 1, ((1, 290000),))},
        addons={1: COOLER},
        area_fees={7: 0},
    )
    without = quote(custom((1, 1)), catalog=catalog)
    with_addon = quote(custom((1, 1), addons=((1, 1),)), catalog=catalog, availability={1: 20})
    assert without.flags.below_minimum is True
    assert with_addon.flags.below_minimum is False


# --- T023: staff add-ons decide which notice period applies ----------------------------------


@pytest.mark.parametrize(
    ("addons", "expected"),
    [((), False), (((1, 2), (2, 5)), False), (((3, 1),), True), (((1, 2), (4, 1)), True), (((99, 1),), False)],
)
def test_has_staff_addon(addons, expected):
    assert has_staff_addon(request(addons=addons), CATALOG) is expected


def test_is_rush_is_passed_through_to_the_flags():
    assert quote(request(), is_rush=True).flags.is_rush is True
    assert quote(request(), is_rush=False).flags.is_rush is False


# --- T024: unlisted area ---------------------------------------------------------------------


def test_custom_area_has_no_delivery_fee_and_is_provisional():
    q = quote(request(area_id=None, custom_area="Bagamoyo"))
    assert q.delivery_fee == 0
    assert q.delivery_custom is True
    assert q.flags.provisional is True


def test_custom_area_total_and_deposit_exclude_delivery():
    q = quote(request(area_id=None, custom_area="Bagamoyo"))
    assert q.total == 892000 + 180000
    assert q.deposit_due == 536000


def test_listed_area_is_not_provisional():
    q = quote(request())
    assert q.delivery_custom is False
    assert q.flags.provisional is False
