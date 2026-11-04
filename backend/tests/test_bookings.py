"""Booking service on the seeded SQLite catalog. Expected figures are hand-calculated."""

from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models import (
    Addon,
    Area,
    Booking,
    BookingStatusHistory,
    Customer,
    Package,
    Payment,
    PriceTier,
    Product,
    Setting,
    Venue,
)
from app.services.availability import EAT, today_eat
from app.services.bookings import (
    BookingClosed,
    BookingRejected,
    DuplicateReference,
    NewBooking,
    NewPayment,
    create_booking,
    find_booking,
    next_booking_code,
    payment_summary,
    submit_payment,
)
from app.services.pricing import QuoteError, QuoteRequest
from app.services.quoting import compute_quote

FAR_AHEAD = 30
PHONE = "255712345678"


async def quote_request(session, days=FAR_AHEAD, **overrides) -> QuoteRequest:
    """Silver, 300 guests, 5 hours, Masaki, 6 coolers."""
    silver = await session.scalar(select(Package.id).where(Package.slug == "silver"))
    masaki = await session.scalar(select(Area.id).where(Area.name == "Masaki"))
    cooler = await session.scalar(select(Addon.id).where(Addon.kind == "cooler"))
    event = today_eat() + timedelta(days=days)
    values = dict(
        event_date=event,
        hours=5,
        guests=300,
        setup_at=datetime(event.year, event.month, event.day, 15, tzinfo=EAT),
        collect_at=datetime(event.year, event.month, event.day, 15, tzinfo=EAT) + timedelta(hours=18),
        package_id=silver,
        addons=((cooler, 6),),
        area_id=masaki,
    )
    return QuoteRequest(**{**values, **overrides})


async def new_booking(session, req=None, expected_total=None, **overrides) -> NewBooking:
    req = req or await quote_request(session)
    if expected_total is None:
        expected_total = (await compute_quote(session, req)).total
    values = dict(
        request=req,
        expected_total=expected_total,
        event_type="wedding",
        start_time=time(16),
        name="Asha",
        phone=PHONE,
    )
    return NewBooking(**{**values, **overrides})


async def count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def with_lines(session, booking_id) -> Booking:
    return await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(selectinload(Booking.items), selectinload(Booking.addons))
        .execution_options(populate_existing=True)
    )


async def test_numbers_are_sequential_and_reset_each_year(seeded_session):
    assert await next_booking_code(seeded_session, year=2026) == "ED-2026-0001"
    assert await next_booking_code(seeded_session, year=2026) == "ED-2026-0002"
    assert await next_booking_code(seeded_session, year=2027) == "ED-2027-0001"
    assert await next_booking_code(seeded_session, year=2026) == "ED-2026-0003"


