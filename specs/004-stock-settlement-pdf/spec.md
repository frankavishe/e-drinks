# Feature Specification: Stock, Settlement & PDFs

**Feature Branch**: `004-stock-settlement-pdf` (specs tracked on `build`)

**Created**: 2026-11-03

**Status**: Draft

**Input**: Build-order phase 5 of `Frank plan.md`: "Stock reservation and purchase list; returns/empties settlement; PDFs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reserve stock and know what to buy (Priority: P1)

When a booking becomes Confirmed, the stock on hand is reserved for it. Any shortfall goes onto a
purchase list with a needed-by date (the event date). When stock is bought from a wholesaler,
staff record it with quantity, unit cost and supplier; this raises on-hand stock and clears the
purchase list.

**Why this priority**: Without this, the business either runs short on event day or over-buys.

**Independent Test**: 20 crates on hand, confirm a booking needing 30 → 20 reserved, 10 on the
purchase list; receive 10 → list cleared.

**Acceptance Scenarios**:

1. **Given** a booking moves to Confirmed, **Then** available stock is reserved and any shortfall
   is listed with its needed-by date.
2. **Given** a booking is cancelled, **Then** its reservation is released and its purchase needs removed.
3. **Given** a purchase is received, **Then** on-hand stock rises, a movement with unit cost is
   recorded, and outstanding needs are reduced, earliest event first.
4. **Given** the owner, **Then** stock levels, reserved, available and purchase list are visible,
   with costs; staff see the same without costs.

---

### User Story 2 - Settle returns and empties after the event (Priority: P1)

After delivery, staff record per product what was delivered and what came back sealed
(sale-or-return within 48h), empties out and back, and lost or damaged equipment. The system
computes the final bill: refund or credit for returned sealed drinks, empties deposit refund
minus missing empties, damage charges at replacement cost (taken from the empties deposit
first), and the net amount due to or from the customer.

**Why this priority**: Sale-or-return and deposits are promises to customers; errors cost money and trust.

**Independent Test**: Deliver 30 crates, 4 sealed returned, 2 crates of empties missing, one
cooler lost → final bill matches a hand calculation.

**Acceptance Scenarios**:

1. **Given** sealed returns recorded within 48h of the event, **Then** they are credited at the snapshotted unit price.
2. **Given** returns recorded after 48h, **Then** they are refused unless the owner overrides.
3. **Given** missing empties, **Then** their deposit is kept; returned empties are refunded.
4. **Given** lost/damaged add-ons, **Then** replacement cost is charged, first from the empties deposit.
5. **Given** settlement is saved, **Then** returned stock goes back on hand and the booking can move to Returns settled.

---

### User Story 3 - Quote and invoice PDFs (Priority: P2)

Customers, planners and admin can download a quote PDF and an invoice PDF in Swahili or English,
showing the business name, TIN, booking number, lines, totals, payments and, once entered, the
EFD receipt number.

**Why this priority**: Planners and corporate clients need documents to get paid and for TRA.

**Independent Test**: Download the invoice for a confirmed booking in both languages and check the totals and TIN.

**Acceptance Scenarios**:

1. **Given** a booking, **Then** a quote PDF and an invoice PDF can be downloaded in either language.
2. **Given** settlement is done, **Then** the invoice shows returns, empties and damage lines and the net balance.
3. **Given** a customer via the tracking page, **Then** they can download PDFs for their own booking only.

### Edge Cases

- Booking edited after Confirmed (quantity changed) → reservation adjusted up or down.
- Stock adjustment for breakage or counting errors → recorded as an adjust movement with a reason.
- Returned quantity greater than delivered → rejected.
- Damage charges greater than the empties deposit → the remainder is added to the amount due.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST reserve stock on Confirmed and release it on Cancelled.
- **FR-002**: System MUST keep a purchase list of shortfalls with needed-by dates.
- **FR-003**: System MUST record every stock change as a movement (purchase, reserve, release,
  deliver, return, adjust) with booking and unit cost where applicable.
- **FR-004**: System MUST record delivered, returned, empties out/back and lost/damaged quantities per booking.
- **FR-005**: System MUST compute the settlement: sealed-return credit, empties refund, damage
  charges taken from the deposit first, and net due.
- **FR-006**: System MUST enforce the 48-hour sale-or-return window, with owner override.
- **FR-007**: System MUST generate quote and invoice PDFs in Swahili and English with business name and TIN from settings.
- **FR-008**: Cost data in stock screens and movements MUST be visible only to the owner.
- **FR-009**: Profit per booking (revenue − snapshotted unit costs) MUST be computable for the owner.

### Key Entities

- **Stock level**: product, on hand, reserved.
- **Stock movement**: product, quantity, type, booking, unit cost, supplier, reason.
- **Purchase need**: product, quantity short, needed-by date, booking.
- **Settlement**: on booking items/add-ons: delivered, returned, empties out/back, lost/damaged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On-hand stock always equals the sum of movements (verified by tests).
- **SC-002**: 100% of settlement test cases match hand calculations.
- **SC-003**: Staff can record a settlement for a 10-product booking in under 3 minutes.
- **SC-004**: PDFs are generated in under 5 seconds and open in common phone PDF viewers.

## Assumptions

- Depends on 003 for stage changes and on 002 for booking data.
- The EFD/VFD receipt number is typed in by staff (VFD integration is phase 2).
- Settlement refunds use the payment records from 003.
