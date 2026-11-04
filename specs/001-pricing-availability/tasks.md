---

description: "Tasks for 001 Pricing, Availability & Public Quote"
---

# Tasks: Pricing, Availability & Public Quote

**Input**: Design documents from `specs/001-pricing-availability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md

**Tests**: Required. Constitution II makes test-first mandatory for money logic: write each test task,
run it and see it fail, then implement.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Paths are relative to the repo root; backend code is under `backend/app/`, tests under `backend/tests/`

---

## Phase 1: Setup

- [X] T001 Create empty modules `backend/app/schemas/__init__.py`, `backend/app/schemas/public.py`, `backend/app/routers/public.py`; run `pytest` to confirm the Phase-1 suite is green before starting

---

## Phase 2: Foundational (blocks all stories)

- [X] T002 [P] Test-first: `backend/tests/test_settings_store.py`, which reads the seeded settings as typed ints (min_order, notice_days, notice_days_servers, deposit_percent, balance_due_days), with defaults when a key is missing
- [X] T003 Implement `backend/app/services/settings_store.py`: `async load_pricing_settings(session) -> PricingSettings`
- [X] T004 Define dataclasses in `backend/app/services/pricing.py`: ProductInfo, PackageInfo, AddonInfo, PricingSettings, QuoteRequest, QuoteLine, AddonLine, Quote, plus `QuoteError`/`CatalogError` (per data-model.md)
- [X] T005 Test-first: `backend/tests/test_catalog_loader.py`. Load the seeded catalog into dataclasses; inactive products/packages/add-ons are excluded; no cost field exists on ProductInfo
- [X] T006 Implement `backend/app/services/catalog_loader.py` (products with tiers, packages with rules, add-ons, area→zone fee lookup)
- [X] T007 Add a `seeded_session` fixture to `backend/tests/conftest.py` that runs `app.seed.seed(session)` on SQLite, plus an httpx `AsyncClient` fixture that overrides `get_session`

**Checkpoint**: settings and catalog load into plain types; pricing can be built as pure functions.

---

## Phase 3: User Story 1 - Instant price for a package event (P1) 🎯 MVP

**Goal**: package + guests + hours + area → correct lines, delivery, empties, total, deposit, balance date.

**Independent Test**: the quickstart Silver/300 guests/Masaki example matches the hand calculation.

- [X] T008 [US1] Test-first in `backend/tests/test_pricing.py`: package rounding (225 bottles / 24 → 10 crates; exact multiple stays exact; Fraction 300×0.1 = 30 bottles is exact), per_hour scaling (10 h on base 5 doubles; non-per-hour rule unchanged), inactive product skipped
- [X] T009 [US1] Test-first in `backend/tests/test_pricing.py`: tier selection at 1, 9, 10, 49, 50 packs; no tier for qty → CatalogError
- [X] T010 [US1] Test-first in `backend/tests/test_pricing.py`: zone delivery fee, empties deposit only on returnable products (packs × per-pack deposit), total = subtotal + addons + delivery + empties, deposit = ceil(total × 50 / 100) for odd totals, balance_due_date = event − 3 days
- [X] T011 [US1] Implement `package_quantities()`, `tier_price()`, and `build_quote()` (lines, delivery, empties, totals, deposit, balance date) in `backend/app/services/pricing.py` until T008–T010 pass
- [X] T012 [P] [US1] Pydantic schemas in `backend/app/schemas/public.py` per `contracts/public-api.md` (QuoteIn with validation rules from data-model.md; QuoteOut; catalog/package/addon/area outputs, all without cost fields)
- [X] T013 [US1] Test-first: `backend/tests/test_public_api.py` covering GET `/public/catalog`, `/public/packages`, `/public/addons`, `/public/areas` and a package POST `/public/quote` on seeded data; assert that no key containing "cost" appears anywhere in the responses
- [X] T014 [US1] Implement `backend/app/routers/public.py` (read endpoints + `/public/quote` wiring loader → availability → pricing) and include the router in `backend/app/main.py`

**Checkpoint**: MVP: a package quote works end to end.

---

## Phase 4: User Story 2 - Custom order and edited quantities (P1)

**Independent Test**: custom 12 soda + 3 beer quote; override a package line; below-minimum flag.

- [X] T015 [US2] Test-first in `backend/tests/test_pricing.py`: custom items priced by tier; override replaces a package line; override 0 removes the line; override for a product not in the package adds it; below_minimum computed on subtotal + addons_total only (R6)
- [X] T016 [US2] Extend `build_quote()` in `backend/app/services/pricing.py` for items/overrides/min-order until T015 passes
- [X] T017 [US2] Add API tests in `backend/tests/test_public_api.py`: both package_id and items → 422; unknown or inactive product → 422; guests/hours/packs ≤ 0 → 422; collect_at ≤ setup_at → 422; custom quote 200

---

## Phase 5: User Story 3 - Add-ons only when available (P2)

**Independent Test**: 10 coolers owned, 7 held on an overlapping booking → asking for 4 is refused (3 available).

- [X] T018 [US3] Test-first: `backend/tests/test_availability.py` (DB): overlapping confirmed booking reduces free count; touching windows don't conflict; cancelled/request/closed/returns_settled bookings don't hold; two bookings that overlap the window but not each other count as the peak, not the sum (R4); next-morning collection; `exclude_booking_id`; unlimited capacity (ice)
- [X] T019 [US3] Implement `async addon_availability(session, addon_ids, setup_at, collect_at, exclude_booking_id=None) -> dict[int, int | None]` in `backend/app/services/availability.py`
- [X] T020 [US3] Test-first in `backend/tests/test_pricing.py`: add-on lines priced (servers per shift), `ok=false` + `available` when qty > free, `addons_unavailable` lists ids, total still computed
- [X] T021 [US3] Wire add-on pricing and availability into `build_quote()` and the `/public/quote` route; API test asking for 21 coolers → `ok: false, available: 20`

---

## Phase 6: User Story 4 - Rush requests (P2)

**Independent Test**: 2 days ahead → rush; servers + 5 days → rush; servers + 8 days → not rush.

- [X] T022 [US4] Test-first in `backend/tests/test_availability.py`: `is_rush(event_date, today, has_staff_addon, settings)` at boundaries (exactly notice days → not rush; notice − 1 → rush); bartender counts as staff; past date → QuoteError
- [X] T023 [US4] Implement `is_rush()` and `today_eat()` in `backend/app/services/availability.py` and set `flags.is_rush` in the quote; API test where changing the `notice_days` setting changes the result (SC-004)

---

## Phase 7: User Story 5 - Unlisted area (P3)

- [ ] T024 [US5] Test-first in `backend/tests/test_pricing.py` + `test_public_api.py`: `custom_area` → delivery_fee 0, delivery_custom + provisional true, deposit on provisional total; both area_id and custom_area → 422; unknown area_id → 422
- [ ] T025 [US5] Implement custom-area handling in `backend/app/services/pricing.py` and `backend/app/routers/public.py`

---

## Phase 8: Polish

- [ ] T026 [P] Run full `pytest`; run quickstart.md manually against a seeded dev DB and record the Silver example figures
- [ ] T027 [P] Update `README.md` with the public API endpoints and a curl example

---

## Dependencies & Execution Order

- Setup → Foundational (T002–T007) → US1 (T008–T014) → US2, US3, US4, US5
- US2–US5 all extend `pricing.py`, so run them in sequence (US2 → US3 → US4 → US5) to avoid edit conflicts; `availability.py` work (T018–T019, T022–T023) can start in parallel with US2
- Within each story: test task → see it fail → implementation → green

## Parallel Opportunities

- T002 with T004/T005 (different files); T012 with T008–T011
- T018/T019 (availability.py) alongside T015/T016 (pricing.py)
- T026 and T027

## Implementation Strategy

1. MVP = Phases 1–3: package quotes over the public API.
2. Add US2 (custom orders), then US3/US4 (availability and rush), then US5.
3. Feature 002 (booking wizard) consumes `/public/*` and `build_quote()` for server-side re-pricing on submit.
