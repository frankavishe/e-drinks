# Research: Pricing, Availability & Public Quote

## R1. Package quantity formula
- **Decision**: `packs = ceil(guests × qty_per_guest × factor / units_per_pack)`, where
  `factor = hours / package.base_hours` if `rule.per_hour` else `1`. Computed with `Fraction`
  (from the `Decimal` column) so `ceil` is exact.
- **Rationale**: `qty_per_guest` is bottles per guest over the base hours (see `PackageRule` comment
  in `app/models/catalog.py`); prices, costs and empties deposits are per pack (seed data).
- **Alternatives**: floats (rejected: e.g. 300×0.1 = 30.000000000000004 would round up to an extra pack).

## R2. Tier selection
- **Decision**: the tier with the largest `min_qty ≤ qty`; whole line at that price. No tier
  matching → `CatalogError` → HTTP 422 with product id.
- **Rationale**: matches the business rule "quantity tiers (1–9 / 10–49 / 50+)".

## R3. Deposit and balance date
- **Decision**: `deposit_due = ceil(total × deposit_percent / 100)` with integer math
  (`-(-total * pct // 100)`); `balance_due_date = event_date − balance_due_days`. Both values are
  read from settings (seeded 50 and 3).
- **Rationale**: Constitution VI. The spec text says "50%" / "3 days"; these are the defaults.
- **Provisional delivery**: when the area is custom, total excludes delivery and the deposit is
  computed on that provisional total.

## R4. Add-on availability
- **Decision**: holding bookings = status in {confirmed, fully_paid, delivered} (equipment still out
  until Returns settled). Requested window `[setup_at, collect_at)` (half-open, so touching windows
  don't conflict). Peak use = max over the start points of the overlapping intervals of the sum of the
  quantities active at that point (sweep line). Free = capacity − peak. `owned_capacity = None` →
  unlimited (ice).
- **Rationale**: Summing every overlapping booking overstates use when two bookings in the window
  don't overlap each other (e.g. Friday night + Saturday morning in a two-day window).
- **Alternatives**: plain sum (rejected, as above); per-day buckets (rejected: next-morning collection
  crosses days).
- `exclude_booking_id` parameter so later features (date change, edits) can re-check a booking
  without counting itself.

## R5. Rush and "today"
- **Decision**: `days_ahead = (event_date − today_EAT).days`; rush if
  `days_ahead < notice_days_servers` when any server/bartender add-on is in the quote, else
  `< notice_days`. Event date before today → 422. `today` is injectable for tests.
- **Rationale**: the owner's day is East Africa Time; servers include bartenders (both are staff shifts).

## R6. Minimum order
- **Decision**: compare `min_order` with `subtotal + addons_total` (drinks + add-ons, excluding delivery
  and refundable empties deposit); flag `below_minimum` and return `min_order`.
- **Rationale**: deposits are refundable and delivery is a pass-through cost, so they shouldn't count
  toward a minimum spend.

## R7. API shape
- **Decision**: one `POST /public/quote` taking event details + either `package_id` (with optional
  `overrides: {product_id: packs}`) or `items: [{product_id, packs}]`, plus `addons`, and either
  `area_id` or `custom_area`. Read endpoints `GET /public/catalog`, `/public/packages`,
  `/public/addons`, `/public/areas` (zones with areas and saved venues).
- Unavailable add-ons and below-minimum are returned as **flags in a 200 response**, not errors, so
  the wizard can show them; malformed input → 422.
