# Implementation Plan: Pricing, Availability & Public Quote

**Branch**: `001-pricing-availability` (tracked on `build`) | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-pricing-availability/spec.md`

## Summary

Add the pure pricing engine (`services/pricing.py`), the add-on availability and rush/notice checks
(`services/availability.py`), and a public, login-free API: catalog read endpoints plus
`POST /public/quote`. The pricing math is pure functions over plain dataclasses (no DB), so it can be
tested exhaustively and test-first; a thin loader reads catalog rows and settings from the DB and
feeds them in. No schema change: Phase 1 models already carry `units_per_pack`, `base_hours`,
tiers, add-on capacity, zones/areas and the settings keys (`min_order`, `notice_days`,
`notice_days_servers`, `deposit_percent`, `balance_due_days`).

## Technical Context

**Language/Version**: Python 3.12 (backend only in this feature)

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, Pydantic v2 (all already in `backend/pyproject.toml`)

**Storage**: Supabase Postgres via existing models in `backend/app/models/`; tests use SQLite (aiosqlite) through `tests/conftest.py`

**Testing**: pytest + pytest-asyncio; pure unit tests for pricing, DB-backed tests for availability and the endpoints (FastAPI `TestClient`/httpx with the session dependency overridden)

**Target Platform**: Linux container on Render/Railway; local Windows dev

**Project Type**: Web service (backend of a web app)

**Performance Goals**: quote returned in < 2 s end-to-end (SC-002); target < 200 ms server time with a handful of queries

**Constraints**: integer TZS only; no cost data in public responses; "today" evaluated in Africa/Dar_es_Salaam (UTC+3)

**Scale/Scope**: ~15 products, 4 packages, 4 add-ons, ~25 areas; tens of bookings per week

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Server-owned logic | All math in `app/services/`; frontend untouched; quote endpoint is the only source of totals | PASS |
| II. Test-first money logic | Tasks write `tests/test_pricing.py` / `test_availability.py` cases first and see them fail | PASS |
| III. Integer TZS | Quantities via exact `Decimal`/`Fraction` then `ceil`; money as `int`; deposit rounded up | PASS |
| IV. Role boundaries | Public schemas have no `cost_price`/`unit_cost` fields; test asserts absence | PASS |
| V. Bilingual | Response lines carry `name_sw` and `name_en`; flags are codes, not prose | PASS |
| VI. Configurable | min order, notice days, deposit %, balance days read from `settings` | PASS |
| VII. Simplicity | No new tables, no caching, no auth on public routes | PASS |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/001-pricing-availability/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/public-api.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                    # include public router
│   ├── services/
│   │   ├── settings_store.py      # NEW: typed read of settings table
│   │   ├── catalog_loader.py      # NEW: DB rows → pricing dataclasses
│   │   ├── pricing.py             # NEW: pure quote calculation
│   │   └── availability.py        # NEW: add-on capacity over windows, rush check
│   ├── schemas/
│   │   └── public.py              # NEW: Pydantic request/response models
│   └── routers/
│       └── public.py              # NEW: /public/catalog, /packages, /addons, /areas, /quote
└── tests/
    ├── test_pricing.py            # NEW: pure unit tests (bulk of coverage)
    ├── test_availability.py       # NEW: DB-backed overlap tests
    └── test_public_api.py         # NEW: endpoint tests on seeded SQLite
```

**Structure Decision**: Existing web-app layout (`backend/`, `frontend/`). This feature touches only
`backend/`. Routes are mounted without the `/api` prefix because the Vite proxy and production
rewrite strip it (`frontend/vite.config.ts`).

## Complexity Tracking

No violations.
