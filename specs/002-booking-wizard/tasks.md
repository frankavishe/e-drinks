---

description: "Tasks for 002 Booking Wizard, Tracking & Payment References"
---

# Tasks: Booking Wizard, Tracking & Payment References

**Input**: Design documents from `specs/002-booking-wizard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md

**Tests**: Required. Constitution II makes test-first mandatory for money, quantity and rule logic: write
each test task, run it and see it fail, then implement. Frontend logic has Vitest tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Paths are relative to the repo root

---

## Phase 1: Setup

- [X] T001 Run `pytest` in `backend/` and `npm test` in `frontend/` to confirm both suites are green before starting

---

## Phase 2: Foundational (blocks all stories)

- [X] T002 [P] Test-first: `backend/tests/test_phone.py`. `0712345678`, `255712345678`, `+255 712-345-678` and `0612345678` normalise to `255…`; landlines, foreign numbers, wrong lengths and text are rejected
- [X] T003 Implement `normalise_phone` in `backend/app/services/phone.py`
- [X] T004 Add `BookingCounter`, unique `customers.phone` and partial unique index `uq_payments_booking_reference` ("where `reference <> '' AND status <> 'rejected'`") in `backend/app/models/booking.py`; export from `backend/app/models/__init__.py`
- [X] T005 Write the Alembic migration in `backend/alembic/versions/` with RLS on `booking_counters` for Postgres, and a working downgrade
- [X] T006 Move the shared quote steps from `backend/app/routers/public.py` into `backend/app/services/quoting.py`; existing `tests/test_public_api.py` stays green
- [X] T007 Test-first in `backend/tests/test_settings_store.py`: public settings loader returns only the whitelisted keys. Implement in `backend/app/services/settings_store.py`; add `notification_email` to `backend/app/seed.py`
- [X] T008 [P] Test-first: `backend/tests/test_rate_limit.py`. Blocks past the limit, recovers after the window, keys are independent. Implement `backend/app/services/rate_limit.py`
- [X] T009 Extend `ApiError` in `frontend/src/lib/api.ts` with `code` and `quote`; add types, calls, `formatTzs` to `frontend/src/lib/publicApi.ts`

**Checkpoint**: schema, shared quote code and limiter ready.

---

## Phase 3: User Story 1 - Book an event without an account (P1) MVP

**Goal**: a customer completes the wizard and gets a booking number with totals equal to the quote.

**Independent Test**: complete the wizard in Swahili for a 300-guest Silver wedding at a Masaki venue; the number is issued with the same totals as the quote.

- [X] T010 [US1] Test-first: `backend/tests/test_bookings.py`. Sequential numbers with yearly reset; saved totals equal the quote (Silver, 300 guests, Masaki); snapshots survive a later price change; `unit_cost` copied; rush and provisional saved; same phone reuses the customer, keeping the name and filling a blank email; first history row
- [X] T011 [US1] Implement `create_booking` in `backend/app/services/bookings.py`
- [X] T012 [US1] Test-first: `backend/tests/test_booking_api.py`. `201` shape with no cost fields; `409` for `addons_unavailable`, `below_minimum` and `quote_changed` with nothing saved; `422` for policy or 18+ not accepted (must be true), invalid phone, venue not in the area; creation rate limit
- [X] T013 [US1] Add schemas to `backend/app/schemas/public.py` and `GET /public/settings` and `POST /public/bookings` to `backend/app/routers/public.py`
- [X] T014 [US1] Vitest in `frontend/src/pages/book/BookingWizard.test.tsx`: language switch keeps data; submit blocked until both boxes are ticked; venue autofill; `409` shown at review
- [X] T015 [US1] Implement `frontend/src/pages/book/` (`BookingWizard`, `EventStep`, `OrderStep`, `AddonsStep`, `ReviewStep`, `ContactStep`, `Confirmation`), the `/book` route in `frontend/src/App.tsx`, and strings in `frontend/src/i18n/sw.json` and `en.json`

**Checkpoint**: bookings can be created end to end.

---

## Phase 4: User Story 2 - Hand off to WhatsApp (P1)

**Goal**: the confirmation screen opens WhatsApp with a prefilled message.

**Independent Test**: the link holds the business number and booking number.

- [X] T016 [US2] Vitest in `frontend/src/lib/publicApi.test.ts`: `whatsappLink` holds the number and encoded message, in both languages
- [X] T017 [US2] Implement `whatsappLink` in `frontend/src/lib/publicApi.ts` and the button in `frontend/src/pages/book/Confirmation.tsx`

---

## Phase 5: User Story 3 - Track a booking and submit a payment reference (P1)

**Goal**: number + phone shows the booking; a reference shows as pending.

**Independent Test**: right phone shows details; wrong phone is not found; a deposit reference shows as pending.

- [X] T018 [US3] Test-first in `backend/tests/test_bookings.py`: `find_booking` across phone formats; `submit_payment` trims and upper-cases, rejects duplicates, allows a rejected reference again, accepts oversized amounts, refuses cancelled and closed bookings; `payment_summary` counts only confirmed deposit and balance as paid
- [X] T019 [US3] Implement `find_booking`, `submit_payment`, `payment_summary` in `backend/app/services/bookings.py`
- [X] T020 [US3] Test-first: `backend/tests/test_tracking_api.py`. Identical `404`s for unknown number, wrong phone and invalid phone; response shape with no cost fields; payment `201`, duplicate `409`; failed-lookup rate limit on both endpoints, and successes not counted
- [X] T021 [US3] Add schemas and `POST /public/track`, `POST /public/bookings/{code}/payments` in `backend/app/schemas/public.py` and `backend/app/routers/public.py`
- [X] T022 [US3] Vitest in `frontend/src/pages/Track.test.tsx`: not-found message; details shown; a submitted reference shows as pending; duplicate message
- [X] T023 [US3] Implement `frontend/src/pages/Track.tsx`, `frontend/src/pages/PaymentForm.tsx`, the `/track` route and strings

---

## Phase 6: User Story 4 - The business is told by email (P2)

**Goal**: emails for new bookings and payment references.

**Independent Test**: with email in test mode, a booking and a reference record two notifications with the booking number.

- [X] T024 [US4] Test-first: `backend/tests/test_notify.py`. Contents per the contract table; customer email in the booking's language and free of customer-typed text; business emails in both languages; no customer email without an address; sender failure is logged and the booking or payment is still saved; empty API key logs instead of sending
- [X] T025 [US4] Implement `backend/app/services/notify.py` and queue emails with `BackgroundTasks` in `backend/app/routers/public.py`

---

## Phase 7: Polish

- [X] T026 [P] Vitest in `frontend/src/i18n/i18n.test.ts`: `sw.json` and `en.json` have identical keys
- [ ] T027 Run the full suites plus `npm run build` and `npm run lint`; run the migration on a throwaway SQLite file and review the offline Postgres SQL
- [ ] T028 Walk through `specs/002-booking-wizard/quickstart.md` in a browser at phone width against a throwaway database; record the results and what wasn't exercised

---

## Dependencies

- Phase 2 blocks all stories.
- US1 comes first: US2 extends its confirmation screen, and US3 and US4 need saved bookings.
- US2, US3 and US4 are independent of each other.

## Parallel Opportunities

T002 and T008 touch separate files. US2, US3 and US4 can proceed in parallel after US1.

## Implementation Strategy

US1 alone is the MVP: it captures orders. Commit per task group.
