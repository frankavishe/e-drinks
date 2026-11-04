"""Public API shapes (contracts/public-api.md). Nothing here may carry a cost field."""

from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.services.phone import normalise_phone


class _FromAttributes(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TierOut(_FromAttributes):
    min_qty: int
    unit_price: int


class ProductOut(_FromAttributes):
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
    tiers: list[TierOut]


class PackageRuleOut(_FromAttributes):
    product_id: int
    qty_per_guest: float
    per_hour: bool


class PackageOut(_FromAttributes):
    id: int
    slug: str
    name_sw: str
    name_en: str
    description_sw: str
    description_en: str
    base_hours: int
    rules: list[PackageRuleOut]


class AddonOut(_FromAttributes):
    id: int
    name_sw: str
    name_en: str
    kind: str
    price: int


class AreaOut(_FromAttributes):
    id: int
    name: str


class ZoneOut(BaseModel):
    id: int
    name: str
    delivery_fee: int
    areas: list[AreaOut]


class VenueOut(_FromAttributes):
    id: int
    name: str
    area_id: int
    address: str


class AreasOut(BaseModel):
    zones: list[ZoneOut]
    venues: list[VenueOut]


class ItemIn(BaseModel):
    product_id: int
    packs: int = Field(ge=1)


class AddonIn(BaseModel):
    addon_id: int
    qty: int = Field(ge=1)


def _has_duplicates(ids: list[int]) -> bool:
    return len(ids) != len(set(ids))


class QuoteIn(BaseModel):
    event_date: date
    hours: int = Field(ge=1, le=24)
    guests: int = Field(ge=1)
    setup_at: AwareDatetime
    collect_at: AwareDatetime
    package_id: int | None = None
    overrides: dict[int, Annotated[int, Field(ge=0)]] | None = None  # product_id -> packs; 0 removes
    items: list[ItemIn] | None = Field(default=None, min_length=1)
    addons: list[AddonIn] = []
    area_id: int | None = None
    custom_area: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ] | None = None

    @model_validator(mode="after")
    def check_combinations(self) -> "QuoteIn":
        if self.collect_at <= self.setup_at:
            raise ValueError("collect_at must be after setup_at")
        if (self.package_id is None) == (self.items is None):
            raise ValueError("Provide exactly one of package_id or items")
        if self.overrides and self.package_id is None:
            raise ValueError("overrides require package_id")
        if (self.area_id is None) == (self.custom_area is None):
            raise ValueError("Provide exactly one of area_id or custom_area")
        # A repeated add-on would pass the capacity check once per line and could overbook.
        if _has_duplicates([a.addon_id for a in self.addons]):
            raise ValueError("Each add-on may appear only once")
        if self.items and _has_duplicates([i.product_id for i in self.items]):
            raise ValueError("Each product may appear only once")
        return self


class QuoteLineOut(_FromAttributes):
    product_id: int
    name_sw: str
    name_en: str
    unit: str
    packs: int
    unit_price: int
    line_total: int
    empties_deposit: int
    source: str


class AddonLineOut(_FromAttributes):
    addon_id: int
    name_sw: str
    name_en: str
    qty: int
    unit_price: int
    line_total: int
    available: int | None
    ok: bool


class QuoteFlagsOut(_FromAttributes):
    is_rush: bool
    below_minimum: bool
    min_order: int
    provisional: bool
    addons_unavailable: list[int]


class QuoteOut(_FromAttributes):
    lines: list[QuoteLineOut]
    addon_lines: list[AddonLineOut]
    subtotal: int
    addons_total: int
    delivery_fee: int
    delivery_custom: bool
    empties_deposit: int
    total: int
    deposit_due: int
    balance_due_date: date
    flags: QuoteFlagsOut


class PaymentInstructions(BaseModel):
    mpesa_till: str
    tigopesa_lipa: str
    airtel_lipa: str
    bank_details: str


class PublicSettingsOut(BaseModel):
    business_name: str
    whatsapp_number: str
    policy_text_sw: str
    policy_text_en: str
    payment_instructions: PaymentInstructions


def _normalised_phone(value: str) -> str:
    return normalise_phone(value)  # InvalidPhone is a ValueError, so this reports as a 422


class BookingIn(QuoteIn):
    event_type: Literal["wedding", "corporate", "birthday", "other"]
    start_time: time
    venue_id: int | None = None
    venue_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    venue_address: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] = ""
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    phone: Annotated[str, AfterValidator(_normalised_phone)]
    email: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, max_length=200, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$"
        ),
    ] = ""
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""
    lang: Literal["sw", "en"] = "sw"
    expected_total: int = Field(ge=0)
    accept_policy: Literal[True]
    age_confirmed: Literal[True]


class BookingCreatedOut(BaseModel):
    code: str
    status: str
    is_rush: bool
    provisional: bool
    total: int
    deposit_due: int
    balance_due_date: date
    payment_instructions: PaymentInstructions
    whatsapp_number: str


# Lookups accept any text up to these lengths: a badly formed phone must read as "not found".
class TrackIn(BaseModel):
    code: str = Field(max_length=40)
    phone: str = Field(max_length=40)


class PaymentIn(BaseModel):
    phone: str = Field(max_length=40)
    kind: Literal["deposit", "balance"]
    method: Literal["mpesa", "tigopesa", "airtel", "bank"]
    amount: int = Field(ge=1)
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class PaymentOut(_FromAttributes):
    kind: str
    amount: int
    method: str
    reference: str
    status: str
    created_at: datetime


class TrackedItemOut(BaseModel):
    name_sw: str
    name_en: str
    unit: str
    qty: int
    unit_price: int
    line_total: int


class TrackedAddonOut(BaseModel):
    name_sw: str
    name_en: str
    qty: int
    unit_price: int
    line_total: int


class TrackedBookingOut(BaseModel):
    code: str
    status: str
    is_rush: bool
    provisional: bool
    event_type: str
    event_date: date
    start_time: time
    hours: int
    guests: int
    venue_name: str
    venue_address: str
    items: list[TrackedItemOut]
    addons: list[TrackedAddonOut]
    subtotal: int
    addons_total: int
    delivery_fee: int
    empties_deposit: int
    total: int
    deposit_due: int
    balance_due_date: date
    amount_paid: int
    amount_pending: int
    balance_due: int
    payments: list[PaymentOut]
    payment_instructions: PaymentInstructions
