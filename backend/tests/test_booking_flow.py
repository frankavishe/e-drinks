"""Stage rules, payments, cancellation, date changes, rush and delivery fee on the seeded catalog."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Addon, Booking, Payment, Profile
from app.services.admin_queries import load_booking
from app.services.availability import today_eat
from app.services.booking_flow import (
    NewRefund,
    StageRefused,
    add_refund,
    allowed_moves,
    cancel_booking,
    cancel_preview,
    change_date,
    confirm_payment,
    decide_rush,
    move_stage,
    reject_payment,
    set_delivery_fee,
)
from app.services.bookings import create_booking, payment_summary
from tests.test_bookings import new_booking, quote_request


@pytest.fixture
async def staff(seeded_session) -> Profile:
    profile = Profile(id=uuid.uuid4(), role="staff", name="Amina")
    seeded_session.add(profile)
    await seeded_session.commit()
    return profile


@pytest.fixture
async def owner(seeded_session) -> Profile:
    profile = Profile(id=uuid.uuid4(), role="owner", name="Frank")
    seeded_session.add(profile)
    await seeded_session.commit()
    return profile


async def book(session, days=30, status="request", **quote_overrides) -> Booking:
    req = await quote_request(session, days=days, **quote_overrides)
    created = await create_booking(session, await new_booking(session, req))
    created.status = status
    await session.commit()
    return await load_booking(session, created.id)


async def reload(session, booking: Booking) -> Booking:
    return await load_booking(session, booking.id)


async def pay(session, booking: Booking, amount: int, status="confirmed", reference=None) -> Booking:
    session.add(Payment(
        booking_id=booking.id, kind="deposit", method="mpesa", amount=amount,
        reference=reference or uuid.uuid4().hex[:12].upper(), status=status,
    ))
    await session.commit()
    return await reload(session, booking)


async def refused(code: str, call) -> None:
    with pytest.raises(StageRefused) as caught:
        await call
    assert caught.value.code == code


async def set_cooler_capacity(session, capacity: int) -> None:
    cooler = await session.scalar(select(Addon).where(Addon.kind == "cooler"))
    cooler.owned_capacity = capacity
    await session.commit()


# --- Forward moves ---


async def test_request_can_move_to_quoted(seeded_session, staff):
    booking = await book(seeded_session)
    await move_stage(seeded_session, booking, "quoted", staff)
    assert (await reload(seeded_session, booking)).status == "quoted"


@pytest.mark.parametrize("start", ["request", "quoted"])
async def test_deposit_allows_the_move_to_confirmed(seeded_session, staff, start):
    booking = await book(seeded_session, status=start)
    booking = await pay(seeded_session, booking, booking.deposit_due)
    await move_stage(seeded_session, booking, "confirmed", staff)
    assert (await reload(seeded_session, booking)).status == "confirmed"


async def test_confirmed_is_refused_without_a_deposit(seeded_session, staff):
    booking = await book(seeded_session)
    await refused("deposit_not_paid", move_stage(seeded_session, booking, "confirmed", staff))
    assert (await reload(seeded_session, booking)).status == "request"


async def test_confirmed_is_refused_one_shilling_short(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, booking.deposit_due - 1)
    await refused("deposit_not_paid", move_stage(seeded_session, booking, "confirmed", staff))


async def test_pending_payments_do_not_count_towards_the_deposit(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, booking.deposit_due, status="pending")
    await refused("deposit_not_paid", move_stage(seeded_session, booking, "confirmed", staff))


async def test_fully_paid_needs_the_whole_total(seeded_session, staff):
    booking = await book(seeded_session, status="confirmed")
    booking = await pay(seeded_session, booking, booking.total - 1)
    await refused("not_fully_paid", move_stage(seeded_session, booking, "fully_paid", staff))
    booking = await pay(seeded_session, booking, 1)
    await move_stage(seeded_session, booking, "fully_paid", staff)
    assert (await reload(seeded_session, booking)).status == "fully_paid"


@pytest.mark.parametrize(
    ("start", "to"),
    [("fully_paid", "delivered"), ("delivered", "returns_settled"), ("returns_settled", "closed")],
)
async def test_later_stages_move_in_order(seeded_session, staff, start, to):
    booking = await book(seeded_session, status=start)
    await move_stage(seeded_session, booking, to, staff)
    assert (await reload(seeded_session, booking)).status == to


@pytest.mark.parametrize(
    ("start", "to"),
    [
        ("request", "fully_paid"),
        ("request", "delivered"),
        ("request", "closed"),
        ("quoted", "request"),
        ("quoted", "fully_paid"),
        ("confirmed", "delivered"),
        ("confirmed", "quoted"),
        ("fully_paid", "returns_settled"),
        ("delivered", "closed"),
        ("returns_settled", "request"),
        ("closed", "returns_settled"),
        ("closed", "request"),
        ("cancelled", "request"),
        ("cancelled", "confirmed"),
        ("request", "request"),
        ("request", "cancelled"),  # cancelling has its own action
        ("confirmed", "nonsense"),
    ],
)
async def test_other_moves_are_invalid(seeded_session, owner, start, to):
    booking = await book(seeded_session, status=start)
    await refused("invalid_move", move_stage(seeded_session, booking, to, owner, note="x"))


# --- Rush, provisional and capacity gates on Confirmed ---


async def test_unapproved_rush_cannot_be_confirmed(seeded_session, staff):
    booking = await book(seeded_session, days=1)
    assert booking.is_rush
    booking = await pay(seeded_session, booking, booking.deposit_due)
    await refused("rush_not_approved", move_stage(seeded_session, booking, "confirmed", staff))


async def test_approved_rush_proceeds_like_a_normal_booking(seeded_session, staff):
    booking = await book(seeded_session, days=1)
    booking = await pay(seeded_session, booking, booking.deposit_due)
    await decide_rush(seeded_session, booking, True, staff)
    booking = await reload(seeded_session, booking)
    assert booking.rush_approved
    await move_stage(seeded_session, booking, "confirmed", staff)
    assert (await reload(seeded_session, booking)).status == "confirmed"


async def provisional(session, **kwargs) -> Booking:
    return await book(session, area_id=None, custom_area="Bagamoyo", **kwargs)


@pytest.mark.parametrize("to", ["quoted", "confirmed"])
async def test_provisional_bookings_cannot_move_forward(seeded_session, staff, to):
    booking = await provisional(seeded_session)
    booking = await pay(seeded_session, booking, booking.total)
    await refused("provisional", move_stage(seeded_session, booking, to, staff))


async def test_confirmed_is_refused_when_add_ons_have_gone(seeded_session, staff):
    await set_cooler_capacity(seeded_session, 6)
    first = await book(seeded_session)
    second = await book(seeded_session)  # both quoted fine: neither holds anything yet
    first = await pay(seeded_session, first, first.deposit_due)
    second = await pay(seeded_session, second, second.deposit_due)
    await move_stage(seeded_session, first, "confirmed", staff)
    await refused("addons_unavailable", move_stage(seeded_session, second, "confirmed", staff))


async def test_confirmed_is_allowed_for_add_ons_on_another_date(seeded_session, staff):
    await set_cooler_capacity(seeded_session, 6)
    first = await book(seeded_session, days=30)
    second = await book(seeded_session, days=40)
    first = await pay(seeded_session, first, first.deposit_due)
    second = await pay(seeded_session, second, second.deposit_due)
    await move_stage(seeded_session, first, "confirmed", staff)
    await move_stage(seeded_session, second, "confirmed", staff)
    assert (await reload(seeded_session, second)).status == "confirmed"


# --- Moving back ---


BACK_MOVES = [
    ("confirmed", "request"),
    ("fully_paid", "confirmed"),
    ("delivered", "fully_paid"),
    ("returns_settled", "delivered"),
]


@pytest.mark.parametrize(("start", "to"), BACK_MOVES)
async def test_owner_can_move_back_with_a_note(seeded_session, owner, start, to):
    booking = await book(seeded_session, status=start)
    await move_stage(seeded_session, booking, to, owner, note="Wrong payment")
    booking = await reload(seeded_session, booking)
    assert booking.status == to
    assert booking.history[-1].note == "Wrong payment"


@pytest.mark.parametrize(("start", "to"), BACK_MOVES)
async def test_staff_cannot_move_back(seeded_session, staff, start, to):
    booking = await book(seeded_session, status=start)
    await refused("owner_only", move_stage(seeded_session, booking, to, staff, note="Please"))


@pytest.mark.parametrize("note", ["", "   "])
async def test_moving_back_needs_a_note(seeded_session, owner, note):
    booking = await book(seeded_session, status="confirmed")
    await refused("note_required", move_stage(seeded_session, booking, "request", owner, note=note))


# --- History ---


async def test_every_move_records_stage_time_and_actor(seeded_session, staff):
    booking = await book(seeded_session)
    await move_stage(seeded_session, booking, "quoted", staff, note="Sent by WhatsApp")
    row = (await reload(seeded_session, booking)).history[-1]
    assert (row.from_status, row.to_status) == ("request", "quoted")
    assert row.changed_by == staff.id
    assert row.note == "Sent by WhatsApp"
    assert row.created_at is not None


async def test_a_refused_move_records_nothing(seeded_session, staff):
    booking = await book(seeded_session)
    before = len(booking.history)
    await refused("deposit_not_paid", move_stage(seeded_session, booking, "confirmed", staff))
    assert len((await reload(seeded_session, booking)).history) == before


# --- allowed_moves agrees with enforcement ---


async def _as_map(session, booking, role_profile):
    return {m.to: m for m in await allowed_moves(session, booking, role_profile)}


async def test_allowed_moves_gives_the_reason(seeded_session, staff):
    booking = await book(seeded_session)
    moves = await _as_map(seeded_session, booking, staff)
    assert set(moves) == {"quoted", "confirmed"}
    assert moves["quoted"].allowed is True and moves["quoted"].reason is None
    assert moves["confirmed"].allowed is False and moves["confirmed"].reason == "deposit_not_paid"
    assert not moves["confirmed"].back


async def test_allowed_moves_marks_back_moves_owner_only(seeded_session, staff, owner):
    booking = await book(seeded_session, status="confirmed")
    as_staff = await _as_map(seeded_session, booking, staff)
    as_owner = await _as_map(seeded_session, booking, owner)
    assert as_staff["request"].back and as_staff["request"].reason == "owner_only"
    assert as_owner["request"].back and as_owner["request"].allowed


@pytest.mark.parametrize("status", ["closed", "cancelled"])
async def test_finished_bookings_have_no_moves(seeded_session, owner, status):
    booking = await book(seeded_session, status=status)
    assert await allowed_moves(seeded_session, booking, owner) == []


@pytest.mark.parametrize(
    "start", ["request", "quoted", "confirmed", "fully_paid", "delivered", "returns_settled"]
)
@pytest.mark.parametrize("paid", ["nothing", "deposit", "all"])
async def test_allowed_moves_matches_what_moving_does(seeded_session, staff, owner, start, paid):
    """Whatever the listing says, actually moving must agree, for both roles."""
    booking = await book(seeded_session, status=start)
    amounts = {"nothing": 0, "deposit": booking.deposit_due, "all": booking.total}
    if amounts[paid]:
        booking = await pay(seeded_session, booking, amounts[paid])
    for actor in (staff, owner):
        for move in await allowed_moves(seeded_session, booking, actor):
            if move.allowed:
                await move_stage(seeded_session, booking, move.to, actor, note="n")
                booking = await reload(seeded_session, booking)
                booking.status = start
                await seeded_session.commit()
                booking = await reload(seeded_session, booking)
            else:
                await refused(move.reason, move_stage(seeded_session, booking, move.to, actor, note="n"))


# --- Confirming and rejecting payments ---


async def test_confirm_records_who_and_when_and_updates_paid(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    await confirm_payment(seeded_session, booking, booking.payments[0], staff)
    booking = await reload(seeded_session, booking)
    payment = booking.payments[0]
    assert payment.status == "confirmed"
    assert payment.confirmed_by == staff.id
    assert payment.confirmed_at is not None
    assert payment_summary(booking.total, booking.payments)[0] == 1000


async def test_second_confirm_takes_no_effect(seeded_session, staff, owner):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    await confirm_payment(seeded_session, booking, booking.payments[0], staff)
    booking = await reload(seeded_session, booking)
    await refused("already_confirmed", confirm_payment(seeded_session, booking, booking.payments[0], owner))
    booking = await reload(seeded_session, booking)
    assert booking.payments[0].confirmed_by == staff.id
    assert payment_summary(booking.total, booking.payments)[0] == 1000


async def test_rejected_payment_cannot_be_confirmed(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    await reject_payment(seeded_session, booking, booking.payments[0], staff)
    booking = await reload(seeded_session, booking)
    await refused("already_rejected", confirm_payment(seeded_session, booking, booking.payments[0], staff))


async def test_reject_pending_records_who(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    await reject_payment(seeded_session, booking, booking.payments[0], staff)
    payment = (await reload(seeded_session, booking)).payments[0]
    assert payment.status == "rejected"
    assert payment.confirmed_by == staff.id
    assert payment.confirmed_at is not None


async def test_reject_twice_is_refused(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    await reject_payment(seeded_session, booking, booking.payments[0], staff)
    booking = await reload(seeded_session, booking)
    await refused("already_rejected", reject_payment(seeded_session, booking, booking.payments[0], staff))


async def test_reject_confirmed_is_allowed_when_the_stage_does_not_need_it(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000)
    await reject_payment(seeded_session, booking, booking.payments[0], staff)
    booking = await reload(seeded_session, booking)
    assert payment_summary(booking.total, booking.payments)[0] == 0


async def test_reject_is_refused_when_confirmed_relies_on_it(seeded_session, staff):
    booking = await book(seeded_session, status="confirmed")
    booking = await pay(seeded_session, booking, booking.deposit_due)
    await refused("payment_needed_by_stage", reject_payment(seeded_session, booking, booking.payments[0], staff))
    assert (await reload(seeded_session, booking)).payments[0].status == "confirmed"


@pytest.mark.parametrize("status", ["fully_paid", "delivered", "returns_settled"])
async def test_reject_is_refused_when_later_stages_rely_on_it(seeded_session, staff, status):
    booking = await book(seeded_session, status=status)
    booking = await pay(seeded_session, booking, booking.total)
    await refused("payment_needed_by_stage", reject_payment(seeded_session, booking, booking.payments[0], staff))


async def test_reject_is_allowed_when_other_payments_still_cover_the_stage(seeded_session, staff):
    booking = await book(seeded_session, status="confirmed")
    booking = await pay(seeded_session, booking, booking.deposit_due)
    booking = await pay(seeded_session, booking, 5000)
    extra = next(p for p in booking.payments if p.amount == 5000)
    await reject_payment(seeded_session, booking, extra, staff)
    assert next(
        p for p in (await reload(seeded_session, booking)).payments if p.amount == 5000
    ).status == "rejected"


async def test_reject_works_after_the_owner_moves_back(seeded_session, staff, owner):
    booking = await book(seeded_session, status="confirmed")
    booking = await pay(seeded_session, booking, booking.deposit_due)
    await move_stage(seeded_session, booking, "request", owner, note="Reference was wrong")
    booking = await reload(seeded_session, booking)
    await reject_payment(seeded_session, booking, booking.payments[0], staff)
    assert (await reload(seeded_session, booking)).payments[0].status == "rejected"


@pytest.mark.parametrize("status", ["cancelled", "closed"])
async def test_order_payments_are_frozen_on_finished_bookings(seeded_session, staff, status):
    booking = await book(seeded_session, status=status)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    booking = await pay(seeded_session, booking, 2000)
    pending = next(p for p in booking.payments if p.status == "pending")
    confirmed = next(p for p in booking.payments if p.status == "confirmed")
    await refused("booking_finished", confirm_payment(seeded_session, booking, pending, staff))
    await refused("booking_finished", reject_payment(seeded_session, booking, confirmed, staff))


# --- Cancelling ---


@pytest.mark.parametrize(
    ("days", "share"), [(20, 0.9), (14, 0.9), (13, 0.5), (10, 0.5), (7, 0.5), (6, 0), (3, 0)]
)
async def test_cancel_fixes_the_refund_by_policy(seeded_session, staff, days, share):
    booking = await book(seeded_session, days=days)
    booking = await pay(seeded_session, booking, 100_000)
    await cancel_booking(seeded_session, booking, staff, note="Customer called")
    booking = await reload(seeded_session, booking)
    assert booking.status == "cancelled"
    assert booking.refund_due == int(100_000 * share)
    last = booking.history[-1]
    assert (last.to_status, last.changed_by, last.note) == ("cancelled", staff.id, "Customer called")


async def test_cancel_with_nothing_paid_owes_nothing(seeded_session, staff):
    booking = await book(seeded_session)
    await cancel_booking(seeded_session, booking, staff)
    assert (await reload(seeded_session, booking)).refund_due == 0


async def test_cancel_returns_the_balance_in_full(seeded_session, staff):
    booking = await book(seeded_session, days=10, status="fully_paid")
    booking = await pay(seeded_session, booking, booking.total)
    await cancel_booking(seeded_session, booking, staff)
    booking = await reload(seeded_session, booking)
    assert booking.refund_due == booking.deposit_due // 2 + booking.total - booking.deposit_due


@pytest.mark.parametrize("status", ["request", "quoted", "confirmed", "fully_paid", "delivered", "returns_settled"])
async def test_cancel_is_allowed_from_any_live_stage(seeded_session, staff, status):
    booking = await book(seeded_session, status=status)
    await cancel_booking(seeded_session, booking, staff)
    assert (await reload(seeded_session, booking)).status == "cancelled"


@pytest.mark.parametrize("status", ["closed", "cancelled"])
async def test_cancel_is_refused_when_finished(seeded_session, staff, status):
    booking = await book(seeded_session, status=status)
    await refused("booking_finished", cancel_booking(seeded_session, booking, staff))


async def test_cancel_is_refused_with_a_payment_pending(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 1000, status="pending")
    await refused("pending_payments", cancel_booking(seeded_session, booking, staff))
    assert (await reload(seeded_session, booking)).status == "request"


async def test_refund_stays_fixed_after_cancelling(seeded_session, staff):
    booking = await book(seeded_session, days=20)
    booking = await pay(seeded_session, booking, 100_000)
    await cancel_booking(seeded_session, booking, staff)
    booking = await reload(seeded_session, booking)
    booking.event_date = today_eat() + timedelta(days=1)  # time passing must not change what's owed
    await seeded_session.commit()
    assert (await reload(seeded_session, booking)).refund_due == 90_000


async def test_cancel_preview_matches_cancelling(seeded_session, staff):
    booking = await book(seeded_session, days=10)
    booking = await pay(seeded_session, booking, 100_000)
    preview = cancel_preview(booking)
    assert (preview.days_ahead, preview.paid, preview.refund_due) == (10, 100_000, 50_000)
    await cancel_booking(seeded_session, booking, staff)
    assert (await reload(seeded_session, booking)).refund_due == preview.refund_due


async def test_cancel_preview_is_refused_when_finished(seeded_session):
    booking = await book(seeded_session, status="cancelled")
    with pytest.raises(StageRefused) as caught:
        cancel_preview(booking)
    assert caught.value.code == "booking_finished"


# --- Refund records ---


async def cancelled_with_refund(session, staff, days=20, paid=100_000) -> Booking:
    booking = await book(session, days=days)
    booking = await pay(session, booking, paid)
    await cancel_booking(session, booking, staff)
    return await reload(session, booking)


async def test_refund_record_is_its_own_confirmed_payment(seeded_session, staff):
    booking = await cancelled_with_refund(seeded_session, staff)
    await add_refund(seeded_session, booking, NewRefund(amount=40_000, method="mpesa", reference=" ref9 "), staff)
    booking = await reload(seeded_session, booking)
    refund = next(p for p in booking.payments if p.kind == "refund")
    assert (refund.amount, refund.status, refund.reference) == (40_000, "confirmed", "REF9")
    assert refund.confirmed_by == staff.id
    assert refund.confirmed_at is not None


async def test_refund_records_do_not_change_paid(seeded_session, staff):
    booking = await cancelled_with_refund(seeded_session, staff)
    await add_refund(seeded_session, booking, NewRefund(amount=90_000, method="cash"), staff)
    booking = await reload(seeded_session, booking)
    assert payment_summary(booking.total, booking.payments)[0] == 100_000


async def test_refunds_can_be_split_up_to_what_is_due(seeded_session, staff):
    booking = await cancelled_with_refund(seeded_session, staff)  # 90,000 due
    await add_refund(seeded_session, booking, NewRefund(amount=50_000, method="cash"), staff)
    booking = await reload(seeded_session, booking)
    await refused(
        "refund_exceeds_due",
        add_refund(seeded_session, booking, NewRefund(amount=40_001, method="cash"), staff),
    )
    await add_refund(seeded_session, booking, NewRefund(amount=40_000, method="cash"), staff)
    booking = await reload(seeded_session, booking)
    assert sum(p.amount for p in booking.payments if p.kind == "refund") == 90_000


async def test_refund_is_refused_on_a_live_booking(seeded_session, staff):
    booking = await book(seeded_session)
    booking = await pay(seeded_session, booking, 100_000)
    await refused(
        "not_cancelled", add_refund(seeded_session, booking, NewRefund(amount=1, method="cash"), staff)
    )


async def test_refund_reference_cannot_repeat(seeded_session, staff):
    booking = await cancelled_with_refund(seeded_session, staff)
    await add_refund(seeded_session, booking, NewRefund(amount=1, method="mpesa", reference="R1"), staff)
    booking = await reload(seeded_session, booking)
    await refused(
        "duplicate_reference",
        add_refund(seeded_session, booking, NewRefund(amount=1, method="mpesa", reference="r1"), staff),
    )


async def test_refund_references_may_be_left_blank_more_than_once(seeded_session, staff):
    booking = await cancelled_with_refund(seeded_session, staff)
    await add_refund(seeded_session, booking, NewRefund(amount=1, method="cash"), staff)
    booking = await reload(seeded_session, booking)
    await add_refund(seeded_session, booking, NewRefund(amount=1, method="cash"), staff)
    booking = await reload(seeded_session, booking)
    assert len([p for p in booking.payments if p.kind == "refund"]) == 2


async def test_a_mistaken_refund_record_can_be_rejected_and_frees_the_cap(seeded_session, staff):
    booking = await cancelled_with_refund(seeded_session, staff)
    await add_refund(seeded_session, booking, NewRefund(amount=90_000, method="cash"), staff)
    booking = await reload(seeded_session, booking)
    refund = next(p for p in booking.payments if p.kind == "refund")
    await reject_payment(seeded_session, booking, refund, staff)
    booking = await reload(seeded_session, booking)
    await add_refund(seeded_session, booking, NewRefund(amount=90_000, method="cash"), staff)


# --- Date changes ---


def in_days(days: int):
    return today_eat() + timedelta(days=days)


async def test_first_change_seven_days_out_is_free(seeded_session, staff):
    booking = await book(seeded_session, days=7)
    await change_date(seeded_session, booking, in_days(20), staff)
    booking = await reload(seeded_session, booking)
    assert booking.event_date == in_days(20)
    assert booking.date_changes_used == 1


async def test_change_moves_setup_collection_and_balance_date_but_not_prices(seeded_session, staff):
    booking = await book(seeded_session)
    setup, collect, total, deposit = booking.setup_at, booking.collect_at, booking.total, booking.deposit_due
    unit_prices = [i.unit_price for i in booking.items]
    await change_date(seeded_session, booking, in_days(35), staff)
    booking = await reload(seeded_session, booking)
    assert booking.setup_at == setup + timedelta(days=5)
    assert booking.collect_at == collect + timedelta(days=5)
    assert booking.balance_due_date == in_days(32)
    assert (booking.total, booking.deposit_due) == (total, deposit)
    assert [i.unit_price for i in booking.items] == unit_prices


async def test_change_can_also_move_earlier(seeded_session, staff):
    booking = await book(seeded_session)
    await change_date(seeded_session, booking, in_days(25), staff)
    assert (await reload(seeded_session, booking)).event_date == in_days(25)


async def test_change_is_recorded_with_both_dates(seeded_session, staff):
    booking = await book(seeded_session)
    await change_date(seeded_session, booking, in_days(35), staff, note="Church moved")
    row = (await reload(seeded_session, booking)).history[-1]
    assert row.from_status == row.to_status == "request"
    assert row.changed_by == staff.id
    assert row.note == f"{in_days(30)} → {in_days(35)} · Church moved"


async def test_second_change_is_refused(seeded_session, staff):
    booking = await book(seeded_session)
    await change_date(seeded_session, booking, in_days(35), staff)
    booking = await reload(seeded_session, booking)
    await refused("date_change_used", change_date(seeded_session, booking, in_days(40), staff))


async def test_change_inside_seven_days_is_refused(seeded_session, staff):
    booking = await book(seeded_session, days=6)
    await refused("too_close_to_event", change_date(seeded_session, booking, in_days(20), staff))


async def test_owner_exception_allows_a_second_change_with_a_note(seeded_session, staff, owner):
    booking = await book(seeded_session)
    await change_date(seeded_session, booking, in_days(35), staff)
    booking = await reload(seeded_session, booking)
    await change_date(seeded_session, booking, in_days(40), owner, exception=True, note="Bereavement")
    booking = await reload(seeded_session, booking)
    assert booking.event_date == in_days(40)
    assert booking.date_changes_used == 2
    assert "Bereavement" in booking.history[-1].note


async def test_owner_exception_allows_a_change_inside_seven_days(seeded_session, owner):
    booking = await book(seeded_session, days=5)
    await change_date(seeded_session, booking, in_days(20), owner, exception=True, note="Venue flooded")
    assert (await reload(seeded_session, booking)).event_date == in_days(20)


async def test_exception_needs_a_note(seeded_session, owner):
    booking = await book(seeded_session, days=5)
    await refused(
        "note_required", change_date(seeded_session, booking, in_days(20), owner, exception=True, note=" ")
    )


async def test_owner_without_exception_is_still_refused(seeded_session, owner):
    booking = await book(seeded_session, days=5)
    await refused("too_close_to_event", change_date(seeded_session, booking, in_days(20), owner, note="x"))


async def test_staff_cannot_use_the_exception(seeded_session, staff):
    booking = await book(seeded_session, days=5)
    await refused(
        "owner_only", change_date(seeded_session, booking, in_days(20), staff, exception=True, note="Please")
    )


async def test_same_date_is_refused_and_does_not_use_the_free_change(seeded_session, staff):
    booking = await book(seeded_session)
    await refused("same_date", change_date(seeded_session, booking, booking.event_date, staff))
    assert (await reload(seeded_session, booking)).date_changes_used == 0


@pytest.mark.parametrize("days", [-1, 0, 2])  # no servers on this booking, so the notice is 3 days
async def test_new_date_inside_the_notice_period_is_refused(seeded_session, owner, days):
    booking = await book(seeded_session)
    await refused(
        "date_inside_notice", change_date(seeded_session, booking, in_days(days), owner, exception=True, note="x")
    )


async def test_new_date_on_the_notice_boundary_is_allowed(seeded_session, staff):
    booking = await book(seeded_session)
    await change_date(seeded_session, booking, in_days(3), staff)
    assert (await reload(seeded_session, booking)).event_date == in_days(3)


async def test_servers_need_the_longer_notice(seeded_session, staff):
    server = await seeded_session.scalar(select(Addon.id).where(Addon.kind == "server"))
    booking = await book(seeded_session, addons=((server, 1),))
    await refused("date_inside_notice", change_date(seeded_session, booking, in_days(6), staff))
    await change_date(seeded_session, booking, in_days(7), staff)
    assert (await reload(seeded_session, booking)).event_date == in_days(7)


async def test_add_on_clash_is_refused_even_with_an_exception(seeded_session, owner):
    await set_cooler_capacity(seeded_session, 6)
    await book(seeded_session, days=30, status="confirmed")
    other = await book(seeded_session, days=40)
    await refused(
        "addons_unavailable", change_date(seeded_session, other, in_days(30), owner, exception=True, note="x")
    )


async def test_a_booking_does_not_clash_with_its_own_hold(seeded_session, staff):
    await set_cooler_capacity(seeded_session, 6)
    base = await quote_request(seeded_session, days=30)
    booking = await book(  # held for two days, so moving one day overlaps the old window
        seeded_session, days=30, status="confirmed", collect_at=base.setup_at + timedelta(days=2)
    )
    await change_date(seeded_session, booking, in_days(31), staff)
    assert (await reload(seeded_session, booking)).event_date == in_days(31)


@pytest.mark.parametrize("status", ["cancelled", "closed"])
async def test_change_is_refused_when_finished(seeded_session, owner, status):
    booking = await book(seeded_session, status=status)
    await refused("booking_finished", change_date(seeded_session, booking, in_days(35), owner))


@pytest.mark.parametrize("status", ["delivered", "returns_settled"])
async def test_change_is_refused_after_delivery(seeded_session, owner, status):
    booking = await book(seeded_session, status=status)
    await refused("invalid_move", change_date(seeded_session, booking, in_days(35), owner))


# --- Rush decisions ---


async def test_approving_records_who(seeded_session, staff):
    booking = await book(seeded_session, days=1)
    await decide_rush(seeded_session, booking, True, staff, note="Have stock")
    booking = await reload(seeded_session, booking)
    assert booking.rush_approved
    assert booking.status == "request"
    assert booking.history[-1].changed_by == staff.id
    assert booking.history[-1].note == "rush ✓ · Have stock"


async def test_declining_cancels_and_returns_everything_at_any_date(seeded_session, staff):
    booking = await book(seeded_session, days=1)  # the normal policy would give nothing back
    booking = await pay(seeded_session, booking, 100_000)
    await decide_rush(seeded_session, booking, False, staff)
    booking = await reload(seeded_session, booking)
    assert booking.status == "cancelled"
    assert booking.refund_due == 100_000
    assert booking.rush_approved is False
    assert booking.history[-1].to_status == "cancelled"
    assert booking.history[-1].note == "rush ✗"


async def test_declining_is_refused_with_a_payment_pending(seeded_session, staff):
    booking = await book(seeded_session, days=1)
    booking = await pay(seeded_session, booking, 100, status="pending")
    await refused("pending_payments", decide_rush(seeded_session, booking, False, staff))


@pytest.mark.parametrize("approve", [True, False])
async def test_rush_decision_needs_a_rush_booking(seeded_session, staff, approve):
    booking = await book(seeded_session)
    await refused("not_rush", decide_rush(seeded_session, booking, approve, staff))


@pytest.mark.parametrize("approve", [True, False])
@pytest.mark.parametrize("status", ["confirmed", "fully_paid", "cancelled", "closed"])
async def test_rush_decision_is_refused_past_quoted(seeded_session, staff, approve, status):
    booking = await book(seeded_session, days=1, status=status)
    await refused("invalid_move", decide_rush(seeded_session, booking, approve, staff))


# --- Delivery fee on provisional bookings ---


async def test_setting_the_fee_recalculates_the_total_and_deposit(seeded_session, staff):
    booking = await provisional(seeded_session)
    assert booking.delivery_fee_custom
    before = booking.total
    await set_delivery_fee(seeded_session, booking, 50_001, staff)
    booking = await reload(seeded_session, booking)
    assert booking.delivery_fee == 50_001
    assert booking.total == before + 50_001
    assert booking.deposit_due == -(-booking.total // 2)
    assert booking.delivery_fee_custom is False
    assert booking.history[-1].changed_by == staff.id
    assert booking.history[-1].note == "TZS 50001"


async def test_fee_of_zero_is_allowed(seeded_session, staff):
    booking = await provisional(seeded_session)
    before = booking.total
    await set_delivery_fee(seeded_session, booking, 0, staff)
    booking = await reload(seeded_session, booking)
    assert booking.total == before
    assert booking.delivery_fee_custom is False


async def test_booking_can_move_on_once_the_fee_is_set(seeded_session, staff):
    booking = await provisional(seeded_session)
    await set_delivery_fee(seeded_session, booking, 50_000, staff)
    booking = await reload(seeded_session, booking)
    await move_stage(seeded_session, booking, "quoted", staff)
    assert (await reload(seeded_session, booking)).status == "quoted"


async def test_fee_is_refused_when_not_provisional(seeded_session, staff):
    booking = await book(seeded_session)
    await refused("not_provisional", set_delivery_fee(seeded_session, booking, 1, staff))


@pytest.mark.parametrize("status", ["confirmed", "cancelled", "closed"])
async def test_fee_is_refused_past_quoted(seeded_session, staff, status):
    booking = await provisional(seeded_session, status=status)
    await refused("invalid_move", set_delivery_fee(seeded_session, booking, 1, staff))
