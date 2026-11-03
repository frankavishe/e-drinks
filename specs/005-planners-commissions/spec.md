# Feature Specification: Planner Accounts & Commissions

**Feature Branch**: `005-planners-commissions` (specs tracked on `build`)

**Created**: 2026-11-03

**Status**: Draft

**Input**: Build-order phase 6 of `Frank plan.md`: "Planner accounts, approvals, commissions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Planner signs up and is approved (Priority: P1)

A wedding or event planner signs up with email and password, name and phone. Their account
waits for approval. The owner approves them and sets a commission rate between 5% and 10%, or
declines them.

**Why this priority**: Planners bring repeat, large orders; approval controls who earns commission.

**Independent Test**: Sign up → login shows "awaiting approval"; owner approves at 7% → planner dashboard opens.

**Acceptance Scenarios**:

1. **Given** a new signup, **Then** the planner is pending and cannot create commission bookings.
2. **Given** the owner approves with a rate, **Then** the planner can use the dashboard.
3. **Given** a rate outside 5–10%, **Then** it is rejected.
4. **Given** a declined or suspended planner, **Then** they cannot log in to the dashboard.

---

### User Story 2 - Planner books for a client (Priority: P1)

An approved planner creates bookings for named clients using the same wizard, sees all their
bookings with status and payments, and downloads quote/invoice PDFs. Clients pay normal prices.

**Why this priority**: This is the planner's main reason to use the platform.

**Independent Test**: Planner creates a booking for "Client: Asha & Juma" → it appears in their
list and in admin with the planner attached; prices equal public prices.

**Acceptance Scenarios**:

1. **Given** an approved planner, **When** they book, **Then** the booking records the planner and client name.
2. **Given** a planner, **Then** they see only their own bookings.
3. **Given** planner views, **Then** no cost or margin data is shown.

---

### User Story 3 - Commission earned on Close and paid monthly (Priority: P2)

When a planner's booking reaches Closed, commission (rate × booking total excluding refundable
deposits and delivery) is earned. The owner sees commissions owed per planner and marks them
paid monthly. Planners see a statement of pending, earned and paid commission.

**Why this priority**: Correct, on-time commission keeps planners loyal.

**Independent Test**: Close a 2,000,000 TZS planner booking at 7% → 140,000 earned; mark paid →
statement shows paid with date.

**Acceptance Scenarios**:

1. **Given** a planner booking is created, **Then** a pending commission is recorded.
2. **Given** it reaches Closed, **Then** the commission becomes earned, based on the final settled amount.
3. **Given** it is Cancelled, **Then** no commission is earned.
4. **Given** the owner marks a month's earned commissions paid, **Then** they show as paid with the date.

### Edge Cases

- Planner's rate changes → applies to bookings created after the change only (rate snapshotted).
- Booking settled with returns → commission is on the final amount after sealed returns.
- Planner books for themselves → allowed; still commissionable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Planners MUST sign up with email/password and start as pending.
- **FR-002**: Owner MUST be able to approve/decline/suspend planners and set a 5–10% rate.
- **FR-003**: Approved planners MUST be able to create bookings for named clients at normal prices.
- **FR-004**: Planners MUST see only their own bookings, payments and PDFs.
- **FR-005**: System MUST snapshot the commission rate on the booking and record a pending commission.
- **FR-006**: Commission MUST become earned only on Closed, computed on the final settled
  drinks-and-add-ons amount (excluding delivery fee and refundable deposits).
- **FR-007**: Owner MUST be able to mark earned commissions paid; planners see a statement.
- **FR-008**: Business email notifies the owner of new planner signups and the planner on approval and booking confirmation.

### Key Entities

- **Profile (planner)**: status pending/approved/declined/suspended, commission rate.
- **Commission**: booking, planner, rate, amount, status pending/earned/paid, earned and paid dates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of commission test cases (earned only on Close, none on Cancel, rate snapshot) pass.
- **SC-002**: A planner can create a client booking in under 5 minutes.
- **SC-003**: The owner can see total commission owed per planner for a month in one screen.

## Assumptions

- "Commission comes out of margin": clients pay standard prices; commission is a business cost.
- Commission base excludes delivery fees and refundable empties deposits (assumed; adjust if the owner wants otherwise).
- Depends on 002–004.
