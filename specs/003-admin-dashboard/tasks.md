---

description: "Tasks for 003 Admin Dashboard"
---

# Tasks: Admin Dashboard

**Input**: Design documents from `specs/003-admin-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-api.md

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

- [X] T002 Add `refund_due` and `internal_notes` to `Booking` in `backend/app/models/booking.py`
- [X] T003 Write the Alembic migration in `backend/alembic/versions/` with a working downgrade
- [X] T004 Add `--staff-email` to `backend/app/seed.py`, with a test in `backend/tests/test_seed.py`
- [X] T005 Test-first: `backend/tests/test_admin_api.py`. `/admin/me` returns `401` with no token, `403` for planners, and the profile for staff and owner
- [X] T006 Create `backend/app/routers/admin.py` with `/admin/me` and `backend/app/schemas/admin.py`; mount in `backend/app/main.py`

**Checkpoint**: the admin router exists and is gated.

---

## Phase 3: User Story 1 - See and manage bookings (P1) MVP

**Goal**: staff and owner find a booking and see everything about it; only the owner sees cost and profit.

**Independent Test**: log in as staff, find a booking by number and by phone, open it and see payments and history.

- [X] T007 [US1] Test-first in `backend/tests/test_admin_api.py`: overview splits today and upcoming in EAT and leaves out cancelled and closed; list filters by stage, date range and rush; search by number, name and phone in any format; paging; detail holds items, add-ons, payments and history; `PATCH` saves EFD number and internal notes (FR-011); internal notes absent from `/public/track`
- [X] T008 [US1] Test-first in `backend/tests/test_admin_api.py`: walk every staff booking response and fail on any key containing `cost`, `profit` or `margin`; owner detail has `financials` with profit excluding the empties deposit and using snapshotted costs
- [X] T009 [US1] Implement `backend/app/services/admin_queries.py`, booking schemas in `backend/app/schemas/admin.py`, and the overview, list, detail and `PATCH` endpoints

**Checkpoint**: bookings readable through the API, with the role boundary tested.

---

## Phase 4: User Story 2 - Payments and stages (P1)

**Goal**: staff confirm money and move bookings; disallowed moves are refused with a reason.

**Independent Test**: confirm a deposit → can move to Confirmed; try without → refused; cancel 10 days out → refund is 50% of the deposit.

- [X] T010 [US2] Test-first: `backend/tests/test_refund.py`. `cancellation_refund` at 15, 14, 13, 10, 7, 6, 3 and 0 days; odd amounts round down; `refund_due` with nothing paid, part of the deposit, the exact deposit and full payment
- [X] T011 [US2] Implement `cancellation_refund` and `deposit_for` in `backend/app/services/pricing.py`; use `deposit_for` in `build_quote` with no behaviour change
- [X] T012 [US2] Test-first: `backend/tests/test_booking_flow.py`. Every allowed move; `invalid_move` for the rest; `deposit_not_paid`, `not_fully_paid`, `rush_not_approved`, `provisional`, `addons_unavailable`; back moves need owner and note; closed and cancelled are final; each change writes a history row with the actor; `allowed_moves` agrees with what enforcing does
- [X] T013 [US2] Test-first in `backend/tests/test_booking_flow.py`: confirm records actor and time and updates paid; second confirm `already_confirmed`; reject pending and confirmed; `payment_needed_by_stage`; confirm on a cancelled booking refused
- [X] T014 [US2] Test-first in `backend/tests/test_booking_flow.py`: cancel fixes `refund_due`; `pending_payments`; refund records up to `refund_due`, then `refund_exceeds_due`; refund records don't change paid
- [X] T015 [US2] Test-first in `backend/tests/test_booking_flow.py`: date change free once at 7+ days; second and under-7 refused; owner exception needs a note, staff can't use it; `date_inside_notice`; add-on clash refused even with an exception, ignoring the booking's own hold; setup, collection and balance date move; prices unchanged
- [X] T016 [US2] Test-first in `backend/tests/test_booking_flow.py`: rush approve lets the booking proceed; decline cancels with everything paid due back at any date; `not_rush`; both refused past Quoted. Delivery fee recomputes total and deposit and clears provisional; `not_provisional`; refused past Quoted
- [X] T017 [US2] Implement `backend/app/services/booking_flow.py` with `StageRefused(code)`, booking and add-on locks
- [X] T018 [US2] Test-first in `backend/tests/test_admin_api.py`: each action endpoint returns the updated detail; refusals are `409` with a code; owner-only rules hold over HTTP; staff responses from every action pass the key walk
- [X] T019 [US2] Add the action endpoints to `backend/app/routers/admin.py` and their schemas

**Checkpoint**: backend for bookings complete.

---

## Phase 5: Admin screens for US1 and US2

- [ ] T020 Add types and calls to `frontend/src/lib/adminApi.ts`
- [ ] T021 Vitest in `frontend/src/pages/admin/AdminLayout.test.tsx`: no session goes to `/login`; `403` shows not-allowed; staff don't see owner-only links
- [ ] T022 [P] [US1] Vitest in `frontend/src/pages/admin/BookingList.test.tsx`: filters and search reach the API; rows show stage and rush
- [ ] T023 [US2] Vitest in `frontend/src/pages/admin/BookingDetail.test.tsx`: refused moves show the server's reason in the current language; confirm calls the API; cancel shows the preview first; financials only when the response has them
- [ ] T024 [US1] Implement `AdminLayout`, `Dashboard`, `BookingList` in `frontend/src/pages/admin/`, the `/admin` routes in `frontend/src/App.tsx`, and strings in `frontend/src/i18n/sw.json` and `en.json`
- [ ] T025 [US2] Implement `frontend/src/pages/admin/BookingDetail.tsx`: payments, history, stage buttons, cancel and refund, date change, rush, delivery fee, EFD number and notes, with strings for every refusal code

**Checkpoint**: staff can run a booking end to end in the browser.

---

## Phase 6: User Story 3 - Calendar (P2)

**Goal**: see bookings and add-on usage against capacity per day.

**Independent Test**: two bookings on one Saturday → the calendar shows both and combined add-on usage.

- [ ] T026 [US3] Test-first: `backend/tests/test_admin_calendar.py`. Every day in range appears; two bookings combine; a multi-day window counts on each day; requests and cancelled bookings show no usage; non-overlapping bookings on one day peak, not sum; unlimited add-ons report null; range limit; no cost keys for staff
- [ ] T027 [US3] Implement daily usage in `backend/app/services/availability.py` and `GET /admin/calendar`
- [ ] T028 [US3] Vitest and implementation: `frontend/src/pages/admin/Calendar.tsx` with month and week views, strings

---

## Phase 7: User Story 4 - Catalog, zones, venues, settings (P2)

**Goal**: the owner changes prices and options without a developer.

**Independent Test**: change a tier price → the next quote uses it; existing bookings keep their old price.

- [ ] T029 [US4] Test-first: `backend/tests/test_catalog_admin.py`. Tier validation; `in_use` on each delete rule in `data-model.md`; deleting unused records works; setting validation
- [ ] T030 [US4] Implement `backend/app/services/catalog_admin.py`
- [ ] T031 [US4] Test-first in `backend/tests/test_catalog_admin.py`: price change reaches a new quote and leaves a booking unchanged; deactivated product leaves `/public/catalog`, `/public/packages` rules and quotes; staff get `403` on all writes, read without `cost_price` or `replacement_cost`, and can read settings
- [ ] T032 [US4] Add catalog, zone, area, venue and settings endpoints and schemas; filter inactive products' rules in `backend/app/routers/public.py`
- [ ] T033 [US4] Vitest in `frontend/src/pages/admin/Settings.test.tsx` and `Catalog.test.tsx`: read-only for staff; no cost column for staff; refusal shown on repeated tier
- [ ] T034 [US4] Implement `Catalog`, `ZonesVenues`, `Settings` in `frontend/src/pages/admin/`, strings

---

## Phase 8: Polish

- [ ] T035 Run the full suites plus `npm run build` and `npm run lint`; run the migration on a throwaway SQLite file and review the offline Postgres SQL
- [ ] T036 Walk through `specs/003-admin-dashboard/quickstart.md` in a browser against a throwaway database; record the results and what wasn't exercised, including Postgres row locking

---

## Dependencies

- Phase 2 blocks all stories.
- US1 before US2: actions return the detail response.
- Phase 5 needs the US1 and US2 backend.
- US3 and US4 need only Phase 2 and the admin shell from T024.

## Parallel Opportunities

T010 and T029 touch separate files. US3 and US4 can proceed in parallel after Phase 5.

## Implementation Strategy

US1 and US2 together are the MVP: staff can act on real bookings. Commit per task group, and stop at each commit for review.
