# Quickstart: verify feature 001

```bash
cd backend
.venv/Scripts/pytest tests/test_pricing.py tests/test_availability.py tests/test_public_api.py -v
.venv/Scripts/pytest            # whole suite stays green
```

Manual check against a seeded dev database:

```bash
.venv/Scripts/uvicorn app.main:app --reload
curl http://localhost:8000/public/packages
curl -X POST http://localhost:8000/public/quote -H "Content-Type: application/json" -d '{
  "event_date":"<a date 10+ days ahead>","hours":5,"guests":300,
  "setup_at":"<date>T15:00:00+03:00","collect_at":"<date+1>T09:00:00+03:00",
  "package_id":<silver id>,"addons":[{"addon_id":<cooler id>,"qty":6}],"area_id":<Masaki id>}'
```

Expected for Silver, 300 guests, 5 h, Masaki (seed data): Coca-Cola 0.75×300=225 bottles → 10 crates
@16,000; Kilimanjaro 300 bottles → 12 crates @48,500; delivery 25,000; empties deposit on all glass
crates; deposit = ceil(total/2); balance due 3 days before. Also check:
- event 2 days ahead → `is_rush: true`; with a server add-on and 5 days ahead → rush
- 21 coolers → `ok: false`, `available: 20`
- `custom_area: "Bagamoyo"` → `delivery_custom: true`, `provisional: true`
- response JSON contains no `cost`
