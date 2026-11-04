# Contract: Public API additions (no auth)

Extends `specs/001-pricing-availability/contracts/public-api.md`. Same mounting and integer TZS. No response
contains `cost_price` or `unit_cost`.

## GET /public/settings
`200` →
```json
{
  "business_name": "e-drinks", "whatsapp_number": "255700000000",
  "policy_text_sw": "...", "policy_text_en": "...",
  "payment_instructions": {"mpesa_till": "", "tigopesa_lipa": "", "airtel_lipa": "", "bank_details": ""}
}
```

## POST /public/bookings
Request: every `/public/quote` field, plus:
```json
{
  "event_type": "wedding", "start_time": "16:00:00",
  "venue_id": 1, "venue_name": "", "venue_address": "",
  "name": "Asha", "phone": "0712345678", "email": "", "notes": "",
  "lang": "sw", "expected_total": 1806500,
  "accept_policy": true, "age_confirmed": true
}
```
`201` →
```json
{
  "code": "ED-2026-0001", "status": "request", "is_rush": false, "provisional": false,
  "total": 1806500, "deposit_due": 903250, "balance_due_date": "2026-11-15",
  "payment_instructions": {"mpesa_till": "", "tigopesa_lipa": "", "airtel_lipa": "", "bank_details": ""},
  "whatsapp_number": "255700000000"
}
```

Errors:
- `409` with `detail: {"code": "addons_unavailable" | "below_minimum" | "quote_changed", "quote": <QuoteOut>}`; nothing saved
- `422` invalid input, invalid phone, policy or 18+ not accepted, or venue not in the area
- `429` too many bookings from this address

## POST /public/track
Request: `{"code": "ED-2026-0001", "phone": "+255712345678"}`

`200` →
```json
{
  "code": "ED-2026-0001", "status": "request", "is_rush": false, "provisional": false,
  "event_type": "wedding", "event_date": "2026-11-18", "start_time": "16:00:00",
  "hours": 5, "guests": 300, "venue_name": "...", "venue_address": "...",
  "items": [{"name_sw": "...", "name_en": "...", "unit": "...", "qty": 10, "unit_price": 16000, "line_total": 160000}],
  "addons": [{"name_sw": "...", "name_en": "...", "qty": 6, "unit_price": 15000, "line_total": 90000}],
  "subtotal": 0, "addons_total": 0, "delivery_fee": 25000, "empties_deposit": 0, "total": 0,
  "deposit_due": 0, "balance_due_date": "2026-11-15",
  "amount_paid": 0, "amount_pending": 0, "balance_due": 0,
  "payments": [{"kind": "deposit", "amount": 903250, "method": "mpesa", "reference": "ABC123",
                "status": "pending", "created_at": "2026-11-04T10:00:00Z"}],
  "payment_instructions": {"mpesa_till": "", "tigopesa_lipa": "", "airtel_lipa": "", "bank_details": ""}
}
```

Errors:
- `404` `{"detail": "Booking not found"}`, identical for an unknown number, wrong phone or invalid phone
- `429` too many failed lookups from this address

## POST /public/bookings/{code}/payments
Request:
`{"phone": "0712345678", "kind": "deposit", "method": "mpesa", "amount": 903250, "reference": "abc123"}`

`201` → the new payment, with `status: "pending"` and the reference upper-cased.

Errors:
- `404` as for tracking
- `409` with `detail: {"code": "duplicate_reference"}` or `{"code": "booking_closed"}`
- `422` invalid input
- `429` too many failed lookups from this address

## Emails

| Trigger | To | Contains |
|---|---|---|
| New booking | Business | Number, customer name and phone, event date, total, rush and provisional notes |
| New booking, email given | Customer | Number, event date, total, deposit, balance date, payment instructions |
| Payment reference | Business | Number, kind, amount, method, reference |
