from dataclasses import fields
from fractions import Fraction

from sqlalchemy import select

from app.models import Addon, Area, Package, Product
from app.services.catalog_loader import load_catalog
from app.services.pricing import ProductInfo


async def _by_name(session, name_en) -> Product:
    return (await session.execute(select(Product).where(Product.name_en == name_en))).scalar_one()


async def test_loads_products_with_tiers(seeded_session):
    catalog = await load_catalog(seeded_session)
    coke_id = (await _by_name(seeded_session, "Coca-Cola 350ml")).id
    coke = catalog.products[coke_id]
    assert len(catalog.products) == 14
    assert coke.units_per_pack == 24
    assert coke.tiers == ((1, 16500), (10, 16000), (50, 15500))
    assert coke.returnable is True
    assert coke.empties_deposit_per_pack == 6000


async def test_product_info_has_no_cost_field():
    assert not [f.name for f in fields(ProductInfo) if "cost" in f.name]


async def test_package_rules_are_exact_fractions(seeded_session):
    catalog = await load_catalog(seeded_session)
    silver = (await seeded_session.execute(select(Package).where(Package.slug == "silver"))).scalar_one()
    coke_id = (await _by_name(seeded_session, "Coca-Cola 350ml")).id
    info = catalog.packages[silver.id]
    assert info.base_hours == 5
    assert (coke_id, Fraction(3, 4), True) in info.rules

    gold = (await seeded_session.execute(select(Package).where(Package.slug == "gold"))).scalar_one()
    wine_id = (await _by_name(seeded_session, "Red Wine 750ml")).id
    assert (wine_id, Fraction(1, 10), True) in catalog.packages[gold.id].rules


async def test_addons_keep_capacity_and_unlimited_is_none(seeded_session):
    catalog = await load_catalog(seeded_session)
    by_kind = {a.kind: a for a in catalog.addons.values()}
    assert by_kind["cooler"].capacity == 20
    assert by_kind["cooler"].price == 15000
    assert by_kind["ice"].capacity is None


async def test_area_fee_lookup(seeded_session):
    catalog = await load_catalog(seeded_session)
    masaki = (await seeded_session.execute(select(Area).where(Area.name == "Masaki"))).scalar_one()
    tegeta = (await seeded_session.execute(select(Area).where(Area.name == "Tegeta"))).scalar_one()
    assert catalog.area_fees[masaki.id] == 25000
    assert catalog.area_fees[tegeta.id] == 60000


async def test_inactive_rows_are_excluded(seeded_session):
    product = await _by_name(seeded_session, "Whisky 750ml")
    product.active = False
    package = (await seeded_session.execute(select(Package).where(Package.slug == "bronze"))).scalar_one()
    package.active = False
    addon = (await seeded_session.execute(select(Addon).where(Addon.kind == "bartender"))).scalar_one()
    addon.active = False
    await seeded_session.commit()

    catalog = await load_catalog(seeded_session)
    assert product.id not in catalog.products
    assert package.id not in catalog.packages
    assert addon.id not in catalog.addons
