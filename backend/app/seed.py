"""Idempotent sample data: settings, catalog, packages, add-ons, Dar es Salaam zones/areas.

Run:  python -m app.seed [--owner-email you@example.com]
The owner email must already exist in Supabase Auth (Auth → Users); its id becomes the owner profile.
All prices are TZS, VAT-inclusive, and are samples for the owner to edit.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Addon,
    Area,
    Package,
    PackageRule,
    PriceTier,
    Product,
    Profile,
    Setting,
    StockLevel,
    Venue,
    Zone,
)

SETTINGS = {
    "business_name": "e-drinks",
    "tin": "",
    "vrn": "",
    "phone": "+255 700 000 000",
    "email": "",
    "notification_email": "",
    "whatsapp_number": "255700000000",
    "min_order": "300000",
    "notice_days": "3",
    "notice_days_servers": "7",
    "deposit_percent": "50",
    "balance_due_days": "3",
    "mpesa_till": "",
    "tigopesa_lipa": "",
    "airtel_lipa": "",
    "bank_details": "",
    "policy_text_sw": (
        "Amana ya 50% inathibitisha tarehe. Salio linalipwa siku 3 kabla ya tukio. "
        "Kughairi siku 14+ kabla: amana inarudishwa ukiondoa 10%. Siku 7–13: 50% inarudishwa. "
        "Chini ya siku 7: hakuna marejesho. Vinywaji visivyofunguliwa hurudishwa ndani ya saa 48."
    ),
    "policy_text_en": (
        "A 50% deposit locks the date. The balance is due 3 days before the event. "
        "Cancel 14+ days before: deposit refunded minus 10%. 7–13 days: 50% refunded. "
        "Under 7 days: no refund. Sealed, unopened drinks can be returned within 48h."
    ),
}

# (name_sw, name_en, category, unit, units_per_pack, alcohol, cost, glass, empties_deposit, tiers)
# tiers: prices per pack for 1–9 / 10–49 / 50+ packs
PRODUCTS = [
    ("Coca-Cola 350ml", "Coca-Cola 350ml", "soft", "kreti ya chupa 24", 24, False, 13000, True, 6000, (16500, 16000, 15500)),
    ("Fanta Orange 350ml", "Fanta Orange 350ml", "soft", "kreti ya chupa 24", 24, False, 13000, True, 6000, (16500, 16000, 15500)),
    ("Sprite 350ml", "Sprite 350ml", "soft", "kreti ya chupa 24", 24, False, 13000, True, 6000, (16500, 16000, 15500)),
    ("Maji 500ml", "Water 500ml", "water", "pakiti ya chupa 12", 12, False, 4800, False, 0, (6500, 6000, 5500)),
    ("Juisi ya Embe 1L", "Mango Juice 1L", "juice", "katoni ya 12", 12, False, 24000, False, 0, (30000, 29000, 28000)),
    ("Kilimanjaro Lager 500ml", "Kilimanjaro Lager 500ml", "beer", "kreti ya chupa 25", 25, True, 42000, True, 10000, (50000, 48500, 47000)),
    ("Safari Lager 500ml", "Safari Lager 500ml", "beer", "kreti ya chupa 25", 25, True, 44000, True, 10000, (52000, 50500, 49000)),
    ("Serengeti Lager 500ml", "Serengeti Lager 500ml", "beer", "kreti ya chupa 25", 25, True, 42000, True, 10000, (50000, 48500, 47000)),
    ("Savanna Cider 330ml", "Savanna Cider 330ml", "cider", "katoni ya chupa 24", 24, True, 72000, False, 0, (86000, 84000, 82000)),
    ("Divai Nyekundu 750ml", "Red Wine 750ml", "wine", "katoni ya chupa 12", 12, True, 180000, False, 0, (216000, 210000, 204000)),
    ("Divai Nyeupe 750ml", "White Wine 750ml", "wine", "katoni ya chupa 12", 12, True, 180000, False, 0, (216000, 210000, 204000)),
    ("Konyagi 750ml", "Konyagi 750ml", "spirit", "katoni ya chupa 12", 12, True, 132000, False, 0, (158000, 154000, 150000)),
    ("Vodka 750ml", "Vodka 750ml", "spirit", "katoni ya chupa 12", 12, True, 300000, False, 0, (360000, 350000, 340000)),
    ("Whisky 750ml", "Whisky 750ml", "spirit", "katoni ya chupa 12", 12, True, 480000, False, 0, (576000, 560000, 545000)),
]

# Bottles per guest over the package's base hours; all scale with event length.
PACKAGES = [
    ("bronze", "Shaba", "Bronze", "Vinywaji baridi na maji.", "Soft drinks and water.", 1, {
        "Coca-Cola 350ml": 1.0, "Fanta Orange 350ml": 0.5, "Sprite 350ml": 0.5, "Water 500ml": 1.0,
    }),
    ("silver", "Fedha", "Silver", "Vinywaji baridi, maji na bia.", "Soft drinks, water and beer.", 2, {
        "Coca-Cola 350ml": 0.75, "Fanta Orange 350ml": 0.5, "Sprite 350ml": 0.25, "Water 500ml": 1.0,
        "Kilimanjaro Lager 500ml": 1.0, "Safari Lager 500ml": 0.5,
    }),
    ("gold", "Dhahabu", "Gold", "Vinywaji baridi, bia, divai na Konyagi.", "Soft drinks, beer, wine and Konyagi.", 3, {
        "Coca-Cola 350ml": 0.75, "Fanta Orange 350ml": 0.5, "Sprite 350ml": 0.25, "Water 500ml": 1.0,
        "Kilimanjaro Lager 500ml": 1.0, "Safari Lager 500ml": 0.5, "Serengeti Lager 500ml": 0.5,
        "Red Wine 750ml": 0.1, "White Wine 750ml": 0.05, "Konyagi 750ml": 0.05,
    }),
    ("premium", "Baa Kamili", "Premium bar", "Baa kamili: bia, divai, cider na pombe kali.", "Full bar: beer, wine, cider and spirits.", 4, {
        "Coca-Cola 350ml": 0.75, "Fanta Orange 350ml": 0.5, "Sprite 350ml": 0.5, "Water 500ml": 1.0,
        "Mango Juice 1L": 0.1, "Kilimanjaro Lager 500ml": 1.0, "Safari Lager 500ml": 0.5,
        "Serengeti Lager 500ml": 0.5, "Savanna Cider 330ml": 0.5, "Red Wine 750ml": 0.15,
        "White Wine 750ml": 0.1, "Konyagi 750ml": 0.05, "Vodka 750ml": 0.04, "Whisky 750ml": 0.04,
    }),
]

# (name_sw, name_en, kind, price, owned_capacity, replacement_cost)
ADDONS = [
    ("Jokofu la barafu (cooler)", "Ice cooler", "cooler", 15000, 20, 150000),
    ("Mfuko wa barafu 5kg", "Ice bag 5kg", "ice", 3000, None, 0),
    ("Mhudumu (zamu moja)", "Drinks server (per shift)", "server", 40000, 10, 0),
    ("Bartender (zamu moja)", "Bartender (per shift)", "bartender", 80000, 3, 0),
]

ZONES = {
    ("Zone A — Kati", 25000): ["Masaki", "Oyster Bay", "Msasani", "Upanga", "Posta", "Kariakoo", "Kinondoni"],
    ("Zone B — Karibu", 40000): ["Mikocheni", "Mwenge", "Sinza", "Kijitonyama", "Mbezi Beach", "Ilala", "Ubungo", "Tabata", "Mabibo"],
    ("Zone C — Mbali", 60000): ["Tegeta", "Bunju", "Kimara", "Mbezi Luis", "Temeke", "Kigamboni", "Ukonga", "Gongo la Mboto", "Kurasini"],
}

VENUES = [
    ("Ukumbi wa Mfano Masaki", "Masaki", "Barabara ya Haile Selassie (mfano)"),
    ("Bustani ya Mfano Mbezi Beach", "Mbezi Beach", "Barabara ya Bagamoyo (mfano)"),
]


async def _get_one(session: AsyncSession, stmt):
    return (await session.execute(stmt)).scalar_one_or_none()


async def seed(
    session: AsyncSession, owner_id: uuid.UUID | None = None, owner_email: str = ""
) -> None:
    for key, value in SETTINGS.items():
        if await session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value))

    products: dict[str, Product] = {}
    for sw, en, cat, unit, per_pack, alcohol, cost, glass, empties, tiers in PRODUCTS:
        product = await _get_one(session, select(Product).where(Product.name_en == en))
        if product is None:
            product = Product(
                name_sw=sw, name_en=en, category=cat, unit=unit, units_per_pack=per_pack,
                is_alcohol=alcohol, cost_price=cost, returnable_glass=glass,
                empties_deposit_per_unit=empties,
                tiers=[PriceTier(min_qty=q, unit_price=p) for q, p in zip((1, 10, 50), tiers)],
            )
            session.add(product)
            await session.flush()
            session.add(StockLevel(product_id=product.id, on_hand=0))
        products[en] = product

    for slug, sw, en, desc_sw, desc_en, order, rules in PACKAGES:
        if await _get_one(session, select(Package).where(Package.slug == slug)) is None:
            session.add(Package(
                slug=slug, name_sw=sw, name_en=en, description_sw=desc_sw, description_en=desc_en,
                base_hours=5, sort_order=order,
                rules=[
                    PackageRule(product_id=products[name].id, qty_per_guest=qty, per_hour=True)
                    for name, qty in rules.items()
                ],
            ))

    for sw, en, kind, price, capacity, replacement in ADDONS:
        if await _get_one(session, select(Addon).where(Addon.kind == kind)) is None:
            session.add(Addon(
                name_sw=sw, name_en=en, kind=kind, price=price,
                owned_capacity=capacity, replacement_cost=replacement,
            ))

    areas: dict[str, Area] = {}
    for (zone_name, fee), area_names in ZONES.items():
        zone = await _get_one(session, select(Zone).where(Zone.name == zone_name))
        if zone is None:
            zone = Zone(name=zone_name, delivery_fee=fee)
            session.add(zone)
            await session.flush()
        for name in area_names:
            area = await _get_one(session, select(Area).where(Area.name == name))
            if area is None:
                area = Area(name=name, zone_id=zone.id)
                session.add(area)
                await session.flush()
            areas[name] = area

    for name, area_name, address in VENUES:
        if await _get_one(session, select(Venue).where(Venue.name == name)) is None:
            session.add(Venue(name=name, area_id=areas[area_name].id, address=address))

    if owner_id is not None and await session.get(Profile, owner_id) is None:
        session.add(Profile(id=owner_id, role="owner", name="Owner", email=owner_email))

    await session.commit()


async def _main(owner_email: str | None) -> None:
    from app.db import SessionLocal, engine

    async with SessionLocal() as session:
        owner_id = None
        if owner_email:
            row = (await session.execute(
                text("select id from auth.users where email = :e"), {"e": owner_email}
            )).first()
            if row is None:
                raise SystemExit(f"No Supabase Auth user with email {owner_email}; create it first.")
            owner_id = row[0]
        await seed(session, owner_id=owner_id, owner_email=owner_email or "")
    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-email")
    asyncio.run(_main(parser.parse_args().owner_email))
