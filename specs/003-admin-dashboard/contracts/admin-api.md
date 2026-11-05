# Contract: Admin API

Mounted at `/admin`. All money is integer TZS. Dates are ISO. Every endpoint needs a Supabase bearer token:
`401` without a valid one; `403` for planners, or for staff on owner-only endpoints.

Refusals by a business rule are `409` with `detail: {"code": "<code>"}`. Codes are listed in
[data-model.md](../data-model.md). Invalid input is `422`, unknown records `404`.

## Session

`GET /admin/me` → `{"id": "...", "role": "staff", "name": "Amina"}`

## Bookings

`GET /admin/overview` → `{"today": [<BookingRow>], "upcoming": [<BookingRow>]}`: live bookings dated today, and the next 14 days. Cancelled and closed left out.

`GET /admin/bookings?q=&status=&date_from=&date_to=&rush=&limit=50&offset=0` → `{"total": 3, "items": [<BookingRow>]}`. `q` matches number, customer name or phone (any format).

BookingRow:
```json
{
  "id": 1, "code": "ED-2026-0001", "status": "request", "is_rush": true, "rush_approved": false,
  "provisional": false, "event_type": "wedding", "event_date": "2026-11-20", "start_time": "16:00:00",
  "guests": 300, "customer_name": "Asha", "customer_phone": "255712345678", "venue_name": "...",
  "total": 1806500, "amount_paid": 0, "amount_pending": 903250
}
```

`GET /admin/bookings/{id}` → BookingRow fields, plus:
```json
{
  "customer_email": "", "hours": 5, "venue_address": "", "custom_area": "", "lang": "sw",
  "setup_at": "...", "collect_at": "...", "notes": "", "internal_notes": "", "efd_receipt_no": "",
  "date_changes_used": 0, "balance_due_date": "2026-11-17", "balance_due": 1806500,
  "subtotal": 0, "addons_total": 0, "delivery_fee": 0, "empties_deposit": 0, "deposit_due": 903250,
  "refund_due": null, "refunded": 0,
  "items": [{"name_sw": "", "name_en": "", "unit": "", "qty": 1, "unit_price": 0, "line_total": 0}],
  "addons": [{"name_sw": "", "name_en": "", "qty": 1, "unit_price": 0, "line_total": 0}],
  "payments": [{"id": 1, "kind": "deposit", "method": "mpesa", "amount": 0, "reference": "", "status": "pending",
                "confirmed_by_name": null, "confirmed_at": null, "created_at": "..."}],
  "history": [{"from_status": null, "to_status": "request", "changed_by_name": null, "note": "", "created_at": "..."}],
  "allowed_moves": [{"to": "confirmed", "allowed": false, "reason": "deposit_not_paid", "back": false}]
}
```
Owner only, on the same response:
```json
{"financials": {"goods_total": 0, "revenue": 0, "profit": 0}}
```
`goods_total` is the snapshotted buying total; `revenue` leaves out the refundable empties deposit. These names
are for the owner's response only; the staff response has no such keys.

`PATCH /admin/bookings/{id}` body `{"efd_receipt_no"?: "", "internal_notes"?: ""}` → detail.

`POST /admin/bookings/{id}/stage` body `{"to": "confirmed", "note": ""}` → detail.

`GET /admin/bookings/{id}/cancel-preview` → `{"days_ahead": 10, "refund_due": 451625, "paid": 903250}`

`POST /admin/bookings/{id}/cancel` body `{"note": ""}` → detail.

`POST /admin/bookings/{id}/date-change` body `{"new_date": "2026-12-01", "exception": false, "note": ""}` → detail.

`POST /admin/bookings/{id}/rush` body `{"approve": true, "note": ""}` → detail.

`POST /admin/bookings/{id}/delivery-fee` body `{"fee": 50000}` → detail.

`POST /admin/bookings/{id}/refunds` body `{"amount": 451625, "method": "mpesa", "reference": ""}` → detail, `201`.

`POST /admin/payments/{id}/confirm` → detail. `POST /admin/payments/{id}/reject` → detail.

## Calendar

`GET /admin/calendar?from=2026-11-01&to=2026-11-30` (at most 62 days) →
```json
{
  "days": [{
    "date": "2026-11-21",
    "bookings": [{"id": 1, "code": "ED-2026-0001", "status": "confirmed", "is_rush": false, "customer_name": "Asha", "start_time": "16:00:00"}],
    "addons": [{"addon_id": 1, "name_sw": "", "name_en": "", "committed": 3, "owned": 5}]
  }]
}
```
Every day in the range appears. `addons` lists only add-ons in use that day. `owned` is null for unlimited.

## Catalog (read: staff and owner; write: owner)

`GET /admin/products` → staff: all public product fields plus `active` and `tiers`. Owner: also `cost_price`.

`POST /admin/products`, `PATCH /admin/products/{id}`, `DELETE /admin/products/{id}` (`204`).

`PUT /admin/products/{id}/tiers` body `[{"min_qty": 1, "unit_price": 30000}]`.

`GET /admin/packages` (with rules), `POST`, `PATCH /{id}`, `DELETE /{id}`, `PUT /admin/packages/{id}/rules` body `[{"product_id": 1, "qty_per_guest": "0.500", "per_hour": true}]`.

`GET /admin/addons` → staff: no `replacement_cost`; owner: with it. `POST`, `PATCH /{id}`, `DELETE /{id}`.

`GET /admin/zones` → zones with their areas. `POST`, `PATCH /{id}`, `DELETE /{id}`.

`POST /admin/areas`, `PATCH /admin/areas/{id}`, `DELETE /admin/areas/{id}`.

`GET /admin/venues`, `POST`, `PATCH /{id}`, `DELETE /{id}`.

## Settings

`GET /admin/settings` (staff and owner) → `{"business_name": "e-drinks", "min_order": "300000", ...}`

`PUT /admin/settings` (owner) body: changed keys only → the full map.

## Public API change

`GET /public/packages` leaves out rules whose product is inactive.
