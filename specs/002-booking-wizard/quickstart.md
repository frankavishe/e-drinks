# Quickstart: verify feature 002

```bash
cd backend && .venv/Scripts/pytest
cd frontend && npm test && npm run build && npm run lint
```

## Against a throwaway database

Override `DATABASE_URL` with a temporary SQLite file and leave `RESEND_API_KEY` empty, so nothing touches
Supabase and no real email is sent. Emails appear in the API log.

1. Migrate and seed the temporary database, and review the offline Postgres SQL (`alembic upgrade head --sql`).
2. Start `uvicorn app.main:app` and `npm run dev`. Open the app at phone width.

| # | Scenario | Expected |
|---|---|---|
| 1 | 300-guest Silver wedding at the Masaki venue in Swahili; switch to English midway | Entered data kept; number issued; totals equal the review step |
| 2 | Submit without the policy or 18+ box | Blocked |
| 3 | Event inside the notice period | Saved as rush; confirmation says availability will be confirmed |
| 4 | Unlisted area | Saved; delivery shown as to be confirmed |
| 5 | Continue on WhatsApp | Link has the configured number and the booking number |
| 6 | Track with 07xx, 2557xx and +2557xx | Same booking each time |
| 7 | Track with a wrong phone | Same not-found message as an unknown number |
| 8 | Submit a deposit reference | Shown as pending; same reference again is rejected |
| 9 | API log | Business emails for the booking and the payment; customer email if one was given |

## Verified

Not yet run.
