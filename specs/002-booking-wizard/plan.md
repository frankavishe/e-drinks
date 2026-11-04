# Implementation Plan: Booking Wizard, Tracking & Payment References

**Branch**: `002-booking-wizard` (tracked on `build`) | **Date**: 2026-11-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-booking-wizard/spec.md`

## Summary

Turn a quote into a saved booking. The backend adds phone normalisation, booking creation with
snapshotted prices and yearly numbers, tracking by number + phone, pending payment references, plain-text
notification emails and failure-based rate limits. The frontend adds a mobile-first booking wizard, a
WhatsApp handoff and a tracking page. Submitting re-prices on the server through the same code as
`/public/quote`, and nothing is saved if the result differs from what the customer reviewed.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 7 with React 19

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Pydantic v2, resend (all in `backend/pyproject.toml`); React Router, TanStack Query, react-i18next, Tailwind (all in `frontend/package.json`). No new dependencies.

**Storage**: Supabase Postgres. One Alembic migration. Tests use SQLite through `tests/conftest.py`.

**Testing**: pytest + pytest-asyncio with httpx against the app; Vitest + Testing Library

**Target Platform**: Linux container (API), Vercel (frontend), customers' phones

**Project Type**: Web application (`backend/`, `frontend/`)

**Performance Goals**: booking completed on a phone in under 5 minutes (SC-001); business email within 1 minute (SC-003)

**Constraints**: integer TZS; no cost fields in public responses; lookups need number + matching phone; "today" and the booking-number year are in EAT (UTC+3)

**Scale/Scope**: tens of bookings per week; one API process

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Server-owned logic | Totals, rush, minimum and balances come from `app/services/`; the browser only formats them | PASS |
| II. Test-first money logic | Booking, payment-summary and phone tests are written and seen failing first; wizard behaviour has Vitest tests | PASS |
| III. Integer TZS & snapshots | `booking_items.unit_price` / `unit_cost` and `booking_addons.unit_price` copied at creation; each payment is a record; balance derived | PASS |
| IV. Role boundaries | Public schemas have no cost fields, asserted in tests; `unit_cost` is stored but never returned | PASS |
| V. Bilingual | All UI text in `sw.json` / `en.json` with a key-parity test; emails in both languages | PASS |
| VI. Configurable | WhatsApp number, payment details, policy text and notification address read from `settings` | PASS |
| VII. Simplicity | No new dependency; in-memory limiter; automated WhatsApp/SMS and online payments stay out | PASS |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/002-booking-wizard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/public-api.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/              # NEW migration: counters, unique phone, payment index
├── app/
│   ├── models/booking.py          # BookingCounter, constraints
│   ├── schemas/public.py          # booking, tracking, payment and settings shapes
│   ├── routers/public.py          # new endpoints
│   ├── seed.py                    # notification_email setting
│   └── services/
│       ├── phone.py               # NEW
│       ├── quoting.py             # NEW: shared by /quote and booking creation
│       ├── bookings.py            # NEW
│       ├── notify.py              # NEW
│       ├── rate_limit.py          # NEW
│       └── settings_store.py      # public settings loader
└── tests/                         # test_phone, test_bookings, test_booking_api,
                                   # test_tracking_api, test_notify, test_rate_limit

frontend/src/
├── App.tsx                        # /book and /track routes
├── i18n/{sw,en}.json
├── lib/{api.ts,publicApi.ts}
└── pages/
    ├── book/                      # BookingWizard, steps, Confirmation
    ├── Track.tsx
    └── PaymentForm.tsx
```

**Structure Decision**: Existing web-app layout. Routes mount without `/api` because the proxy strips it.

## Complexity Tracking

No violations.
