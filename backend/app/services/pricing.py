"""Pure quote calculation: plain dataclasses in, plain dataclasses out, no database.

All money is integer TZS, VAT-inclusive. Prices, tiers and empties deposits are per pack.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction


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
