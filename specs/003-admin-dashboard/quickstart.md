# Quickstart: verify feature 003

```bash
cd backend && .venv/Scripts/pytest
cd frontend && npm test && npm run build && npm run lint
```

## Against a throwaway database

Override `DATABASE_URL` with a temporary SQLite file and leave `RESEND_API_KEY` empty, so nothing touches
Supabase and no real email is sent. Build the schema with `Base.metadata.create_all`, as the tests do, and review
the offline Postgres SQL (`alembic upgrade head --sql`).

Login needs Supabase Auth. Without a dev project, sign tokens with `SUPABASE_JWT_SECRET` and put an owner and a
staff row in `profiles`; record in the results below which was used.

Start `uvicorn app.main:app` and `npm run dev`. Create bookings through `/book` first.

| # | Scenario | Expected |
|---|---|---|
| 1 | Log in as staff; open `/admin` | Today and Upcoming list events with stage and rush flags |
| 2 | Find a booking by number, then by `07xx` phone | Found both ways; detail shows payments and history |
| 3 | As staff, look over the detail, products and add-ons | No cost, margin or profit; settings read-only; no catalog edit controls |
| 4 | As owner, open the same booking | Cost and profit visible |
| 5 | Try to move to Confirmed with no deposit | Refused, reason shown |
| 6 | Submit a deposit reference on `/track`; confirm it; move to Confirmed | Confirmer and time shown; paid total updated; move allowed; history has the actor |
| 7 | Reject that payment | Refused while Confirmed. As owner, move back with a note; rejecting now works |
| 8 | Cancel a booking 10 days out with a deposit paid | Preview and result show 50% of the deposit; a refund record can be added and can't exceed it |
| 9 | Change the date of a booking 7+ days out; change it again | First works and shifts setup and collection; second refused; as owner, works as an exception with a note |
| 10 | Approve one rush request; decline another | Approved one can move on; declined one is Cancelled with everything paid due back |
| 11 | Set the delivery fee on an unlisted-area booking | Total and deposit update; no longer provisional |
| 12 | Two confirmed bookings on one Saturday with coolers | Calendar shows both and combined usage against owned, in month and week views |
| 13 | As owner, change a tier price | A new quote uses it; the existing booking keeps its total |
| 14 | Enter a repeated tier quantity; delete a product used in a booking | Both refused with a reason |
| 15 | Deactivate a product | Gone from `/public/catalog` and from package rules |
| 16 | Switch to English and back on each admin screen | All text translated, including refusal reasons |
