from fractions import Fraction

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Addon, Area, Package, Product, Zone
from app.services.pricing import AddonInfo, Catalog, PackageInfo, ProductInfo


async def load_catalog(session: AsyncSession) -> Catalog:
    """Load the active catalog into the plain types the pricing functions use."""
    products = await session.scalars(
        select(Product).where(Product.active).options(selectinload(Product.tiers))
    )
    packages = await session.scalars(
        select(Package).where(Package.active).options(selectinload(Package.rules))
    )
    addons = await session.scalars(select(Addon).where(Addon.active))
    area_fees = await session.execute(select(Area.id, Zone.delivery_fee).join(Zone))

    return Catalog(
        products={
            p.id: ProductInfo(
                id=p.id,
                name_sw=p.name_sw,
                name_en=p.name_en,
                unit=p.unit,
                units_per_pack=p.units_per_pack,
                tiers=tuple(sorted((t.min_qty, t.unit_price) for t in p.tiers)),
                returnable=p.returnable_glass,
                empties_deposit_per_pack=p.empties_deposit_per_unit,
            )
            for p in products
        },
        packages={
            p.id: PackageInfo(
                id=p.id,
                base_hours=p.base_hours,
                # str() keeps the column's exact decimal, whatever numeric type the driver returns
                rules=tuple(
                    (r.product_id, Fraction(str(r.qty_per_guest)), r.per_hour) for r in p.rules
                ),
            )
            for p in packages
        },
        addons={
            a.id: AddonInfo(
                id=a.id,
                name_sw=a.name_sw,
                name_en=a.name_en,
                kind=a.kind,
                price=a.price,
                capacity=a.owned_capacity,
            )
            for a in addons
        },
        area_fees={area_id: fee for area_id, fee in area_fees},
    )
