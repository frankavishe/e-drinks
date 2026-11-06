# Data Model: Admin Dashboard

All tables exist already. This feature adds two columns.

## Schema changes (one migration)

| Change | Detail |
|---|---|
| `bookings.refund_due` | Nullable bigint. Null until cancelled; then the TZS owed back, fixed at that moment. |
| `bookings.internal_notes` | Text, not null, default `''`. Staff notes; never returned by public endpoints. `notes` stays what the customer typed. |

## Stage transitions

| From | To | Who | Requires | Refusal codes |
|---|---|---|---|---|
| request | quoted | staff, owner | not provisional | `provisional` |
| request, quoted | confirmed | staff, owner | paid ≥ `deposit_due`; rush approved if `is_rush`; not provisional; add-ons free | `deposit_not_paid`, `rush_not_approved`, `provisional`, `addons_unavailable` |
| confirmed | fully_paid | staff, owner | paid ≥ `total` | `not_fully_paid` |
| fully_paid | delivered | staff, owner | none | |
| delivered | returns_settled | staff, owner | none | |
| returns_settled | closed | staff, owner | none | |
| confirmed | request | owner | note | `owner_only`, `note_required` |
| fully_paid | confirmed | owner | note | `owner_only`, `note_required` |
| delivered | fully_paid | owner | note | `owner_only`, `note_required` |
| returns_settled | delivered | owner | note | `owner_only`, `note_required` |
| any but closed, cancelled | cancelled | staff, owner | no pending payments | `pending_payments`, `booking_finished` |

Any other move is refused with `invalid_move`. "Paid" is the first value from `payment_summary`: confirmed
deposit and balance records. Cancelling has its own endpoint, so `/stage` with `to: cancelled` is `invalid_move`.
`allowed_moves` lists the forward and back moves, from the same check that enforces them; a missing note isn't a
listed reason, because the note is typed when acting.

## Written by admin actions

**Stage move**: `Booking.status`; a `BookingStatusHistory` row with `from_status`, `to_status`, `changed_by`, `note`.

**Payment confirm**: `Payment.status = confirmed`, `confirmed_by`, `confirmed_at`. Only from pending; otherwise
`already_confirmed` or `already_rejected`. Refused with `booking_finished` on a cancelled or closed booking.

**Payment reject**: `Payment.status = rejected`, `confirmed_by`, `confirmed_at` (who decided, and when). From
pending or confirmed. Refused with `payment_needed_by_stage` if paid would fall below what the stage needs
(`deposit_due` at confirmed; `total` at fully_paid and later), and `already_rejected` if repeated. On a cancelled
or closed booking, deposit and balance records are frozen (`booking_finished`) because `refund_due` was worked out
from them; a mistaken refund record can still be rejected, which frees that amount against the cap.

**Cancel**: `status = cancelled`, `refund_due`, history row.

| Days before event | Deposit part returned |
|---|---|
| 14 or more | 90% |
| 7–13 | 50% |
| under 7 | none |

`refund_due = cancellation_refund(min(paid, deposit_due), days) + max(paid - deposit_due, 0)`

**Refund record**: a new `Payment` with `kind = refund`, `status = confirmed`, the actor and time. Method may also
be `cash`; the reference is optional. Only on a cancelled booking (`not_cancelled`). Refused with
`refund_exceeds_due` if refund records would total more than `refund_due`, and `duplicate_reference` if the
reference is already used. `payment_summary` already ignores refund records.

**Date change**: `event_date`; `setup_at` and `collect_at` shifted by the same days; `balance_due_date` from
`balance_due_days`; `date_changes_used + 1`; a history row with the same from and to stage and a note holding
both dates. Refusal codes: `date_change_used`, `too_close_to_event`, `date_inside_notice` (also for a past date),
`same_date` (so a no-op can't use up the free change), `addons_unavailable`, `booking_finished`, `invalid_move`
(Delivered or later), `owner_only`, `note_required`.

**Same-stage history rows** hold data rather than sentences, so they read in either language:
`2026-11-20 → 2026-12-01`, `TZS 50000`, `rush ✓`, `rush ✗`, followed by any note typed.

**Rush approve**: `rush_approved = true`. Refused with `not_rush` if `is_rush` is false, and `invalid_move`
past Quoted.

**Rush decline**: as cancel, but `refund_due` = everything paid, whatever the date. Refused with `not_rush` if
`is_rush` is false, `invalid_move` past Quoted (use cancel instead, where the policy applies), and
`pending_payments` while any is pending.

**Delivery fee**: `delivery_fee`; `total` recomputed; `deposit_due` from the current `deposit_percent`;
`delivery_fee_custom = false`; history note. Only in request or quoted (`invalid_move`) and only while provisional
(`not_provisional`).

**EFD number and notes**: `efd_receipt_no`, `internal_notes`.

## Not changed by catalog edits

`booking_items` and `booking_addons` keep their snapshots. A product, package or add-on referenced by a booking
can't be deleted, only deactivated.

## Validation rules

| Entity | Rule | Code |
|---|---|---|
| PriceTier set | at least one; lowest `min_qty` is 1; no repeated `min_qty`; `unit_price` ≥ 0 | `invalid_tiers` |
| Product | not deleted while in `booking_items` or `package_rules` | `in_use` |
| Package | not deleted while on a booking | `in_use` |
| Addon | not deleted while in `booking_addons` | `in_use` |
| Zone | not deleted while it has areas | `in_use` |
| Area | not deleted while it has venues or bookings | `in_use` |
| Venue | not deleted while on a booking | `in_use` |
| Setting | only known seed keys; pricing keys must be whole numbers ≥ 0, `deposit_percent` at most 100 | `invalid_setting` |
