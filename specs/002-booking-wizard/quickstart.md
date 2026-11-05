# Quickstart: verify feature 002

```bash
cd backend && .venv/Scripts/pytest
cd frontend && npm test && npm run build && npm run lint
```

## Against a throwaway database

Override `DATABASE_URL` with a temporary SQLite file and leave `RESEND_API_KEY` empty, so nothing touches
Supabase and no real email is sent. Emails appear in the API log.

1. Seed the temporary database, and review the offline Postgres SQL (`alembic upgrade head --sql`). The base
   migration's `now()` defaults are Postgres-only: `alembic upgrade` runs on SQLite, but inserting a booking
   then fails. For this walkthrough, build the SQLite schema with `Base.metadata.create_all`, as the tests do.
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

Run on 2026-11-05 in Chrome, with the app in a 390x844 iframe (the browser window would not resize below
1280), against a throwaway SQLite database with `RESEND_API_KEY` empty. All 9 scenarios passed, with no
horizontal overflow at that width.

| # | Result |
|---|---|
| 1 | ED-2026-0001 issued for the Masaki venue in Swahili. Data kept through a switch to English and back. Total TSh 1,716,500 and deposit TSh 858,250 equal the review step |
| 2 | Submit stayed disabled with neither box, or only one, ticked |
| 3 | Event on 2026-11-06: ED-2026-0002 saved as rush, with the availability message |
| 4 | Area "Bagamoyo": ED-2026-0003 saved; delivery shown as to be confirmed, with the note |
| 5 | Link has `wa.me/255700000000` and the booking number |
| 6 | `0712345678`, `255712345678` and `+255712345678` found the same booking |
| 7 | Wrong phone, unknown number and invalid phone showed the same message |
| 8 | Deposit reference shown as pending; the same reference again was refused and not added |
| 9 | Log held 3 business booking emails, 1 customer email (only the booking with an address) and 1 business payment email, with no customer-typed note in any of them |

Automated: 272 backend and 23 frontend tests passed; build passed; lint had 3 fast-refresh warnings and no
errors. Migrations ran up, down and up again on SQLite. The offline Postgres SQL was reviewed; it was rendered
with a stand-in for the `asyncpg` import, because Windows Application Control blocks its DLL on this machine.

Not exercised:

- Real delivery through Resend, so SC-003 (email within 1 minute) is unmeasured
- The API or migrations against a live Postgres or Supabase database
- A real phone: touch input and the WhatsApp link actually opening the app
- The customer email's rush and provisional notes in a browser run (unit tests cover them)

Found and fixed: a blank `VITE_API_URL`, as in `.env.example`, skipped the dev proxy, so the wizard received
HTML instead of data.

Open questions:

- For a rush event, the balance date can already be past (event 2026-11-06 shows 2026-11-03). This follows the
  "event minus 3 days" rule, which has no rush exception.
- Product units such as "kreti ya chupa 24" stay in Swahili on the English pages.
