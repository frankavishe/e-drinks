"""Staff and owner endpoints. The router-level check means no route here can be left open."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.db import get_session
from app.models import Booking, Profile
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
    FinancialsOut,
    HistoryOut,
    OverviewOut,
    ProfileOut,
    Stage,
)
from app.services.admin_queries import (
    BookingFilters,
    actor_names,
    financials,
    list_bookings,
    load_booking,
    overview,
    refunded_total,
)
from app.services.availability import today_eat
from app.services.bookings import payment_summary

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
