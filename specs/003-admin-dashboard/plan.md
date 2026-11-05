# Implementation Plan: Admin Dashboard

**Branch**: `003-admin-dashboard` (tracked on `build`) | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-admin-dashboard/spec.md`

## Summary

Give staff and the owner a logged-in area to run bookings. The backend adds a role-gated `/admin` router,
stage rules with refusal codes, payment confirmation, cancellation refunds, date changes, rush decisions, a
calendar with add-on usage, and catalog and settings management. The frontend adds an `/admin` area in Swahili
and English. All rules live on the server, which tells the browser which moves are allowed and why not.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 7 with React 19

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Pydantic v2; React Router, TanStack Query, react-i18next, Tailwind. No new dependencies.

**Storage**: Supabase Postgres. One Alembic migration. Tests use SQLite through `tests/conftest.py`.

**Testing**: pytest + pytest-asyncio with httpx against the app; Vitest + Testing Library

**Target Platform**: Linux container (API), Vercel (frontend), staff phones and laptops

**Project Type**: Web application (`backend/`, `frontend/`)

**Performance Goals**: confirm a payment and move to Confirmed in under 1 minute (SC-001)

**Constraints**: integer TZS; no cost, margin or profit in staff responses; "today" is in EAT (UTC+3); every refusal carries a code the UI can translate

**Scale/Scope**: tens of bookings per week; a handful of staff; one API process

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Server-owned logic | Stage, refund and date rules live in `services/booking_flow.py` and `services/pricing.py`; the detail response carries `allowed_moves` so the browser repeats no rule | PASS |
| II. Test-first money logic | Refund, stage, payment and date-change tests are written and seen failing first; admin screens with logic have Vitest tests | PASS |
| III. Integer TZS & snapshots | Catalog edits never touch `booking_items` / `booking_addons`; each refund is its own payment record; `refund_due` is fixed at cancellation because it depends on that day | PASS |
| IV. Role boundaries | Every endpoint uses `require_role`; separate staff and owner schemas; a test walks staff responses for cost, profit and margin keys | PASS |
| V. Bilingual | All admin text in `sw.json` / `en.json`, including refusal reasons; key-parity test covers it | PASS |
| VI. Configurable | Settings edited in admin; notice days and balance days read from `settings`; catalog is data | PASS |
| VII. Simplicity | No new dependency; hand-built calendar; image URL field instead of upload; no user-management screen | PASS |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/003-admin-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/admin-api.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/              # NEW migration: refund_due, internal_notes
├── app/
│   ├── main.py                    # mount the admin router
│   ├── models/booking.py          # two new columns
│   ├── routers/admin.py           # NEW
│   ├── routers/public.py          # /packages leaves out inactive products' rules
│   ├── schemas/admin.py           # NEW: staff and owner shapes
│   ├── seed.py                    # --staff-email
│   └── services/
│       ├── pricing.py             # cancellation_refund, deposit_for
│       ├── availability.py        # calendar usage per day
│       ├── booking_flow.py        # NEW: stages, payments, cancel, date change, rush, delivery fee
│       ├── admin_queries.py       # NEW: overview, list, detail loading
│       └── catalog_admin.py       # NEW: tier validation, in-use checks
└── tests/                         # test_refund, test_booking_flow, test_admin_api,
                                   # test_admin_calendar, test_catalog_admin

frontend/src/
├── App.tsx                        # /admin routes
├── i18n/{sw,en}.json
├── lib/adminApi.ts                # NEW
└── pages/admin/                   # AdminLayout, Dashboard, BookingList, BookingDetail,
                                   # Calendar, Catalog, ZonesVenues, Settings
```

**Structure Decision**: Existing web-app layout. Routes mount without `/api` because the proxy strips it.

## Complexity Tracking

No violations.
