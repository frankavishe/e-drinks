# Feature Specification: Pricing, Availability & Public Quote

**Feature Branch**: `001-pricing-availability` (specs tracked on `build`)

**Created**: 2026-11-03

**Status**: Draft

**Input**: Build-order phase 2 of `Frank plan.md`: "Pricing + availability services with tests; public quote endpoint."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get an instant price for a package event (Priority: P1)

A customer planning a wedding picks a package (Bronze/Silver/Gold/Premium bar), enters the
number of guests, the event length in hours, the event date and the venue's area. They
immediately see the drink quantities (in whole crates/packs), the price for each line, the
delivery fee, the refundable empties deposit, the total, the 50% deposit and the date the
balance is due.

**Why this priority**: Pricing is the core of the business; every booking, invoice and
profit figure depends on it being correct.

**Independent Test**: Request a quote for a 300-guest Silver wedding, 5 hours, at a venue
in Masaki, and check every figure against a hand calculation from the seeded catalog.

**Acceptance Scenarios**:

1. **Given** a package with per-guest rules, **When** a quote is requested for N guests and
   H hours, **Then** each product quantity equals guests × rule (scaled for hours where the
   rule is per-hour), rounded **up** to whole packs.
2. **Given** a product with quantity tiers (e.g. 1–9, 10–49, 50+), **When** the quantity falls
   into a tier, **Then** that tier's unit price applies to the whole line.
3. **Given** the venue area belongs to a zone, **When** quoting, **Then** the zone's fixed
   delivery fee is added.
4. **Given** the quote includes returnable glass products, **When** quoting, **Then** an
   empties deposit (packs × per-pack deposit) is shown separately and included in the total.
5. **Given** any quote, **Then** the deposit due is 50% of the total (whole shillings, rounded
   up) and the balance due date is 3 days before the event.

---

### User Story 2 - Build a custom order and adjust quantities (Priority: P1)

A customer who does not want a package picks products and crate counts directly, or takes a
package and edits the suggested quantities, and gets a new quote each time.

**Why this priority**: Many customers know exactly what they want; the custom crate builder is
a first-class ordering path in the business rules.

**Independent Test**: Quote a custom order of 12 crates of soda + 3 crates of beer and confirm
tier prices and totals; then change a quantity and confirm the quote updates.

**Acceptance Scenarios**:

1. **Given** a custom list of products and pack quantities, **When** quoted, **Then** each line
   uses the tier price for its quantity.
2. **Given** a package quote, **When** the customer overrides a line's quantity, **Then** the
   quote uses the edited quantity instead of the computed one.
3. **Given** an order whose total is below the minimum order setting, **When** quoted, **Then**
   the quote is returned but flagged as below minimum, showing the minimum amount.

---

### User Story 3 - Add equipment and staff only when available (Priority: P2)

The customer adds coolers, ice bags, drink servers (per shift) and a bartender. The system
checks that enough of each is free across the whole period from setup time to collection
time, counting other confirmed bookings, and refuses quantities that are not available.

**Why this priority**: Double-booking equipment or servers would break a delivery promise;
add-ons are also part of the price.

**Independent Test**: With 10 coolers owned and an overlapping confirmed booking holding 7,
request 4 coolers for an overlapping window → refused, showing 3 available; request 3 → OK.

**Acceptance Scenarios**:

1. **Given** an add-on with owned capacity C and existing bookings holding Q during any
   moment of the requested window, **When** more than C − Q is requested, **Then** the quote
   reports the add-on as unavailable with the number still free.
2. **Given** another booking whose window touches but does not overlap (its collection ends
   when this setup starts), **Then** it does not reduce availability.
3. **Given** add-ons within capacity, **Then** their prices are added to the quote.

---

### User Story 4 - Know when a booking is a rush request (Priority: P2)

If the event is sooner than the notice period (3 days, or 7 days when servers are booked,
both editable in settings), the quote says the booking will be a rush request that the
business must approve by hand.

**Why this priority**: It protects the business from promises it cannot keep, while still
capturing short-notice demand.

**Independent Test**: Quote for an event 2 days away without servers → rush; 5 days away with
servers → rush; 8 days away with servers → not rush.

