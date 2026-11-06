"""Admin API shapes (contracts/admin-api.md).

Staff and owner have separate classes. A field missing from the staff class can't reach staff, so cost,
margin and profit belong only on the owner classes.
"""

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Stage = Literal[
    "request", "quoted", "confirmed", "fully_paid", "delivered", "returns_settled", "closed", "cancelled"
]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    name: str


class BookingRow(BaseModel):
    id: int
    code: str
    status: str
    is_rush: bool
    rush_approved: bool
    provisional: bool
    event_type: str
    event_date: date
    start_time: time
    guests: int
    customer_name: str
    customer_phone: str
    venue_name: str
    total: int
    amount_paid: int
    amount_pending: int


class OverviewOut(BaseModel):
    today: list[BookingRow]
    upcoming: list[BookingRow]


class BookingListOut(BaseModel):
    total: int
    items: list[BookingRow]


class AdminItemOut(BaseModel):
    name_sw: str
    name_en: str
    unit: str
    qty: int
    unit_price: int
    line_total: int


class AdminAddonOut(BaseModel):
    name_sw: str
    name_en: str
    qty: int
    unit_price: int
    line_total: int


class AdminPaymentOut(BaseModel):
    id: int
    kind: str
    method: str
    amount: int
    reference: str
    status: str
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    created_at: datetime


class HistoryOut(BaseModel):
    from_status: str | None
    to_status: str
    changed_by_name: str | None
    note: str
    created_at: datetime


class MoveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    to: str
    allowed: bool
    reason: str | None
    back: bool


class BookingDetailOut(BookingRow):
    """What staff see."""

    customer_email: str
    hours: int
    venue_address: str
    custom_area: str
    lang: str
    setup_at: datetime
    collect_at: datetime
    notes: str
    internal_notes: str
    efd_receipt_no: str
    date_changes_used: int
    balance_due_date: date | None
    balance_due: int
    subtotal: int
    addons_total: int
    delivery_fee: int
    empties_deposit: int
    deposit_due: int
    refund_due: int | None
    refunded: int
    items: list[AdminItemOut]
    addons: list[AdminAddonOut]
    payments: list[AdminPaymentOut]
    history: list[HistoryOut]
    allowed_moves: list[MoveOut]


class FinancialsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    goods_total: int
    revenue: int
    profit: int


class BookingOwnerOut(BookingDetailOut):
    """What the owner sees: the staff view, plus the money behind it."""

    financials: FinancialsOut


# The owner class comes first: it needs `financials`, so a staff response can only match the other.
BookingResponse = BookingOwnerOut | BookingDetailOut


class BookingPatch(BaseModel):
    efd_receipt_no: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    internal_notes: Annotated[str, Field(max_length=5000)] | None = None


Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class StageIn(BaseModel):
    to: Stage
    note: Note = ""


class CancelIn(BaseModel):
    note: Note = ""


class CancelPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    days_ahead: int
    paid: int
    refund_due: int


class DateChangeIn(BaseModel):
    new_date: date
    exception: bool = False
    note: Note = ""


class RushIn(BaseModel):
    approve: bool
    note: Note = ""


class DeliveryFeeIn(BaseModel):
    fee: int = Field(ge=0)


class RefundIn(BaseModel):
    amount: int = Field(ge=1)
    method: Literal["mpesa", "tigopesa", "airtel", "bank", "cash"]
    reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""


class CalendarBooking(BaseModel):
    id: int
    code: str
    status: str
    is_rush: bool
    customer_name: str
    start_time: time


class CalendarAddon(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    addon_id: int
    name_sw: str
    name_en: str
    committed: int
    owned: int | None


class CalendarDay(BaseModel):
    date: date
    bookings: list[CalendarBooking]
    addons: list[CalendarAddon]


class CalendarOut(BaseModel):
    days: list[CalendarDay]
