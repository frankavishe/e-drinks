# Research: Booking Wizard, Tracking & Payment References

## Booking numbers

- **Decision**: `booking_counters(year, last_no)`, incremented with one
  `INSERT … ON CONFLICT (year) DO UPDATE … RETURNING` inside the booking's transaction. The year is the
  creation year in EAT.
- **Rationale**: the upsert is atomic on Postgres and SQLite, so concurrent bookings can't collide, and a
  rollback leaves no gap.
- **Alternatives**: `max(code) + 1` with a retry loop (more code, and a race to handle); a Postgres
  sequence (no yearly reset, not on SQLite).

## Re-check on submit

- **Decision**: the client sends `expected_total`. The server re-prices through the code `/public/quote`
  uses and returns `409` with `{code, quote}` for `addons_unavailable`, `below_minimum` or `quote_changed`.
- **Rationale**: SC-002 needs saved totals to equal the reviewed quote, and the customer needs to see why
  it changed.
- **Alternatives**: saving whatever the new total is (breaks SC-002).

## Minimum order

- **Decision**: below-minimum orders are blocked at submit. The quote keeps flagging them, as 001 requires.
- **Rationale**: `Frank plan.md` lists the minimum order under "Limits"; FR-002 saves only if valid.

## Unlisted areas

- **Decision**: allowed. Delivery is 0 with `delivery_fee_custom=true`, and the deposit is on the total
  without delivery. Admin sets the fee in 003.

## Phone numbers

- **Decision**: Tanzanian mobiles only (`0`, `255` or `+255`, then `6x`/`7x` and 8 digits; spaces and
  dashes ignored), stored as `255XXXXXXXXX`.
- **Trade-off**: customers using overseas numbers can't book.

## Repeat customers

- **Decision**: unique `customers.phone`; `INSERT … ON CONFLICT DO NOTHING`, then select. The stored name is
  kept and a blank email is filled in. The confirmation goes to the email entered on the booking.
- **Rationale**: no account proves ownership of a phone, so a stranger must not be able to overwrite
  contact details.

## Duplicate payment references

- **Decision**: trim and upper-case the reference; partial unique index on `(booking_id, reference)` where
  the reference isn't blank and the status isn't `rejected`. An `IntegrityError` also returns `409`.
- **Rationale**: the index also covers double-taps. A rejected reference may be resubmitted in case of an
  admin mistake.

## Lookups and guessing

- **Decision**: `POST /public/track` keeps the phone out of URLs. Unknown number, wrong phone and invalid
  phone return the same `404`.
- **Rate limits**: in-memory sliding window per IP. 20 failed lookups per 10 minutes; 10 created bookings
  per 10 minutes.
- **Rationale**: only failures count, because many mobile users share a carrier IP. No per-booking lockout,
  which would let an attacker lock a customer out. In-memory is enough for one API process.
- **Deployment note**: uvicorn needs `--proxy-headers` behind a host's proxy (feature 006).

## Email

- **Decision**: plain text through Resend, sent by `BackgroundTasks` after the commit. An empty
  `RESEND_API_KEY` logs instead of sending; failures are logged and never raised. Business address is the
  `notification_email` setting, falling back to `ADMIN_EMAIL`.
- **Rationale**: FR-009. Plain text avoids HTML injection. The customer email carries no text the customer
  typed, so it can't relay arbitrary messages to another address.
- **Language**: customer email in the booking's language; business emails carry both.

## Add-on holds

- **Decision**: a request holds nothing; only Confirmed or later does, per 001.
- **Follow-up**: 003 must re-check capacity when confirming.
