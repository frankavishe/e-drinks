"""Turn a quote into a saved booking. Nothing is written unless the server's own quote is valid."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Booking,
    BookingAddon,
    BookingItem,
    BookingStatusHistory,
    Customer,
    Payment,
    Product,
    Venue,
)
from app.services.availability import today_eat
from app.services.phone import InvalidPhone, normalise_phone
from app.services.pricing import Quote, QuoteError, QuoteRequest
from app.services.quoting import compute_quote


class BookingRejected(Exception):
    """The order can't be saved as reviewed. Carries the current quote to show the customer."""

    def __init__(self, code: str, quote: Quote) -> None:
        super().__init__(code)
        self.code = code  # addons_unavailable | below_minimum | quote_changed
        self.quote = quote


@dataclass(frozen=True)
class NewBooking:
    request: QuoteRequest
    expected_total: int
    event_type: str
    start_time: time
    name: str
    phone: str  # already normalised
    email: str = ""
    notes: str = ""
    lang: str = "sw"
    venue_id: int | None = None
    venue_name: str = ""
    venue_address: str = ""


@dataclass(frozen=True)
class NewPayment:
    kind: str
    method: str
    amount: int
    reference: str


class DuplicateReference(Exception):
    """This reference is already pending or confirmed on the booking."""


class BookingClosed(Exception):
    """The booking is cancelled or closed, so it takes no more payments."""


FINISHED_STATUSES = ("cancelled", "closed")
ORDER_PAYMENT_KINDS = ("deposit", "balance")

_NEXT_NUMBER = text(
    "INSERT INTO booking_counters (year, last_no) VALUES (:year, 1) "
    "ON CONFLICT (year) DO UPDATE SET last_no = booking_counters.last_no + 1 "
    "RETURNING last_no"
)

_ADD_CUSTOMER = text(
    "INSERT INTO customers (name, phone, email) VALUES (:name, :phone, :email) "
    "ON CONFLICT (phone) DO NOTHING"
)


async def next_booking_code(session: AsyncSession, year: int | None = None) -> str:
    """Atomic within the caller's transaction, so concurrent bookings can't share a number."""
    year = year or today_eat().year
    number = (await session.execute(_NEXT_NUMBER, {"year": year})).scalar_one()
    return f"ED-{year}-{number:04d}"


def _check_bookable(quote: Quote, expected_total: int) -> None:
    if not quote.lines:
        raise QuoteError("The order has no drinks")
    if quote.flags.addons_unavailable:
        raise BookingRejected("addons_unavailable", quote)
    if quote.flags.below_minimum:
        raise BookingRejected("below_minimum", quote)
    if quote.total != expected_total:
        raise BookingRejected("quote_changed", quote)


async def _venue_details(session: AsyncSession, new: NewBooking) -> tuple[str, str]:
    if new.venue_id is None:
        return new.venue_name, new.venue_address
    venue = await session.get(Venue, new.venue_id)
    if venue is None or venue.area_id != new.request.area_id:
        raise QuoteError(f"Venue {new.venue_id} is not in the chosen area")
    return venue.name, venue.address


async def _customer(session: AsyncSession, new: NewBooking) -> Customer:
    """One record per phone. No account proves who owns a phone, so existing details are kept."""
    await session.execute(_ADD_CUSTOMER, {"name": new.name, "phone": new.phone, "email": new.email})
    customer = await session.scalar(select(Customer).where(Customer.phone == new.phone))
    if not customer.email:
        customer.email = new.email
    return customer


