"""What staff and the owner may do to a booking, and what each action changes.

Actions expect a booking from load_booking(..., lock=True), so status checks made here can't go stale
before the commit. A refusal raises StageRefused before anything is written.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Addon, Booking, BookingStatusHistory, Payment, Profile
from app.services.admin_queries import refunded_total
from app.services.availability import addon_availability, is_rush, today_eat
from app.services.bookings import (
    FINISHED_STATUSES,
    ORDER_PAYMENT_KINDS,
    payment_summary,
    reference_in_use,
)
from app.services.pricing import STAFF_KINDS, deposit_for, refund_due
from app.services.settings_store import load_pricing_settings

FORWARD_MOVES = {
    "request": ("quoted", "confirmed"),
    "quoted": ("confirmed",),
    "confirmed": ("fully_paid",),
    "fully_paid": ("delivered",),
    "delivered": ("returns_settled",),
    "returns_settled": ("closed",),
}
BACK_MOVES = {
    "confirmed": "request",
    "fully_paid": "confirmed",
    "delivered": "fully_paid",
    "returns_settled": "delivered",
}
BEFORE_CONFIRMED = ("request", "quoted")
AFTER_DELIVERY = ("delivered", "returns_settled")

FREE_DATE_CHANGES = 1
FREE_DATE_CHANGE_DAYS = 7


class StageRefused(Exception):
    """A business rule said no. The code is translated for the person looking at the screen."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Move:
    to: str
    allowed: bool
    reason: str | None
    back: bool


@dataclass(frozen=True)
class CancelPreview:
    days_ahead: int
    paid: int
    refund_due: int


@dataclass(frozen=True)
class NewRefund:
    amount: int
    method: str
    reference: str = ""


def _paid(booking: Booking) -> int:
    return payment_summary(booking.total, booking.payments)[0]


def _has_pending(booking: Booking) -> bool:
    return payment_summary(booking.total, booking.payments)[1] > 0


def _record(booking: Booking, from_status: str, to_status: str, actor: Profile, note: str) -> None:
    booking.history.append(
        BookingStatusHistory(
            from_status=from_status, to_status=to_status, changed_by=actor.id, note=note.strip()
        )
    )


def _with_note(data: str, note: str) -> str:
    """Same-stage history rows hold data, not sentences, so they read in either language."""
    return f"{data} · {note.strip()}" if note.strip() else data


async def _addons_free(
    session: AsyncSession, booking: Booking, setup_at: datetime, collect_at: datetime, *, lock: bool
) -> bool:
    """Whether this booking's add-ons fit the window, not counting its own hold.

    With `lock`, the add-on rows are held until commit, in id order so two bookings can't deadlock.
    Without it, two bookings could each take the last cooler at once.
    """
    wanted = {line.addon_id: line.qty for line in booking.addons}
    if not wanted:
        return True
    if lock:
        await session.execute(
            select(Addon.id).where(Addon.id.in_(wanted)).order_by(Addon.id).with_for_update()
        )
    free = await addon_availability(
        session, wanted, setup_at, collect_at, exclude_booking_id=booking.id
    )
    return all(free[addon_id] is None or qty <= free[addon_id] for addon_id, qty in wanted.items())


async def _refusal(
    session: AsyncSession, booking: Booking, to: str, role: str, *, lock: bool
) -> str | None:
    """Why this move can't happen, or None. The note is checked when acting: it's typed then."""
    if BACK_MOVES.get(booking.status) == to:
        return None if role == "owner" else "owner_only"
    if to not in FORWARD_MOVES.get(booking.status, ()):
        return "invalid_move"
    if to == "quoted":
        return "provisional" if booking.delivery_fee_custom else None
    if to == "confirmed":
        if booking.delivery_fee_custom:
            return "provisional"
        if booking.is_rush and not booking.rush_approved:
            return "rush_not_approved"
        if _paid(booking) < booking.deposit_due:
            return "deposit_not_paid"
        if not await _addons_free(session, booking, booking.setup_at, booking.collect_at, lock=lock):
            return "addons_unavailable"
    if to == "fully_paid" and _paid(booking) < booking.total:
        return "not_fully_paid"
    return None


