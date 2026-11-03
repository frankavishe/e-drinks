# e-drinks Constitution

e-drinks is an event drinks booking platform for weddings and events in Dar es Salaam.
The source of settled business rules is `Frank plan.md`; this constitution fixes the rules
every feature spec, plan and task MUST obey.

## Core Principles

### I. Server-Owned Business Logic

- All pricing, availability, stock, booking-stage, refund, settlement and commission logic MUST
  live in the FastAPI backend under `backend/app/services/`, never in the browser.
- The frontend MUST get data only through the FastAPI API. Supabase JS is used **only** for login
  (planners, staff, owner).
- Every Supabase table MUST have Row Level Security enabled with no public policies, so the browser
  cannot read tables directly.
- Any total the client shows MUST come from the server; the client never recalculates prices.

Rationale: one source of truth for money and stock, and no leakage of cost data.

### II. Test-First Money Logic (NON-NEGOTIABLE)

- Code that computes money, quantities, availability or stage transitions MUST have pytest tests
  written before the implementation and seen to fail first (red → green → refactor).
- `services/pricing.py` is the core and MUST have the broadest coverage: tiers, package rounding,
  zone fees, empties deposit, 50% deposit, cancellation refunds at each policy boundary.
- Every bug fix in these areas MUST add a regression test.
- Frontend behaviour with logic (wizard steps, forms) MUST have Vitest tests.

### III. Integer TZS & Snapshotted Prices

- Money MUST be stored and computed as integer TZS (no floats, no decimals), VAT-inclusive.
- Quantities derived from packages MUST be rounded **up** to whole packs (crates).
- Unit price and unit cost MUST be snapshotted on `booking_items` / `booking_addons` when a booking
  is created; later catalog changes MUST NOT change existing bookings.
- Every payment (deposit, balance, refund, damage) is its own record; balances are derived, never
  overwritten.

### IV. Role Boundaries

- Roles are Customer (no account; tracks a booking by booking number + phone), Planner, Staff,
  Owner.
- Cost price, profit and margin MUST be visible only to Owner. Staff and Planner API responses MUST
  NOT include them; this MUST be covered by tests.
- Admin endpoints MUST be gated with `require_role(...)` from `backend/app/auth.py`.
- Unapproved planners MUST NOT book with commission. Commission is earned only when a booking
  reaches Closed.

### V. Swahili-First Bilingual

- Every user-facing string, email and PDF MUST exist in Swahili (default) and English.
- Frontend text goes through react-i18next (`frontend/src/i18n/sw.json`, `en.json`); no
  hard-coded UI strings.
- Catalog content carries `_sw` / `_en` fields.

### VI. Configurable, Not Hard-Coded

- Business values that the owner may change (business name, TIN, minimum order, notice days,
  payment numbers, bank details, policy text, WhatsApp number) MUST be read from the `settings`
  table, never hard-coded.
- Catalog data (products, tiers, packages, add-ons, zones, areas) is data, managed in admin.

### VII. Simplicity & Phase Discipline

- Build only what the current feature spec requires (YAGNI). Phase-2 items are out of scope until
  explicitly specified: AzamPay/Selcom online payments, automated SMS/WhatsApp, VFD integration,
  phone OTP login, delivery tracking, other cities.
- Payments in phase 1 are manual: customer submits a mobile-money/bank reference, admin confirms.
- Schema changes MUST go through Alembic migrations; Alembic owns the schema.

## Technology & Platform Constraints

- Backend: Python, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic v2, pytest.
- Frontend: Vite, React, TypeScript, Tailwind, react-router, react-i18next, TanStack Query, Vitest.
- Platform: Supabase (Postgres, Auth email/password, Storage for images), region EU.
- Auth: Supabase JWT verification supporting HS256 and asymmetric keys via JWKS.
- PDFs: ReportLab (WeasyPrint rejected: no GTK on Windows). Email: Resend.
- Hosting: Vercel (frontend), Render or Railway (API), Supabase cloud; `.co.tz` domain.
- Secrets live only in `.env` files (never committed); `.env.example` documents every variable.

## Development Workflow

- Work is spec-driven with Spec Kit: `/speckit-specify` → (`/speckit-clarify`) → `/speckit-plan`
  → `/speckit-tasks` → (`/speckit-analyze`) → `/speckit-implement`, one feature at a time in
  build order, since each feature builds on the one before.
- Each feature's plan MUST pass the Constitution Check against these principles; any violation
  MUST be justified in the plan's Complexity Tracking table.
- Before a feature is marked done: `pytest` (in `backend/`) and `npm test` (in `frontend/`) pass,
  and the feature's acceptance scenarios have been exercised against a running API + frontend.
- Commits are small and per task group; messages describe the change.

## Governance

- This constitution supersedes other practice documents. Where it conflicts with `Frank plan.md`,
  amend one of them explicitly rather than silently diverging.
- Amendments are made with `/speckit-constitution`, recorded with a version bump:
  MAJOR for removed/redefined principles, MINOR for added principles or sections, PATCH for wording.
- Every plan and code review MUST verify compliance with the Core Principles.

**Version**: 1.0.0 | **Ratified**: 2026-11-03 | **Last Amended**: 2026-11-03