async def create_booking(session: AsyncSession, new: NewBooking) -> Booking:
    """Re-price on the server and save in one transaction.

    Raises BookingRejected, QuoteError or CatalogError, having written nothing.
    """
    req = new.request
    quote = await compute_quote(session, req)
    _check_bookable(quote, new.expected_total)
    venue_name, venue_address = await _venue_details(session, new)

    product_ids = [line.product_id for line in quote.lines]
    costs = dict(
        (await session.execute(
            select(Product.id, Product.cost_price).where(Product.id.in_(product_ids))
        )).all()
    )

    customer = await _customer(session, new)
    booking = Booking(
        code=await next_booking_code(session),
        customer_id=customer.id,
        lang=new.lang,
        event_type=new.event_type,
        event_date=req.event_date,
        start_time=new.start_time,
        hours=req.hours,
        guests=req.guests,
        package_id=req.package_id,
        venue_id=new.venue_id,
        venue_name=venue_name,
        venue_address=venue_address,
        area_id=req.area_id,
        custom_area=req.custom_area or "",
        setup_at=req.setup_at,
        collect_at=req.collect_at,
        status="request",
        is_rush=quote.flags.is_rush,
        subtotal=quote.subtotal,
        addons_total=quote.addons_total,
        delivery_fee=quote.delivery_fee,
        delivery_fee_custom=quote.delivery_custom,
        empties_deposit=quote.empties_deposit,
        total=quote.total,
        deposit_due=quote.deposit_due,
        balance_due_date=quote.balance_due_date,
        policy_accepted_at=datetime.now(timezone.utc),
        age_confirmed=True,
        notes=new.notes,
        items=[
            BookingItem(
                product_id=line.product_id,
                qty=line.packs,
                unit_price=line.unit_price,
                unit_cost=costs[line.product_id],
            )
            for line in quote.lines
        ],
        addons=[
            BookingAddon(addon_id=line.addon_id, qty=line.qty, unit_price=line.unit_price)
            for line in quote.addon_lines
        ],
        history=[BookingStatusHistory(from_status=None, to_status="request")],
    )
    session.add(booking)
    await session.commit()
    return booking


async def find_booking(session: AsyncSession, code: str, phone: str) -> Booking | None:
    """The booking only if both the number and the phone match. Callers can't tell which failed."""
    try:
        normalised = normalise_phone(phone)
    except InvalidPhone:
        return None
    return await session.scalar(
        select(Booking)
        .join(Booking.customer)
        .where(Booking.code == code.strip().upper(), Customer.phone == normalised)
        .options(
            selectinload(Booking.customer),
            selectinload(Booking.items).selectinload(BookingItem.product),
            selectinload(Booking.addons).selectinload(BookingAddon.addon),
            selectinload(Booking.payments),
        )
        .execution_options(populate_existing=True)
    )


async def _reference_in_use(session: AsyncSession, booking_id: int, reference: str) -> bool:
    stmt = select(Payment.id).where(
        Payment.booking_id == booking_id,
        Payment.reference == reference,
        Payment.status != "rejected",
    )
    return await session.scalar(stmt) is not None


async def submit_payment(session: AsyncSession, booking: Booking, new: NewPayment) -> Payment:
    """Save a pending payment for admin to confirm. The amount is the customer's claim, not checked."""
    if booking.status in FINISHED_STATUSES:
        raise BookingClosed(booking.code)
    reference = new.reference.strip().upper()
    if await _reference_in_use(session, booking.id, reference):
        raise DuplicateReference(reference)

    payment = Payment(
        booking_id=booking.id,
        kind=new.kind,
        method=new.method,
        amount=new.amount,
        reference=reference,
        status="pending",
    )
    session.add(payment)
    try:
        await session.commit()
    except IntegrityError as exc:  # a double-tap got past the check above
        await session.rollback()
        raise DuplicateReference(reference) from exc
    await session.refresh(payment)
    return payment


def payment_summary(total: int, payments: Iterable[Payment]) -> tuple[int, int, int]:
    """(paid, pending, balance due). Derived from the records, never stored."""
    towards_order = [p for p in payments if p.kind in ORDER_PAYMENT_KINDS]
    paid = sum(p.amount for p in towards_order if p.status == "confirmed")
    pending = sum(p.amount for p in towards_order if p.status == "pending")
    return paid, pending, max(total - paid, 0)