async def allowed_moves(session: AsyncSession, booking: Booking, actor: Profile) -> list[Move]:
    """Every next stage on offer and why not, from the same check that enforces the move."""
    targets = list(FORWARD_MOVES.get(booking.status, ()))
    back = BACK_MOVES.get(booking.status)
    if back:
        targets.append(back)
    moves = []
    for to in targets:
        reason = await _refusal(session, booking, to, actor.role, lock=False)
        moves.append(Move(to=to, allowed=reason is None, reason=reason, back=to == back))
    return moves


async def move_stage(
    session: AsyncSession, booking: Booking, to: str, actor: Profile, note: str = ""
) -> None:
    reason = await _refusal(session, booking, to, actor.role, lock=True)
    if reason:
        raise StageRefused(reason)
    if BACK_MOVES.get(booking.status) == to and not note.strip():
        raise StageRefused("note_required")
    _record(booking, booking.status, to, actor, note)
    booking.status = to
    await session.commit()


def _paid_needed_by_stage(booking: Booking) -> int:
    if booking.status in BEFORE_CONFIRMED:
        return 0
    if booking.status == "confirmed":
        return booking.deposit_due
    return booking.total


def _decide(payment: Payment, status: str, actor: Profile) -> None:
    payment.status = status
    payment.confirmed_by = actor.id
    payment.confirmed_at = datetime.now(timezone.utc)


async def confirm_payment(
    session: AsyncSession, booking: Booking, payment: Payment, actor: Profile
) -> None:
    if booking.status in FINISHED_STATUSES:
        raise StageRefused("booking_finished")
    if payment.status != "pending":
        raise StageRefused(f"already_{payment.status}")
    _decide(payment, "confirmed", actor)
    await session.commit()


async def reject_payment(
    session: AsyncSession, booking: Booking, payment: Payment, actor: Profile
) -> None:
    """A refund record can be rejected on a cancelled booking, to correct a mistaken entry."""
    if payment.status == "rejected":
        raise StageRefused("already_rejected")
    if payment.kind in ORDER_PAYMENT_KINDS:
        if booking.status in FINISHED_STATUSES:  # refund_due was worked out from these
            raise StageRefused("booking_finished")
        if (
            payment.status == "confirmed"
            and _paid(booking) - payment.amount < _paid_needed_by_stage(booking)
        ):
            raise StageRefused("payment_needed_by_stage")
    _decide(payment, "rejected", actor)
    await session.commit()


def _check_cancellable(booking: Booking) -> None:
    if booking.status in FINISHED_STATUSES:
        raise StageRefused("booking_finished")


def cancel_preview(booking: Booking) -> CancelPreview:
    _check_cancellable(booking)
    days_ahead = (booking.event_date - today_eat()).days
    paid = _paid(booking)
    return CancelPreview(
        days_ahead=days_ahead,
        paid=paid,
        refund_due=refund_due(paid, booking.deposit_due, days_ahead),
    )


async def _cancel(
    session: AsyncSession, booking: Booking, refund: int, actor: Profile, note: str
) -> None:
    _record(booking, booking.status, "cancelled", actor, note)
    booking.status = "cancelled"
    booking.refund_due = refund
    await session.commit()


async def cancel_booking(
    session: AsyncSession, booking: Booking, actor: Profile, note: str = ""
) -> None:
    """Fixes what's owed now, because it depends on today and on the money received so far."""
    _check_cancellable(booking)
    if _has_pending(booking):
        raise StageRefused("pending_payments")
    await _cancel(session, booking, cancel_preview(booking).refund_due, actor, note)


