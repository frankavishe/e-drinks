# Data Model: Pricing, Availability & Public Quote

No new tables or migrations. This feature reads existing tables and adds in-memory types.

## Tables read (existing, `backend/app/models/`)

| Table | Fields used |
|---|---|
| `products` | id, name_sw/en, unit, units_per_pack, returnable_glass, empties_deposit_per_unit (per pack), active (cost_price is **never** read into public types) |
| `price_tiers` | product_id, min_qty, unit_price |
| `packages` / `package_rules` | base_hours, active; product_id, qty_per_guest (bottles/guest), per_hour |
| `addons` | kind, price, owned_capacity (None = unlimited), active |
| `zones` / `areas` / `venues` | delivery_fee; area → zone; venue → area |
| `settings` | min_order, notice_days, notice_days_servers, deposit_percent, balance_due_days |
| `bookings` / `booking_addons` | status, setup_at, collect_at; addon_id, qty (for availability only) |

## In-memory types (`app/services/pricing.py`)

- **ProductInfo**: id, name_sw, name_en, unit, units_per_pack, tiers `[(min_qty, unit_price)]`,
  returnable, empties_deposit_per_pack
- **PackageInfo**: id, base_hours, rules `[(product_id, qty_per_guest: Fraction, per_hour)]`
- **AddonInfo**: id, name_sw, name_en, kind, price, capacity | None
- **PricingSettings**: min_order, notice_days, notice_days_servers, deposit_percent, balance_due_days
- **QuoteRequest**: event_date, hours, guests, setup_at, collect_at, package_id | None,
  overrides `{product_id: packs}`, items `[(product_id, packs)]`, addons `[(addon_id, qty)]`,
  area_id | None, custom_area
- **QuoteLine**: product_id, names, unit, packs, unit_price, line_total, empties_deposit, source (package | custom)
- **AddonLine**: addon_id, names, qty, unit_price, line_total, available (int | None), ok (bool)
- **Quote**: lines, addon_lines, subtotal, addons_total, delivery_fee, delivery_custom (bool),
  empties_deposit, total, deposit_due, balance_due_date, flags {is_rush, below_minimum, min_order,
  provisional, addons_unavailable}

## Rules (validation)

- guests ≥ 1, hours 1–24, packs ≥ 1 (an override of 0 removes the line), addon qty ≥ 1
- `collect_at > setup_at`; event_date ≥ today (EAT)
- exactly one of `package_id` / `items`; exactly one of `area_id` / `custom_area`
- inactive or unknown products/add-ons/packages → 422
