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
