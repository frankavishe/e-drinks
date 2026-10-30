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

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local                 # Supabase URL + anon key
npm run dev                                # http://localhost:5173, /api proxied to :8000
npm test
```
