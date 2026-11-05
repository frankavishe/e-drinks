# e-drinks — Event Drinks Booking Platform (Dar es Salaam)

## Context
The owner sells drinks in bulk (soft drinks + alcohol, licensed) to weddings and events in Dar es Salaam, delivering to the venue with ice coolers and drink servers. Customers are wedding planners, event planners and the general public. Goal: a real, money-making business. The project folder `C:\Users\User\Desktop\e-drinks` is empty, so this is a greenfield build. Stack: React frontend, FastAPI backend, Supabase (Postgres + Auth + Storage). All design decisions below were settled in the grilling session (Q1–Q32).

## Settled business rules
- **Stock**: the owner holds stock *and* buys from wholesalers. A confirmed booking reserves the stock on hand; any shortfall goes onto a purchase list with a needed-by date. Purchases record unit cost, which gives true profit per booking.
- **Pricing**: TZS, VAT-inclusive, with per-product quantity tiers (e.g. 1–9 / 10–49 / 50+ crates). Cost price is stored and shown only to the Owner. Planner clients pay normal prices, and commission comes out of margin.
- **Ordering**: packages (Bronze/Silver/Gold/Premium bar) with per-guest rules adjusted for event length, rounded up to whole crates and editable by the customer, **or** a custom crate builder.
- **Add-ons**: coolers, ice bags, servers (per shift), bartender. These are limited resources, checked per date so they can't be double-booked. The block runs from setup time to collection time.
- **Delivery**: to the venue. The venue's area maps to a zone, and the zone sets a fixed fee. Areas not on the list get a manual "custom quote" fee. Saved venues auto-fill. Each booking stores setup time and collection time (same night or next morning).
- **Sale-or-return**: sealed, unopened drinks are refunded or credited within 48h. **Empties**: a refundable deposit on glass bottles and crates, with empties tracked out and back. Lost or damaged equipment is billed at replacement cost, taken from the empties deposit first.
- **Payments**: 50% deposit locks the date; the balance is due 3 days before the event. Methods: M-Pesa, Tigo Pesa, Airtel Money (Lipa Namba/till) and bank transfer. The customer submits a transaction reference and admin confirms it by hand. Every payment is a separate record (deposit/balance/refund). Online payments via AzamPay come in phase 2.
- **Booking stages**: Request → Quoted → Confirmed (deposit paid) → Fully paid → Delivered → Returns settled → Closed; Cancelled from any stage. Cancellation: 14+ days before = deposit back minus 10%; 7–13 days = 50% back; under 7 days = nothing back. One free date change if made 7+ days ahead. The customer must accept the policy and confirm they are 18+.
- **Limits**: minimum order (e.g. TZS 300,000) and notice period (3 days, or 7 if servers are booked), both editable in settings. Inside the notice period a booking becomes a "rush request" that admin approves by hand.
- **Planners**: sign up with email and password and wait for admin approval. Each planner has a commission rate (5–10%). They can book for named clients. Commission is *earned* only when a booking reaches Closed, and is then paid monthly.
- **Roles**: Customer (no account; tracks a booking with booking number + phone), Planner, Staff (no cost or profit figures), Owner (everything).
- **Language**: Swahili by default, with English available.
- **WhatsApp**: after submitting, a "Continue on WhatsApp" button opens a prefilled message containing the booking number. Automatic WhatsApp messages come in phase 2.
- **Tax receipts (TRA)**: the app produces quote and invoice PDFs (Swahili/English, with TIN). The EFD/VFD receipt number is typed into the booking.
- **Notifications**: emails via Resend (new booking, payment reference submitted, planner booking confirmed). Customers see status on their tracking page.
- **Business name**: "e-drinks", stored as a single setting so a rename is one change.

## Architecture
- `frontend/`: Vite + React + TypeScript + Tailwind, react-router, react-i18next (sw/en), TanStack Query. Uses Supabase JS **only for login** (planners and admin); all data goes through the FastAPI API.
- `backend/`: FastAPI + SQLAlchemy 2 (async, asyncpg) + Alembic + Pydantic v2 + pytest. Checks Supabase login tokens (JWT) and holds all pricing, availability, commission and refund logic. PDFs via WeasyPrint or ReportLab; emails via Resend.
- **Supabase**: Postgres (schema owned by Alembic), Auth (email/password), Storage (product and gallery images). Row Level Security is on for every table with no public policies, so the browser can't read tables directly.
- **Hosting**: Vercel (frontend), Render or Railway (API), Supabase cloud (EU), a `.co.tz` domain. Git repo and `.env.example`.