async def test_saved_totals_equal_the_quote(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    assert booking.subtotal == 1_385_500
    assert booking.addons_total == 90_000
    assert booking.delivery_fee == 25_000
    assert booking.empties_deposit == 306_000
    assert booking.total == 1_806_500
    assert booking.deposit_due == 903_250
    assert booking.balance_due_date == booking.event_date - timedelta(days=3)


async def test_booking_starts_at_request_with_confirmations(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    assert booking.code == f"ED-{today_eat().year}-0001"
    assert booking.status == "request"
    assert booking.age_confirmed is True
    assert booking.policy_accepted_at is not None
    assert booking.is_rush is False
    assert booking.lang == "sw"


async def test_first_history_row_is_written(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    rows = (await seeded_session.scalars(
        select(BookingStatusHistory).where(BookingStatusHistory.booking_id == booking.id)
    )).all()
    assert [(r.from_status, r.to_status, r.changed_by) for r in rows] == [(None, "request", None)]


async def test_prices_and_costs_are_snapshotted(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    coke = await seeded_session.scalar(select(Product).where(Product.name_en == "Coca-Cola 350ml"))

    coke.cost_price = 99_999
    for tier in (await seeded_session.scalars(
        select(PriceTier).where(PriceTier.product_id == coke.id)
    )).all():
        tier.unit_price = 77_777
    cooler = await seeded_session.scalar(select(Addon).where(Addon.kind == "cooler"))
    cooler.price = 55_555
    await seeded_session.commit()

    saved = await with_lines(seeded_session, booking.id)
    line = next(i for i in saved.items if i.product_id == coke.id)
    assert (line.qty, line.unit_price, line.unit_cost) == (10, 16_000, 13_000)
    assert [(a.addon_id, a.qty, a.unit_price) for a in saved.addons] == [(cooler.id, 6, 15_000)]
    assert saved.total == 1_806_500


async def test_rush_is_saved(seeded_session):
    req = await quote_request(seeded_session, days=2, addons=())
    booking = await create_booking(seeded_session, await new_booking(seeded_session, req))
    assert booking.is_rush is True


async def test_unlisted_area_is_saved_as_provisional(seeded_session):
    req = await quote_request(seeded_session, area_id=None, custom_area="Bagamoyo")
    booking = await create_booking(seeded_session, await new_booking(seeded_session, req))
    assert booking.delivery_fee == 0
    assert booking.delivery_fee_custom is True
    assert booking.custom_area == "Bagamoyo"
    assert booking.area_id is None
    assert booking.total == 1_806_500 - 25_000
    assert booking.deposit_due == (1_806_500 - 25_000 + 1) // 2


async def test_saved_venue_snapshots_name_and_address(seeded_session):
    venue = await seeded_session.scalar(select(Venue).where(Venue.name.like("%Masaki")))
    booking = await create_booking(
        seeded_session,
        await new_booking(seeded_session, venue_id=venue.id, venue_name="typed", venue_address="typed"),
    )
    assert booking.venue_id == venue.id
    assert booking.venue_name == venue.name
    assert booking.venue_address == venue.address


async def test_typed_venue_is_kept(seeded_session):
    booking = await create_booking(
        seeded_session, await new_booking(seeded_session, venue_name="Ukumbi", venue_address="Mtaa 1")
    )
    assert (booking.venue_id, booking.venue_name, booking.venue_address) == (None, "Ukumbi", "Mtaa 1")


async def test_venue_in_another_area_is_refused(seeded_session):
    venue = await seeded_session.scalar(select(Venue).where(Venue.name.like("%Mbezi Beach")))
    with pytest.raises(QuoteError):
        await create_booking(seeded_session, await new_booking(seeded_session, venue_id=venue.id))
    assert await count(seeded_session, Booking) == 0


async def test_unknown_venue_is_refused(seeded_session):
    with pytest.raises(QuoteError):
        await create_booking(seeded_session, await new_booking(seeded_session, venue_id=999_999))


async def test_same_phone_links_to_one_customer(seeded_session):
    first = await create_booking(seeded_session, await new_booking(seeded_session))
    second = await create_booking(seeded_session, await new_booking(seeded_session))
    assert first.customer_id == second.customer_id
    assert await count(seeded_session, Customer) == 1
    assert second.code.endswith("-0002")


async def test_repeat_booking_keeps_name_and_fills_a_blank_email(seeded_session):
    await create_booking(seeded_session, await new_booking(seeded_session))
    await create_booking(
        seeded_session, await new_booking(seeded_session, name="Someone Else", email="a@example.com")
    )
    customer = await seeded_session.scalar(select(Customer))
    assert (customer.name, customer.phone, customer.email) == ("Asha", PHONE, "a@example.com")


async def test_repeat_booking_never_overwrites_an_email(seeded_session):
    await create_booking(seeded_session, await new_booking(seeded_session, email="a@example.com"))
    await create_booking(seeded_session, await new_booking(seeded_session, email="b@example.com"))
    customer = await seeded_session.scalar(select(Customer))
    assert customer.email == "a@example.com"


async def assert_rejected(session, new: NewBooking, code: str):
    with pytest.raises(BookingRejected) as caught:
        await create_booking(session, new)
    assert caught.value.code == code
    assert await count(session, Booking) == 0
    assert await count(session, Customer) == 0
    return caught.value


async def test_unavailable_addon_saves_nothing(seeded_session):
    cooler = await seeded_session.scalar(select(Addon.id).where(Addon.kind == "cooler"))
    req = await quote_request(seeded_session, addons=((cooler, 21),))
    rejected = await assert_rejected(
        seeded_session, await new_booking(seeded_session, req), "addons_unavailable"
    )
    assert rejected.quote.flags.addons_unavailable == (cooler,)


async def test_below_minimum_saves_nothing(seeded_session):
    coke = await seeded_session.scalar(select(Product.id).where(Product.name_en == "Coca-Cola 350ml"))
    req = await quote_request(
        seeded_session, package_id=None, items=((coke, 1),), addons=()
    )
    await assert_rejected(seeded_session, await new_booking(seeded_session, req), "below_minimum")


async def test_exactly_the_minimum_is_accepted(seeded_session):
    setting = await seeded_session.get(Setting, "min_order")
    setting.value = "16500"
    await seeded_session.commit()
    coke = await seeded_session.scalar(select(Product.id).where(Product.name_en == "Coca-Cola 350ml"))
    req = await quote_request(
        seeded_session, package_id=None, items=((coke, 1),), addons=()
    )
    booking = await create_booking(seeded_session, await new_booking(seeded_session, req))
    assert booking.subtotal == 16_500


async def test_changed_total_saves_nothing(seeded_session):
    rejected = await assert_rejected(
        seeded_session,
        await new_booking(seeded_session, expected_total=1_806_499),
        "quote_changed",
    )
    assert rejected.quote.total == 1_806_500


def payment(**overrides) -> NewPayment:
    values = dict(kind="deposit", method="mpesa", amount=903_250, reference="abc123")
    return NewPayment(**{**values, **overrides})


@pytest.mark.parametrize("phone", ["0712345678", "255712345678", "+255 712 345 678"])
async def test_find_booking_accepts_every_phone_format(seeded_session, phone):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    found = await find_booking(seeded_session, booking.code, phone)
    assert found.id == booking.id


async def test_find_booking_ignores_case_and_spaces_in_the_number(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    found = await find_booking(seeded_session, f" {booking.code.lower()} ", PHONE)
    assert found.id == booking.id


@pytest.mark.parametrize("code_ok, phone", [(True, "0799999999"), (True, "nonsense"), (False, "0712345678")])
async def test_find_booking_returns_none_without_a_match(seeded_session, code_ok, phone):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    code = booking.code if code_ok else "ED-1999-0001"
    assert await find_booking(seeded_session, code, phone) is None


async def test_submit_payment_is_pending_with_a_clean_reference(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    saved = await submit_payment(seeded_session, booking, payment(reference="  abc123 "))
    assert (saved.status, saved.reference, saved.amount, saved.kind, saved.method) == (
        "pending", "ABC123", 903_250, "deposit", "mpesa",
    )


async def test_same_reference_is_refused_whatever_its_case(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    await submit_payment(seeded_session, booking, payment(reference="abc123"))
    with pytest.raises(DuplicateReference):
        await submit_payment(seeded_session, booking, payment(reference="ABC123 ", amount=5))


async def test_confirmed_reference_is_refused_too(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    saved = await submit_payment(seeded_session, booking, payment())
    saved.status = "confirmed"
    await seeded_session.commit()
    with pytest.raises(DuplicateReference):
        await submit_payment(seeded_session, booking, payment())


async def test_rejected_reference_can_be_sent_again(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    saved = await submit_payment(seeded_session, booking, payment())
    saved.status = "rejected"
    await seeded_session.commit()
    again = await submit_payment(seeded_session, booking, payment())
    assert again.status == "pending"


async def test_same_reference_on_another_booking_is_allowed(seeded_session):
    first = await create_booking(seeded_session, await new_booking(seeded_session))
    second = await create_booking(seeded_session, await new_booking(seeded_session))
    await submit_payment(seeded_session, first, payment())
    assert (await submit_payment(seeded_session, second, payment())).booking_id == second.id


async def test_database_index_stops_a_double_tap(seeded_session):
    """Two requests can both pass the read check; the index must still refuse the second."""
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    await submit_payment(seeded_session, booking, payment())
    seeded_session.add(
        Payment(booking_id=booking.id, kind="deposit", amount=1, method="mpesa", reference="ABC123")
    )
    with pytest.raises(IntegrityError):
        await seeded_session.commit()
    await seeded_session.rollback()


async def test_amount_above_the_balance_is_accepted(seeded_session):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    saved = await submit_payment(seeded_session, booking, payment(amount=99_000_000))
    assert saved.amount == 99_000_000


@pytest.mark.parametrize("status", ["cancelled", "closed"])
async def test_payment_refused_on_finished_bookings(seeded_session, status):
    booking = await create_booking(seeded_session, await new_booking(seeded_session))
    booking.status = status
    await seeded_session.commit()
    with pytest.raises(BookingClosed):
        await submit_payment(seeded_session, booking, payment())


def test_payment_summary_counts_only_confirmed_deposit_and_balance():
    payments = [
        Payment(kind="deposit", amount=400, status="confirmed"),
        Payment(kind="balance", amount=100, status="confirmed"),
        Payment(kind="balance", amount=50, status="pending"),
        Payment(kind="deposit", amount=70, status="rejected"),
        Payment(kind="refund", amount=30, status="confirmed"),
        Payment(kind="damage", amount=20, status="pending"),
    ]
    assert payment_summary(1000, payments) == (500, 50, 500)


def test_payment_summary_balance_never_goes_below_zero():
    payments = [Payment(kind="deposit", amount=1200, status="confirmed")]
    assert payment_summary(1000, payments) == (1200, 0, 0)


def test_payment_summary_with_nothing_paid():
    assert payment_summary(1000, []) == (0, 0, 1000)


async def test_order_with_no_drinks_is_refused(seeded_session):
    products = (await seeded_session.scalars(select(Product.id))).all()
    req = await quote_request(seeded_session, overrides={p: 0 for p in products})
    with pytest.raises(QuoteError):
        await create_booking(seeded_session, await new_booking(seeded_session, req))
    assert await count(seeded_session, Booking) == 0
