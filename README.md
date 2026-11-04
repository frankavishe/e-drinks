# e-drinks

Event drinks booking platform for Dar es Salaam. The spec is `Frank plan.md`.

- `backend/` — FastAPI + SQLAlchemy (async) + Alembic. All pricing, availability, booking and money logic.
- `frontend/` — Vite + React + TypeScript + Tailwind, Swahili by default with English available.
- Supabase — Postgres (schema owned by Alembic, RLS on with no policies), Auth (email/password).

## Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"     # macOS/Linux: .venv/bin/pip
cp .env.example .env                       # fill in the Supabase values
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.seed --owner-email you@example.com
.venv/Scripts/uvicorn app.main:app --reload
.venv/Scripts/pytest
```

## Public API

These endpoints need no login. The backend serves them at the root, and the browser calls them under
`/api` (the proxy strips the prefix). All money is in whole TZS, and responses never include cost data.

| Method and path | Returns |
|---|---|
| `GET /public/catalog` | Active products with their price tiers |
| `GET /public/packages` | Active packages with their per-guest rules |
| `GET /public/addons` | Active add-ons and prices |
| `GET /public/areas` | Delivery zones with fees and areas, plus venues |
| `POST /public/quote` | A full price for a package or custom order; nothing is saved |

Example: a Silver package for 300 guests over 5 hours in Masaki, with 6 coolers. The IDs are from a fresh
seed, so look yours up with the `GET` endpoints.

```bash
curl -X POST http://localhost:8000/public/quote -H "Content-Type: application/json" -d '{
  "event_date":"2026-12-12","hours":5,"guests":300,
  "setup_at":"2026-12-12T15:00:00+03:00","collect_at":"2026-12-13T09:00:00+03:00",
  "package_id":2,"addons":[{"addon_id":1,"qty":6}],"area_id":1}'
```

The response includes `"total":1806500`, `"deposit_due":903250` and `"balance_due_date":"2026-12-09"`.
The event date must not be in the past, or the request returns `422`. The full request and response
format is in `specs/001-pricing-availability/contracts/public-api.md`.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local                 # Supabase URL + anon key
npm run dev                                # http://localhost:5173, /api proxied to :8000
npm test
```
