import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.catalog import Addon, Product

BOOKING_STATUSES = (
    "request",
    "quoted",
    "confirmed",
    "fully_paid",
    "delivered",
    "returns_settled",
    "closed",
    "cancelled",
)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)  # = auth.users.id
    role: Mapped[str] = mapped_column(String(20))  # owner | staff | planner
    name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    business_name: Mapped[str] = mapped_column(String(120), default="")
    planner_status: Mapped[str | None] = mapped_column(String(20))  # pending | approved | rejected
    commission_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))  # percent, e.g. 7.50
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # 255XXXXXXXXX
    email: Mapped[str] = mapped_column(String(200), default="")


class BookingCounter(Base):
    """Last booking number issued per year, for ED-YYYY-NNNN."""

    __tablename__ = "booking_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_no: Mapped[int] = mapped_column(Integer)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # ED-YYYY-NNNN
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    planner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("profiles.id"))
    lang: Mapped[str] = mapped_column(String(2), default="sw")
    event_type: Mapped[str] = mapped_column(String(40))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    hours: Mapped[int] = mapped_column(Integer)
    guests: Mapped[int] = mapped_column(Integer)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id"))
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    venue_name: Mapped[str] = mapped_column(String(160), default="")
    venue_address: Mapped[str] = mapped_column(String(255), default="")
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"))
    custom_area: Mapped[str] = mapped_column(String(120), default="")  # area not on the list
    setup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collect_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="request", index=True)
    is_rush: Mapped[bool] = mapped_column(Boolean, default=False)
    rush_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    date_changes_used: Mapped[int] = mapped_column(Integer, default=0)
    # totals snapshot (TZS)
    subtotal: Mapped[int] = mapped_column(BigInteger, default=0)
    addons_total: Mapped[int] = mapped_column(BigInteger, default=0)
    delivery_fee: Mapped[int] = mapped_column(BigInteger, default=0)
    delivery_fee_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    empties_deposit: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    deposit_due: Mapped[int] = mapped_column(BigInteger, default=0)
    balance_due_date: Mapped[date | None] = mapped_column(Date)
    efd_receipt_no: Mapped[str] = mapped_column(String(60), default="")
    policy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")  # what the customer typed
    internal_notes: Mapped[str] = mapped_column(Text, default="", server_default="")  # staff only
    refund_due: Mapped[int | None] = mapped_column(BigInteger)  # fixed when cancelled
    client_name: Mapped[str] = mapped_column(String(120), default="")  # planner's named client
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped[Customer] = relationship()
    items: Mapped[list["BookingItem"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
    addons: Mapped[list["BookingAddon"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", order_by="Payment.id"
    )
    history: Mapped[list["BookingStatusHistory"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", order_by="BookingStatusHistory.id"
    )


class BookingItem(Base):
    __tablename__ = "booking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    unit_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    qty_delivered: Mapped[int] = mapped_column(Integer, default=0)
    qty_returned: Mapped[int] = mapped_column(Integer, default=0)  # sealed, sale-or-return
    empties_out: Mapped[int] = mapped_column(Integer, default=0)
    empties_back: Mapped[int] = mapped_column(Integer, default=0)

    booking: Mapped[Booking] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class BookingAddon(Base):
    __tablename__ = "booking_addons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    addon_id: Mapped[int] = mapped_column(ForeignKey("addons.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    qty_lost_damaged: Mapped[int] = mapped_column(Integer, default=0)

    booking: Mapped[Booking] = relationship(back_populates="addons")
    addon: Mapped[Addon] = relationship()


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="history")


_LIVE_REFERENCE = "reference <> '' AND status <> 'rejected'"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # A reference counts once per booking, even for a double-tap; rejected ones may be retried.
        Index(
            "uq_payments_booking_reference",
            "booking_id",
            "reference",
            unique=True,
            postgresql_where=text(_LIVE_REFERENCE),
            sqlite_where=text(_LIVE_REFERENCE),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # deposit | balance | refund | damage
    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(20))  # mpesa | tigopesa | airtel | bank | cash
    reference: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|confirmed|rejected
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="payments")


class StockLevel(Base):
    __tablename__ = "stock_levels"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))  # purchase|reserve|release|deliver|return|adjust
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"))
    unit_cost: Mapped[int | None] = mapped_column(BigInteger)
    supplier: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseNeed(Base):
    """Shortfall line on the purchase list: stock to buy before needed_by."""

    __tablename__ = "purchase_needs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    qty: Mapped[int] = mapped_column(Integer)
    needed_by: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | bought | cancelled


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    planner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|earned|paid
    earned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
