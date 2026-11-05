# Research: Admin Dashboard

## Refund due on cancellation

- **Decision**: refund = policy share of the deposit part + 100% of anything paid above the deposit. The
  deposit part is `min(paid, deposit_due)`. 14+ days keeps 90%, 7–13 days 50%, under 7 days nothing, rounded
  down to whole TZS. Days are `event_date - today_eat()`.
- **Rationale**: the owner's decision. The policy text only penalises the deposit.
- **Alternatives**: policy percentage on everything paid (stricter than the wording); deposit only, with
  balance refunds worked out by hand (no cap on refund records).

## Fixing the refund at cancellation

- **Decision**: store `bookings.refund_due` when the booking is cancelled.
- **Rationale**: the amount depends on the day of cancellation and on the payments at that moment. Deriving it
  later from a history timestamp would move if the deposit or policy changed. It is an amount owed, not a
  balance, so Principle III's "balances are derived" still holds; refunds actually paid are payment records.

## Declining a rush request

- **Decision**: declining moves the booking to Cancelled with `refund_due` = everything paid.
- **Rationale**: the owner's decision. The business turned it down, so no penalty applies.
- **Alternatives**: normal policy (customer loses money for the business's choice); stay open flagged as
  declined (a state the stage list doesn't have).

## Moving a stage back

- **Decision**: one step back, owner only, note required: confirmed → request, fully_paid → confirmed,
  delivered → fully_paid, returns_settled → delivered. Closed and Cancelled are final.
- **Rationale**: the owner's decision. The spec needs moving back so a wrongly confirmed payment can be
  rejected; staff alone could otherwise undo a stage and then reject a payment.

## Confirming a payment and moving the stage

- **Decision**: two separate actions. The UI puts the next allowed move right beside the payment.
- **Rationale**: the spec says the booking "can move", and SC-001 counts both actions. `Frank plan.md` read as
  automatic, and is amended to match.

## Telling the browser what's allowed

- **Decision**: the detail response has `allowed_moves: [{to, allowed, reason}]`, from the same function that
  enforces the move.
- **Rationale**: Principle I, and SC-002 needs the reason shown. The rule cannot drift between UI and server.

## Concurrency

- **Decision**: every admin mutation loads the booking `with_for_update()` and re-reads status under the lock.
  The move to Confirmed also locks the booking's add-on rows before checking capacity.
- **Rationale**: one rule covers double confirmation and reject-versus-move races. Locking add-ons stops two
  bookings taking the last cooler at once, which a per-booking lock alone would allow.
- **Limit**: SQLite ignores `FOR UPDATE`, so tests prove the status recheck (a second confirm is refused), not
  the lock itself.

## Staff and owner responses

- **Decision**: separate Pydantic classes per role (`ProductStaffOut` / `ProductOwnerOut`). The staff booking
  schema has no financial fields at all; `BookingOwnerOut` extends it with `financials`. Each endpoint picks
  the class from the profile's role.
- **Rationale**: a field that doesn't exist can't leak. An optional field set to null would still put the key
  in staff responses, and a forgotten null check would leak the value.
- **Profit**: `subtotal + addons_total + delivery_fee - sum(qty × unit_cost)`. The empties deposit is excluded
  because it is refundable. True cost from purchases arrives in 004.
- **Replacement cost**: owner only, since the spec hides catalog cost fields from staff.

## Provisional delivery fee

- **Decision**: admin sets the fee in Request or Quoted. `total` and `deposit_due` are recomputed with the
  current `deposit_percent`, and `delivery_fee_custom` is cleared. Provisional bookings can't move forward
  until then.
- **Rationale**: 001 and 002 both say the fee is set by hand in 003, but the spec didn't list it. A booking
  can't be confirmed against a deposit calculated without delivery.

## Date change

- **Decision**: free if it is the first change and the current event is 7+ days away. Otherwise refused, unless
  the owner marks it an exception with a note. The new date must be today or later and outside the notice
  period, and add-ons must be free; the exception does not waive those two. `setup_at` and `collect_at` shift by
  the same number of days; `balance_due_date` is recomputed; prices stay as booked. Recorded as a history row
  whose from and to stage match.
- **Rationale**: an exception waives the policy, not the physical equipment limit. Refusing dates inside the
  notice period avoids turning a confirmed booking into an unapproved rush.

## Tiers

- **Decision**: tiers are replaced as a whole set. Rejected if `min_qty` repeats, the lowest isn't 1, or the set
  is empty.
- **Rationale**: tiers store only `min_qty`, so ranges can't overlap except by duplicating. A lowest tier above
  1 makes `tier_price` raise `CatalogError` for small orders at quote time.

## Deletion

- **Decision**: delete is refused with `in_use` when a booking or dependent row references the record. Products,
  packages and add-ons can be deactivated instead.
- **Rationale**: the spec's edge case; foreign keys would refuse anyway, but with an unreadable error.

## Calendar

- **Decision**: `GET /admin/calendar?from&to` returns, per EAT day, the bookings on that event date and each
  add-on's committed peak against owned capacity. Committed counts `HOLDING_STATUSES` bookings whose
  setup-to-collect window touches that day. Hand-built CSS grid in the browser.
- **Rationale**: uses the rule availability already uses; requests don't hold equipment, so they appear as
  bookings but not in usage. No calendar library (Principle VII).

## Product images

- **Decision**: a URL text field. No upload.
- **Rationale**: Principle VII. The spec asks for an image, and upload needs a Storage bucket and credentials
  that nothing else here uses.

## Staff accounts

- **Decision**: `python -m app.seed --staff-email`, the same way as `--owner-email`.
- **Rationale**: the spec assumes the owner creates accounts, with no screen for it. The user is created in
  Supabase Auth, then this adds the profile.
