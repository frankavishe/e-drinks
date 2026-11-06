"""Catalog, zone and venue shapes (contracts/admin-api.md).

As in schemas/admin.py, cost fields exist only on the owner classes, so they can't reach staff.
Tier values aren't range-checked for meaning here: catalog_admin refuses bad sets with a code the UI translates.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer

MAX_MONEY = 1_000_000_000_000
MAX_COUNT = 1_000_000

Money = Annotated[int, Field(ge=0, le=MAX_MONEY)]
Count = Annotated[int, Field(ge=0, le=MAX_COUNT)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
LongName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]+$", max_length=40)]
ImageUrl = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^https?://\S+$", max_length=500)]
UnitsPerPack = Annotated[int, Field(ge=1, le=MAX_COUNT)]
BaseHours = Annotated[int, Field(ge=1, le=48)]
QtyPerGuest = Annotated[Decimal, Field(gt=0, max_digits=6, decimal_places=3)]
AddonKind = Literal["cooler", "ice", "server", "bartender"]


class _FromAttributes(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Products


class TierIn(BaseModel):
    min_qty: int = Field(le=MAX_COUNT)
    unit_price: int = Field(le=MAX_MONEY)


class TierAdminOut(_FromAttributes):
    min_qty: int
    unit_price: int


class ProductIn(BaseModel):
    name_sw: LongName
    name_en: LongName
    category: Category
    unit: Unit
    units_per_pack: UnitsPerPack = 1
    is_alcohol: bool = False
    cost_price: Money = 0
    image_url: ImageUrl | None = None
    returnable_glass: bool = False
    empties_deposit_per_unit: Money = 0
    active: bool = True
    tiers: list[TierIn]


class ProductPatch(BaseModel):
    name_sw: LongName | None = None
    name_en: LongName | None = None
    category: Category | None = None
    unit: Unit | None = None
    units_per_pack: UnitsPerPack | None = None
    is_alcohol: bool | None = None
    cost_price: Money | None = None
    image_url: ImageUrl | None = None
    returnable_glass: bool | None = None
    empties_deposit_per_unit: Money | None = None
    active: bool | None = None


class ProductStaffOut(_FromAttributes):
    id: int
    name_sw: str
    name_en: str
    category: str
    unit: str
    units_per_pack: int
    is_alcohol: bool
    image_url: str | None
    returnable_glass: bool
    empties_deposit_per_unit: int
    active: bool
    tiers: list[TierAdminOut]


class ProductOwnerOut(ProductStaffOut):
    cost_price: int


# Packages


class RuleIn(BaseModel):
    product_id: int
    qty_per_guest: QtyPerGuest
    per_hour: bool = False


class RuleOut(_FromAttributes):
    product_id: int
    qty_per_guest: Decimal
    per_hour: bool

    @field_serializer("qty_per_guest")
    def exact_three_places(self, value: Decimal) -> str:
        return f"{value:.3f}"


class PackageIn(BaseModel):
    slug: Slug
    name_sw: Name
    name_en: Name
    description_sw: Description = ""
    description_en: Description = ""
    base_hours: BaseHours = 5
    sort_order: Count = 0
    active: bool = True
    rules: list[RuleIn]


class PackagePatch(BaseModel):
    slug: Slug | None = None
    name_sw: Name | None = None
    name_en: Name | None = None
    description_sw: Description | None = None
    description_en: Description | None = None
    base_hours: BaseHours | None = None
    sort_order: Count | None = None
    active: bool | None = None


class PackageAdminOut(_FromAttributes):
    id: int
    slug: str
    name_sw: str
    name_en: str
    description_sw: str
    description_en: str
    base_hours: int
    sort_order: int
    active: bool
    rules: list[RuleOut]


# Add-ons


class AddonCreate(BaseModel):
    name_sw: Name
    name_en: Name
    kind: AddonKind
    price: Money
    owned_capacity: Count | None = None
    replacement_cost: Money = 0
    active: bool = True


class AddonPatch(BaseModel):
    name_sw: Name | None = None
    name_en: Name | None = None
    kind: AddonKind | None = None
    price: Money | None = None
    owned_capacity: Count | None = None
    replacement_cost: Money | None = None
    active: bool | None = None


class AddonStaffOut(_FromAttributes):
    id: int
    name_sw: str
    name_en: str
    kind: str
    price: int
    owned_capacity: int | None
    active: bool


class AddonOwnerOut(AddonStaffOut):
    replacement_cost: int


# Zones, areas, venues


class ZoneIn(BaseModel):
    name: Name
    delivery_fee: Money


class ZonePatch(BaseModel):
    name: Name | None = None
    delivery_fee: Money | None = None


class AreaIn(BaseModel):
    name: Name
    zone_id: int


class AreaPatch(BaseModel):
    name: Name | None = None
    zone_id: int | None = None


class AreaAdminOut(_FromAttributes):
    id: int
    name: str
    zone_id: int


class ZoneAdminOut(BaseModel):
    id: int
    name: str
    delivery_fee: int
    areas: list[AreaAdminOut]


class VenueIn(BaseModel):
    name: LongName
    area_id: int
    address: Address = ""


class VenuePatch(BaseModel):
    name: LongName | None = None
    area_id: int | None = None
    address: Address | None = None


class VenueAdminOut(_FromAttributes):
    id: int
    name: str
    area_id: int
    address: str
