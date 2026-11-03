# Contract: Public API (no auth)

Mounted at the API root; the browser calls it as `/api/...` (proxy strips `/api`).
All money fields are integer TZS. No response contains `cost_price` or `unit_cost`.

## GET /public/catalog
`200` → `[{id, name_sw, name_en, category, unit, units_per_pack, is_alcohol, image_url,
returnable_glass, empties_deposit_per_unit, tiers: [{min_qty, unit_price}]}]` (active only)

## GET /public/packages
`200` → `[{id, slug, name_sw, name_en, description_sw, description_en, base_hours,
rules: [{product_id, qty_per_guest, per_hour}]}]` (active only, by sort_order)

## GET /public/addons
`200` → `[{id, name_sw, name_en, kind, price}]` (active only; capacity not exposed)

## GET /public/areas
`200` → `{zones: [{id, name, delivery_fee, areas: [{id, name}]}],
venues: [{id, name, area_id, address}]}`

## POST /public/quote
Request:
```json
{
  "event_date": "2026-12-12", "hours": 5, "guests": 300,
  "setup_at": "2026-12-12T15:00:00+03:00", "collect_at": "2026-12-13T09:00:00+03:00",
  "package_id": 2, "overrides": {"6": 14},
  "items": null,
  "addons": [{"addon_id": 1, "qty": 6}, {"addon_id": 3, "qty": 4}],
  "area_id": 1, "custom_area": null
}
```
Response `200`:
```json
{
  "lines": [{"product_id": 1, "name_sw": "...", "name_en": "...", "unit": "...", "packs": 10,
             "unit_price": 16000, "line_total": 160000, "empties_deposit": 60000, "source": "package"}],
  "addon_lines": [{"addon_id": 1, "name_sw": "...", "name_en": "...", "qty": 6, "unit_price": 15000,
                   "line_total": 90000, "available": 20, "ok": true}],
  "subtotal": 0, "addons_total": 0, "delivery_fee": 25000, "delivery_custom": false,
  "empties_deposit": 0, "total": 0, "deposit_due": 0, "balance_due_date": "2026-12-09",
  "flags": {"is_rush": false, "below_minimum": false, "min_order": 300000,
            "provisional": false, "addons_unavailable": []}
}
```
Errors: `422` invalid input, past date, unknown/inactive product/package/add-on/area, catalog error
(no tier for quantity) with `detail` naming the item.
