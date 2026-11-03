# Feature Specification: Marketing Site, Reports & Launch

**Feature Branch**: `006-marketing-deploy` (specs tracked on `build`)

**Created**: 2026-11-03

**Status**: Draft

**Input**: Build-order phase 7 of `Frank plan.md`: "Marketing pages, i18n polish, SEO, reports, deploy (Vercel/Render/Supabase, domain)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visitors understand the offer and start booking (Priority: P1)

A visitor finds the site from Google or a WhatsApp link and sees Home, Packages, Gallery, FAQ,
For Planners and Contact pages in Swahili (or English), each with a clear "Book now" path.

**Why this priority**: Turns visitors into bookings.

**Independent Test**: Open each page on a phone in both languages; every page links into the wizard.

**Acceptance Scenarios**:

1. **Given** a visitor, **Then** Packages shows each package with what's included and a "from" price per guest count.
2. **Given** the gallery, **Then** images managed by admin are shown.
3. **Given** a search engine, **Then** each page has a title, description and language tags in sw and en.
4. **Given** FAQ, **Then** it covers deposit, cancellation, sale-or-return, empties, delivery areas and age rules.

---

### User Story 2 - Owner sees how the business is doing (Priority: P2)

The owner opens Reports: revenue by period, profit per booking, best sellers, outstanding
balances, and commission owed.

**Why this priority**: The goal is a money-making business; the owner needs the numbers.

**Independent Test**: With seeded bookings, revenue and profit for a month match a hand calculation.

**Acceptance Scenarios**:

1. **Given** the owner, **Then** reports show revenue, profit, best sellers and outstanding balances for a chosen period.
2. **Given** staff, **Then** Reports is not available.

---

### User Story 3 - The platform is live on its domain (Priority: P1)

The frontend, API and database run in production on the business domain with HTTPS, real
Supabase project, email sending and backups.

**Why this priority**: Nothing earns money until it is live.

**Independent Test**: Make a real booking on the production domain end-to-end and receive the notification email.

**Acceptance Scenarios**:

1. **Given** production, **Then** the end-to-end verification list from `Frank plan.md` passes on the live site.
2. **Given** direct database reads from the browser, **Then** they are blocked.

### Edge Cases

- Missing English translation for a string → falls back to Swahili, and a check flags missing keys.
- Gallery image upload too large → resized or rejected with a clear message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Site MUST provide Home, Packages, Gallery, FAQ, For Planners and Contact pages in Swahili and English.
- **FR-002**: Pages MUST have SEO metadata per language and be shareable with a preview.
- **FR-003**: Admin MUST manage gallery images.
- **FR-004**: Owner-only Reports MUST show revenue, profit per booking, best sellers, outstanding balances and commissions owed.
- **FR-005**: All translation keys MUST exist in both languages (checked automatically).
- **FR-006**: The platform MUST be deployed to production hosting on the business domain with HTTPS.
- **FR-007**: Production secrets MUST be configured in hosting, never committed.

### Key Entities

- **Gallery image**: image, caption sw/en, order, visible.
- Reports read existing bookings, payments, stock movements and commissions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Public pages load in under 3 seconds on a typical mobile connection in Dar es Salaam.
- **SC-002**: 100% of translation keys exist in both languages.
- **SC-003**: The end-to-end checklist from `Frank plan.md` passes on production.
- **SC-004**: Report figures match hand calculations on test data.

## Assumptions

- The `.co.tz` domain is bought by the owner; DNS access will be provided.
- Hosting: Vercel (frontend), Render or Railway (API), Supabase cloud (EU).
- Gallery photos are supplied by the owner.
