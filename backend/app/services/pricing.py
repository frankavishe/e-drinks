"""Pure quote calculation: plain dataclasses in, plain dataclasses out, no database.

All money is integer TZS, VAT-inclusive. Prices, tiers and empties deposits are per pack.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction
from math import ceil


class QuoteError(ValueError):
    """The request cannot be quoted (bad input, or an unknown/inactive item)."""


class CatalogError(ValueError):
    """The catalog data itself is wrong (e.g. no price tier covers a quantity)."""


@dataclass(frozen=True)
class ProductInfo:
    id: int
    name_sw: str
    name_en: str
    unit: str
    units_per_pack: int
    tiers: tuple[tuple[int, int], ...]  # (min_qty, unit_price)
    returnable: bool = False
    empties_deposit_per_pack: int = 0


@dataclass(frozen=True)
class PackageInfo:
    id: int
    base_hours: int
    rules: tuple[tuple[int, Fraction, bool], ...]  # (product_id, qty_per_guest, per_hour)


@dataclass(frozen=True)
class AddonInfo:
    id: int
    name_sw: str
    name_en: str
    kind: str
    price: int
    capacity: int | None  # None = unlimited


@dataclass(frozen=True)
class PricingSettings:
    min_order: int = 300000
    notice_days: int = 3
    notice_days_servers: int = 7
    deposit_percent: int = 50
    balance_due_days: int = 3


@dataclass(frozen=True)
class Catalog:
    products: dict[int, ProductInfo] = field(default_factory=dict)
    packages: dict[int, PackageInfo] = field(default_factory=dict)
    addons: dict[int, AddonInfo] = field(default_factory=dict)
    area_fees: dict[int, int] = field(default_factory=dict)  # area_id -> zone delivery fee


@dataclass(frozen=True)
class QuoteRequest:
    event_date: date
    hours: int
    guests: int
    setup_at: datetime
    collect_at: datetime
    package_id: int | None = None
    overrides: dict[int, int] = field(default_factory=dict)  # product_id -> packs
    items: tuple[tuple[int, int], ...] = ()  # (product_id, packs)
    addons: tuple[tuple[int, int], ...] = ()  # (addon_id, qty)
    area_id: int | None = None
    custom_area: str | None = None


@dataclass(frozen=True)
class QuoteLine:
    product_id: int
    name_sw: str
    name_en: str
    unit: str
    packs: int
    unit_price: int
    line_total: int
    empties_deposit: int
    source: str  # package | custom


@dataclass(frozen=True)
class AddonLine:
    addon_id: int
    name_sw: str
    name_en: str
    qty: int
    unit_price: int
    line_total: int
    available: int | None  # None = unlimited
    ok: bool


@dataclass(frozen=True)
class QuoteFlags:
    is_rush: bool
    below_minimum: bool
    min_order: int
    provisional: bool
    addons_unavailable: tuple[int, ...]


@dataclass(frozen=True)
class Quote:
    lines: tuple[QuoteLine, ...]
    addon_lines: tuple[AddonLine, ...]
    subtotal: int
    addons_total: int
    delivery_fee: int
    delivery_custom: bool
    empties_deposit: int
    total: int
    deposit_due: int
    balance_due_date: date
    flags: QuoteFlags


def package_quantities(
    package: PackageInfo, guests: int, hours: int, products: dict[int, ProductInfo]
) -> dict[int, int]:
    """Whole packs per product. Rules for products not in `products` (inactive) are skipped."""
    quantities = {}
    for product_id, qty_per_guest, per_hour in package.rules:
        product = products.get(product_id)
        if product is None:
            continue
        factor = Fraction(hours, package.base_hours) if per_hour else 1
        quantities[product_id] = ceil(guests * qty_per_guest * factor / product.units_per_pack)
    return quantities


def tier_price(product: ProductInfo, qty: int) -> int:
    """Unit price from the tier with the largest min_qty not exceeding qty; applies to the whole line."""
    prices = [(min_qty, price) for min_qty, price in product.tiers if min_qty <= qty]
    if not prices:
        raise CatalogError(f"No price tier for {qty} of product {product.id} ({product.name_en})")
    return max(prices)[1]


def _line(product: ProductInfo, packs: int, source: str) -> QuoteLine:
    unit_price = tier_price(product, packs)
    return QuoteLine(
        product_id=product.id,
        name_sw=product.name_sw,
        name_en=product.name_en,
        unit=product.unit,
        packs=packs,
        unit_price=unit_price,
        line_total=packs * unit_price,
        empties_deposit=packs * product.empties_deposit_per_pack if product.returnable else 0,
        source=source,
    )


def _product(catalog: Catalog, product_id: int) -> ProductInfo:
    product = catalog.products.get(product_id)
    if product is None:
        raise QuoteError(f"Unknown or inactive product {product_id}")
    return product


def _drink_lines(req: QuoteRequest, catalog: Catalog) -> tuple[QuoteLine, ...]:
    if req.package_id is None:
        return tuple(
            _line(_product(catalog, product_id), packs, "custom") for product_id, packs in req.items
        )

    package = catalog.packages.get(req.package_id)
    if package is None:
        raise QuoteError(f"Unknown or inactive package {req.package_id}")
    computed = package_quantities(package, req.guests, req.hours, catalog.products)
    for product_id in req.overrides:
        _product(catalog, product_id)
    quantities = {**computed, **req.overrides}
    return tuple(
        _line(catalog.products[product_id], packs, "package" if product_id in computed else "custom")
        for product_id, packs in quantities.items()
        if packs > 0
    )


def _delivery_fee(req: QuoteRequest, catalog: Catalog) -> int:
    if req.area_id not in catalog.area_fees:
        raise QuoteError(f"Unknown area {req.area_id}")
    return catalog.area_fees[req.area_id]


def build_quote(
    req: QuoteRequest,
    catalog: Catalog,
    settings: PricingSettings,
    *,
    availability: dict[int, int | None],
    is_rush: bool,
) -> Quote:
    lines = _drink_lines(req, catalog)
    subtotal = sum(line.line_total for line in lines)
    empties_deposit = sum(line.empties_deposit for line in lines)
    delivery_fee = _delivery_fee(req, catalog)
    total = subtotal + delivery_fee + empties_deposit

    return Quote(
        lines=lines,
        addon_lines=(),
        subtotal=subtotal,
        addons_total=0,
        delivery_fee=delivery_fee,
        delivery_custom=False,
        empties_deposit=empties_deposit,
        total=total,
        deposit_due=-(-total * settings.deposit_percent // 100),  # integer ceiling
        balance_due_date=req.event_date - timedelta(days=settings.balance_due_days),
        flags=QuoteFlags(
            is_rush=is_rush,
            below_minimum=subtotal < settings.min_order,
            min_order=settings.min_order,
            provisional=False,
            addons_unavailable=(),
        ),
    )