**Acceptance Scenarios**:

1. **Given** today and an event date closer than the applicable notice days, **When** quoted,
   **Then** the quote is marked rush.
2. **Given** the owner changes the notice setting, **Then** new quotes use the new value.

---

### User Story 5 - Get a delivery price for an unlisted area (Priority: P3)

A customer whose venue area is not on the list can still get a quote; delivery is shown as
"custom quote — to be confirmed" and the total is marked as excluding delivery.

**Why this priority**: Captures leads outside the mapped zones without blocking them.

**Independent Test**: Quote with a free-text area → delivery shown as pending, total excludes it.

**Acceptance Scenarios**:

1. **Given** an area not in the list, **When** quoted, **Then** delivery fee is reported as
   "custom quote" and excluded from the total, which is flagged as provisional.

### Edge Cases

- Zero or negative guests, hours or quantities → rejected with a clear message.
- Event date in the past → rejected.
- Product that is inactive, or a package referencing an inactive product → that product is
  excluded from package quotes; requesting it in a custom order is rejected.
- Quantity exactly at a tier boundary (e.g. 10) uses the higher tier.
- Product with no tier covering quantity 1 → treated as a catalog error and reported.
- Collection the next morning (window crosses midnight) is handled as one continuous window.
- Cancelled bookings and non-confirmed requests do not hold add-on capacity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute quotes from catalog data: products, quantity tiers, packages
  and package rules, add-ons, zones/areas and settings.
- **FR-002**: System MUST convert package rules to quantities as guests × qty-per-guest,
  multiplied by (hours ÷ the package's base hours) for per-hour rules, then rounded up to whole
  packs.
- **FR-003**: System MUST let the customer override any computed line quantity, and accept fully
  custom product lists.
- **FR-004**: System MUST price each line with the tier whose minimum quantity is the highest one
  not exceeding the line quantity.
- **FR-005**: System MUST add add-on charges (per unit, per shift for servers), the zone delivery
  fee for listed areas, and the empties deposit for returnable products.
- **FR-006**: System MUST compute deposit due = 50% of the total rounded up to the whole
  shilling, and balance due date = event date − 3 days.
- **FR-007**: System MUST check add-on availability across the setup→collection window against
  bookings that hold equipment (Confirmed or later, not Cancelled/Closed), and report available
  counts when short.
- **FR-008**: System MUST flag rush when the event is closer than the notice days (the server
  notice value if servers are included), read from settings.
- **FR-009**: System MUST flag quotes below the minimum order setting.
- **FR-010**: System MUST expose quoting publicly (no login) along with the catalog, packages,
  zones/areas and add-ons needed to build a quote.
- **FR-011**: Public quote and catalog responses MUST NOT expose cost prices or margins.
- **FR-012**: All amounts MUST be whole Tanzanian shillings, VAT-inclusive.
- **FR-013**: Quote line names MUST be available in Swahili and English.

### Key Entities

- **Quote**: an unsaved price calculation: lines, add-ons, delivery fee, empties deposit,
  subtotal, total, deposit due, balance due date, flags (rush, below minimum, provisional
  delivery, unavailable add-ons).
- **Quote line**: product, pack quantity, unit price, line total, source (package or custom).
- **Availability window**: setup time to collection time for an event.
- Uses existing catalog entities: Product, Price tier, Package, Package rule, Add-on, Zone,
  Area, Setting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the pricing test cases (tiers, rounding, zone fee, empties, deposit, rush,
  minimum order, availability overlap) match hand-calculated results.
- **SC-002**: A customer receives a full quote within 2 seconds of submitting event details.
- **SC-003**: No quote ever offers more of an add-on than is free in the requested window.
- **SC-004**: Changing a setting (minimum order, notice days) affects the next quote with no
  code change.

## Assumptions

- Prices in the catalog are VAT-inclusive; no separate VAT line is shown.
- The 50% deposit and 3-day balance rule are fixed business rules for this phase.
- Server prices are per shift; one shift covers one event's setup→collection window.
- Event length (hours) scales only rules marked per-hour.
- The seeded catalog, packages, add-ons and Dar zones/areas from Phase 1 are the test data.
- Saving a quote as a booking is out of scope (feature 002).
