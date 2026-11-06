"""Staff and owner endpoints. The router-level check means no route here can be left open."""

from collections import defaultdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.db import get_session
from app.models import Booking, Payment, Profile
from app.schemas.admin import (
    AdminAddonOut,
    AdminItemOut,
    AdminPaymentOut,
    BookingDetailOut,
    BookingListOut,
    BookingOwnerOut,
    BookingPatch,
    BookingResponse,
    BookingRow,
    CalendarAddon,
    CalendarBooking,
    CalendarDay,
    CalendarOut,
    CancelIn,
    CancelPreviewOut,
    DateChangeIn,
    DeliveryFeeIn,
    FinancialsOut,
    HistoryOut,
    MoveOut,
    OverviewOut,
    ProfileOut,
    RefundIn,
    RushIn,
    Stage,
    StageIn,
)
from app.services.admin_queries import (
    BookingFilters,
    actor_names,
    calendar_bookings,
    financials,
    list_bookings,
    load_booking,
    overview,
    refunded_total,
)
from app.services.availability import daily_usage, today_eat
from app.services.booking_flow import (
    NewRefund,
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
from app.services.bookings import payment_summary

MAX_CALENDAR_DAYS = 62

staff_or_owner = require_role("staff", "owner")

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(staff_or_owner)])

Session = Annotated[AsyncSession, Depends(get_session)]
Actor = Annotated[Profile, Depends(staff_or_owner)]


@router.get("/me", response_model=ProfileOut)
async def me(actor: Actor):
    return actor


def _row_fields(booking: Booking) -> dict:
    paid, pending, _ = payment_summary(booking.total, booking.payments)
    return {
        "id": booking.id,
        "code": booking.code,
        "status": booking.status,
        "is_rush": booking.is_rush,
        "rush_approved": booking.rush_approved,
        "provisional": booking.delivery_fee_custom,
        "event_type": booking.event_type,
        "event_date": booking.event_date,
        "start_time": booking.start_time,
        "guests": booking.guests,
        "customer_name": booking.customer.name,
        "customer_phone": booking.customer.phone,
        "venue_name": booking.venue_name,
        "total": booking.total,
        "amount_paid": paid,
        "amount_pending": pending,
    }


def _row(booking: Booking) -> BookingRow:
    return BookingRow(**_row_fields(booking))


async def _detail(session: AsyncSession, booking: Booking, actor: Profile) -> BookingDetailOut:
    """The owner's class only for the owner; everyone else gets the one with no money fields."""
    names = await actor_names(session, booking)
    _, _, balance = payment_summary(booking.total, booking.payments)
    fields = {
        **_row_fields(booking),
        "customer_email": booking.customer.email,
        "hours": booking.hours,
        "venue_address": booking.venue_address,
        "custom_area": booking.custom_area,
        "lang": booking.lang,
        "setup_at": booking.setup_at,
        "collect_at": booking.collect_at,
        "notes": booking.notes,
        "internal_notes": booking.internal_notes,
        "efd_receipt_no": booking.efd_receipt_no,
        "date_changes_used": booking.date_changes_used,
        "balance_due_date": booking.balance_due_date,
        "balance_due": balance,
        "subtotal": booking.subtotal,
        "addons_total": booking.addons_total,
        "delivery_fee": booking.delivery_fee,
        "empties_deposit": booking.empties_deposit,
        "deposit_due": booking.deposit_due,
        "refund_due": booking.refund_due,
        "refunded": refunded_total(booking.payments),
        "items": [
            AdminItemOut(
                name_sw=item.product.name_sw,
                name_en=item.product.name_en,
                unit=item.product.unit,
                qty=item.qty,
                unit_price=item.unit_price,
                line_total=item.qty * item.unit_price,
            )
            for item in booking.items
        ],
        "addons": [
            AdminAddonOut(
                name_sw=line.addon.name_sw,
                name_en=line.addon.name_en,
                qty=line.qty,
                unit_price=line.unit_price,
                line_total=line.qty * line.unit_price,
            )
            for line in booking.addons
        ],
        "payments": [
            AdminPaymentOut(
                id=p.id,
                kind=p.kind,
                method=p.method,
                amount=p.amount,
                reference=p.reference,
                status=p.status,
                confirmed_by_name=names.get(p.confirmed_by),
                confirmed_at=p.confirmed_at,
                created_at=p.created_at,
            )
            for p in booking.payments
        ],
        "history": [
            HistoryOut(
                from_status=h.from_status,
                to_status=h.to_status,
                changed_by_name=names.get(h.changed_by),
                note=h.note,
                created_at=h.created_at,
            )
            for h in booking.history
        ],
        "allowed_moves": [
            MoveOut.model_validate(move) for move in await allowed_moves(session, booking, actor)
        ],
    }
    if actor.role == "owner":
        return BookingOwnerOut(
            **fields, financials=FinancialsOut.model_validate(financials(booking))
        )
    return BookingDetailOut(**fields)


async def _found(session: AsyncSession, booking_id: int, *, lock: bool = False) -> Booking:
    booking = await load_booking(session, booking_id, lock=lock)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.get("/overview", response_model=OverviewOut)
async def get_overview(session: Session):
    today, upcoming = await overview(session, today_eat())
    return OverviewOut(today=[_row(b) for b in today], upcoming=[_row(b) for b in upcoming])