async def add_refund(
    session: AsyncSession, booking: Booking, new: NewRefund, actor: Profile
) -> None:
    if booking.status != "cancelled":
        raise StageRefused("not_cancelled")
    if refunded_total(booking.payments) + new.amount > (booking.refund_due or 0):
        raise StageRefused("refund_exceeds_due")
    reference = new.reference.strip().upper()
    if reference and await reference_in_use(session, booking.id, reference):
        raise StageRefused("duplicate_reference")
    booking.payments.append(
        Payment(
            kind="refund",
            method=new.method,
            amount=new.amount,
            reference=reference,
            status="confirmed",
            confirmed_by=actor.id,
            confirmed_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


def _date_change_refusal(booking: Booking) -> str | None:
    """The policy limits, which only the owner can waive."""
    if booking.date_changes_used >= FREE_DATE_CHANGES:
        return "date_change_used"
    if (booking.event_date - today_eat()).days < FREE_DATE_CHANGE_DAYS:
        return "too_close_to_event"
    return None


async def change_date(
    session: AsyncSession,
    booking: Booking,
    new_date: date,
    actor: Profile,
    *,
    exception: bool = False,
    note: str = "",
) -> None:
    """Prices stay as booked. An exception waives the policy, not the notice or equipment limits."""
    if booking.status in FINISHED_STATUSES:
        raise StageRefused("booking_finished")
    if booking.status in AFTER_DELIVERY:
        raise StageRefused("invalid_move")
    if new_date == booking.event_date:
        raise StageRefused("same_date")

    refusal = _date_change_refusal(booking)
    if refusal:
        if not exception:
            raise StageRefused(refusal)
        if actor.role != "owner":
            raise StageRefused("owner_only")
        if not note.strip():
            raise StageRefused("note_required")

    settings = await load_pricing_settings(session)
    today = today_eat()
    has_staff = any(line.addon.kind in STAFF_KINDS for line in booking.addons)
    if new_date < today or is_rush(new_date, today, has_staff, settings):
        raise StageRefused("date_inside_notice")

    shift = timedelta(days=(new_date - booking.event_date).days)
    setup_at, collect_at = booking.setup_at + shift, booking.collect_at + shift
    if not await _addons_free(session, booking, setup_at, collect_at, lock=True):
        raise StageRefused("addons_unavailable")

    _record(booking, booking.status, booking.status, actor, _with_note(f"{booking.event_date} → {new_date}", note))
    booking.event_date = new_date
    booking.setup_at = setup_at
    booking.collect_at = collect_at
    booking.balance_due_date = new_date - timedelta(days=settings.balance_due_days)
    booking.date_changes_used += 1
    await session.commit()


async def decide_rush(
    session: AsyncSession, booking: Booking, approve: bool, actor: Profile, note: str = ""
) -> None:
    """Declining cancels with everything paid due back: the business said no, so no penalty applies."""
    if not booking.is_rush:
        raise StageRefused("not_rush")
    if booking.status not in BEFORE_CONFIRMED:
        raise StageRefused("invalid_move")
    if approve:
        booking.rush_approved = True
        _record(booking, booking.status, booking.status, actor, _with_note("rush ✓", note))
        await session.commit()
        return
    if _has_pending(booking):
        raise StageRefused("pending_payments")
    await _cancel(session, booking, _paid(booking), actor, _with_note("rush ✗", note))


async def set_delivery_fee(
    session: AsyncSession, booking: Booking, fee: int, actor: Profile
) -> None:
    if booking.status not in BEFORE_CONFIRMED:
        raise StageRefused("invalid_move")
    if not booking.delivery_fee_custom:
        raise StageRefused("not_provisional")
    settings = await load_pricing_settings(session)
    booking.total += fee - booking.delivery_fee
    booking.delivery_fee = fee
    booking.deposit_due = deposit_for(booking.total, settings.deposit_percent)
    booking.delivery_fee_custom = False
    _record(booking, booking.status, booking.status, actor, f"TZS {fee}")
    await session.commit()
