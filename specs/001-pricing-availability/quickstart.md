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

## Verified

2026-11-04, real `uvicorn` server over HTTP, on a throwaway SQLite database built with
`Base.metadata.create_all` and `app.seed.seed`. Postgres and the Alembic migrations were not exercised.
All the checks above passed.

Silver, 300 guests, 5 h, Masaki, 6 coolers, event 2026-11-18:

| Line | Packs | Unit price | Line total | Empties deposit |
|---|---:|---:|---:|---:|
| Coca-Cola 350ml | 10 | 16,000 | 160,000 | 60,000 |
| Fanta Orange 350ml | 7 | 16,500 | 115,500 | 42,000 |
| Sprite 350ml | 4 | 16,500 | 66,000 | 24,000 |
| Water 500ml | 25 | 6,000 | 150,000 | 0 |
| Kilimanjaro Lager 500ml | 12 | 48,500 | 582,000 | 120,000 |
| Safari Lager 500ml | 6 | 52,000 | 312,000 | 60,000 |

| Figure | TZS |
|---|---:|
| Subtotal | 1,385,500 |
| Add-ons (6 coolers @ 15,000) | 90,000 |
| Delivery | 25,000 |
| Empties deposit | 306,000 |
| **Total** | **1,806,500** |
| Deposit due | 903,250 |

Balance due 2026-11-15.