## Data model (Alembic migrations)
- `settings` (key/value: business name, TIN, min order, notice days, payment numbers, bank details, policy text, WhatsApp number)
- `profiles` (auth user id, role owner/staff/planner, name, phone, planner_status, commission_rate)
- `customers` (name, phone, email)
- `products` (name_sw/en, category, unit e.g. "crate of 24", is_alcohol, cost_price, image, returnable_glass, empties_deposit_per_unit, active)
- `price_tiers` (product_id, min_qty, unit_price)
- `packages`, `package_rules` (package_id, product_id, qty_per_guest, per_hour flag)
- `addons` (name, kind cooler/ice/server/bartender, price, owned_capacity, replacement_cost)
- `zones` (name, delivery_fee), `areas` (name, zone_id), `venues` (name, area_id, address, lat/lng)
- `bookings` (code ED-YYYY-NNNN, customer_id, planner_id, event_type, event_date, start_time, hours, guests, venue/area, setup_at, collect_at, status, is_rush, totals snapshot: subtotal, delivery_fee, empties_deposit, total, deposit_due, balance_due_date, efd_receipt_no, policy_accepted_at, age_confirmed, notes)
- `booking_items` (product_id, qty, unit_price & unit_cost snapshots, qty_delivered, qty_returned, empties_out, empties_back)
- `booking_addons` (addon_id, qty, unit_price, qty_lost_damaged)
- `booking_status_history`
- `payments` (booking_id, kind deposit/balance/refund/damage, amount, method, reference, status pending/confirmed/rejected, confirmed_by, confirmed_at)
- `stock_levels` (product_id, on_hand), `stock_movements` (product_id, qty, type purchase/reserve/release/deliver/return/adjust, booking_id, unit_cost, supplier)
- `commissions` (booking_id, planner_id, amount, status pending/earned/paid, paid_at)
- `gallery_images`

## Backend modules (`backend/app/`)
- `services/pricing.py`: tier lookup, package-to-quantities (guests × hours, rounded up to crates), add-ons, zone fee, empties deposit, deposit/balance amounts. **This is the core, so it has the most tests.**
- `services/availability.py`: add-on capacity across the setup→collect window, notice period / rush check
- `services/stock.py`: reserve and release, purchase list, receiving stock
- `services/booking_flow.py`: stage changes with rules (e.g. Confirmed needs a confirmed deposit), cancellation refund calculation, date change
- `services/settlement.py`: returns and empties settlement, damage charges, final bill, commission earned on Close
- `services/pdf.py`, `services/notify.py`
- `routers/`: `public` (catalog, packages, zones/areas/venues, quote, create booking, track, submit payment ref), `planner`, `admin` (all dashboard endpoints, role-gated)
- `auth.py`: Supabase JWT check, plus `require_role(...)`

## Frontend (`frontend/src/`)
- **Public**: Home, Packages, Gallery, FAQ, For Planners, Contact (SEO meta in sw/en); Booking wizard (event → package/custom → add-ons → review quote → contact → confirmation with payment instructions + WhatsApp button); Track booking.
- **Planner**: sign up / log in, dashboard (bookings, new booking for a client, PDFs, commission statement).
- **Admin**: Today/Upcoming, Bookings list + detail (payments, returns/empties, EFD number, PDFs, stage changes), Calendar (bookings + equipment/servers per day), Stock (levels, reserved, purchase list, receive), Catalog (products, tiers, packages, add-ons), Zones & Venues, Planners (approve, rates, commissions owed/paid), Reports (Owner only: revenue, profit per booking, best sellers, outstanding balances), Settings.

## Build order
1. Repo skeleton, Supabase project, Alembic base migration, auth/roles, seed data (sample products, zones/areas for Dar, packages, add-ons).
2. Pricing + availability services with pytest; public quote endpoint.
3. Booking wizard + track page + payment-reference submission + WhatsApp handoff + Resend emails.
4. Admin: bookings, payment confirmation, stage changes, calendar, catalog, zones/venues, settings.
5. Stock reservation and purchase list; returns/empties settlement; PDFs.
6. Planner accounts, approvals, commissions.
7. Marketing pages, i18n polish, SEO, reports, deploy (Vercel/Render/Supabase, domain).

**Phase 2 (after real bookings)**: AzamPay/Selcom payments, automated SMS/WhatsApp, VFD integration, phone one-time-code login, delivery tracking, more cities.

## Verification
- `pytest` in `backend/`: pricing tiers, package rounding, zone fees, empties deposit, 50% deposit, cancellation refund at 15/10/3 days, commission only on Close, add-on overbooking blocked across overlapping setup→collect windows, stock reserve/shortfall.
- Run the API (`uvicorn`) + frontend (`npm run dev`) against a Supabase dev project. End-to-end check:
  1. Book a 300-guest Silver wedding at a Masaki venue → correct quote → submit → WhatsApp link holds the booking number.
  2. Submit a deposit reference → admin confirms it → admin moves the booking to Confirmed → stock is reserved, the purchase list shows any shortfall.
  3. Try to book more coolers than owned on an overlapping date → blocked.
  4. Mark Delivered → enter returns and empties → Returns settled → Closed → planner commission is earned.
  5. Download the invoice PDF in Swahili and English; tracking page works with booking number + phone.
- Check that Staff can't see cost or profit, an unapproved planner can't book with commission, and Row Level Security blocks direct table reads from the browser.