@router.get("/calendar", response_model=CalendarOut)
async def get_calendar(
    session: Session,
    first: Annotated[date, Query(alias="from")],
    last: Annotated[date, Query(alias="to")],
):
    if not 1 <= (last - first).days + 1 <= MAX_CALENDAR_DAYS:
        raise HTTPException(status_code=422, detail=f"Range must be 1 to {MAX_CALENDAR_DAYS} days")

    bookings: dict[date, list[CalendarBooking]] = defaultdict(list)
    for booking in await calendar_bookings(session, first, last):
        bookings[booking.event_date].append(
            CalendarBooking(
                id=booking.id,
                code=booking.code,
                status=booking.status,
                is_rush=booking.is_rush,
                customer_name=booking.customer.name,
                start_time=booking.start_time,
            )
        )
    usage = await daily_usage(session, first, last)
    return CalendarOut(
        days=[
            CalendarDay(
                date=day,
                bookings=bookings[day],
                addons=[CalendarAddon.model_validate(line) for line in lines],
            )
            for day, lines in usage.items()
        ]
    )


@router.get("/bookings", response_model=BookingListOut)
async def get_bookings(
    session: Session,
    q: Annotated[str, Query(max_length=120)] = "",
    status: Stage | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    rush: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    total, rows = await list_bookings(
        session,
        BookingFilters(
            q=q, status=status, date_from=date_from, date_to=date_to, rush=rush, limit=limit, offset=offset
        ),
    )
    return BookingListOut(total=total, items=[_row(b) for b in rows])


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: int, session: Session, actor: Actor):
    return await _detail(session, await _found(session, booking_id), actor)


@router.patch("/bookings/{booking_id}", response_model=BookingResponse)
async def patch_booking(booking_id: int, body: BookingPatch, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    if body.efd_receipt_no is not None:
        booking.efd_receipt_no = body.efd_receipt_no
    if body.internal_notes is not None:
        booking.internal_notes = body.internal_notes
    await session.commit()
    return await _detail(session, booking, actor)


async def _reloaded(session: AsyncSession, booking_id: int, actor: Profile) -> BookingDetailOut:
    """The detail after an action, read again so new rows and amounts are included."""
    return await _detail(session, await _found(session, booking_id), actor)


@router.post("/bookings/{booking_id}/stage", response_model=BookingResponse)
async def post_stage(booking_id: int, body: StageIn, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    await move_stage(session, booking, body.to, actor, note=body.note)
    return await _reloaded(session, booking_id, actor)


@router.get("/bookings/{booking_id}/cancel-preview", response_model=CancelPreviewOut)
async def get_cancel_preview(booking_id: int, session: Session):
    return CancelPreviewOut.model_validate(cancel_preview(await _found(session, booking_id)))


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def post_cancel(booking_id: int, body: CancelIn, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    await cancel_booking(session, booking, actor, note=body.note)
    return await _reloaded(session, booking_id, actor)


@router.post("/bookings/{booking_id}/refunds", response_model=BookingResponse, status_code=201)
async def post_refund(booking_id: int, body: RefundIn, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    new = NewRefund(amount=body.amount, method=body.method, reference=body.reference)
    await add_refund(session, booking, new, actor)
    return await _reloaded(session, booking_id, actor)


@router.post("/bookings/{booking_id}/date-change", response_model=BookingResponse)
async def post_date_change(booking_id: int, body: DateChangeIn, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    await change_date(session, booking, body.new_date, actor, exception=body.exception, note=body.note)
    return await _reloaded(session, booking_id, actor)


@router.post("/bookings/{booking_id}/rush", response_model=BookingResponse)
async def post_rush(booking_id: int, body: RushIn, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    await decide_rush(session, booking, body.approve, actor, note=body.note)
    return await _reloaded(session, booking_id, actor)


@router.post("/bookings/{booking_id}/delivery-fee", response_model=BookingResponse)
async def post_delivery_fee(booking_id: int, body: DeliveryFeeIn, session: Session, actor: Actor):
    booking = await _found(session, booking_id, lock=True)
    await set_delivery_fee(session, booking, body.fee, actor)
    return await _reloaded(session, booking_id, actor)


async def _locked_payment(session: AsyncSession, payment_id: int) -> tuple[Booking, Payment]:
    """Locks through the booking, so its payment rules and stage can't change underneath."""
    booking_id = await session.scalar(select(Payment.booking_id).where(Payment.id == payment_id))
    if booking_id is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    booking = await _found(session, booking_id, lock=True)
    return booking, next(p for p in booking.payments if p.id == payment_id)


@router.post("/payments/{payment_id}/confirm", response_model=BookingResponse)
async def post_confirm_payment(payment_id: int, session: Session, actor: Actor):
    booking, payment = await _locked_payment(session, payment_id)
    await confirm_payment(session, booking, payment, actor)
    return await _reloaded(session, booking.id, actor)


@router.post("/payments/{payment_id}/reject", response_model=BookingResponse)
async def post_reject_payment(payment_id: int, session: Session, actor: Actor):
    booking, payment = await _locked_payment(session, payment_id)
    await reject_payment(session, booking, payment, actor)
    return await _reloaded(session, booking.id, actor)
