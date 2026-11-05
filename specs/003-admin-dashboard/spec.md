# Feature Specification: Admin Dashboard

**Feature Branch**: `003-admin-dashboard` (specs tracked on `build`)

**Created**: 2026-11-03

**Status**: Draft

**Input**: Build-order phase 4 of `Frank plan.md`: "Admin: bookings, payment confirmation, stage changes, calendar, catalog, zones/venues, settings."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See and manage bookings (Priority: P1)

Staff or the owner log in and see today's and upcoming events, then a searchable list of
bookings (filter by stage, date, rush). Opening a booking shows the event, items, add-ons,
payments, status history and notes.

**Why this priority**: Day-to-day operations run from this screen.

**Independent Test**: Log in as staff, find a booking by number and by phone, open it and see
payments and history.

**Acceptance Scenarios**:

1. **Given** a logged-in staff member, **Then** Today/Upcoming lists events by date with stage and rush flags.
2. **Given** filters, **Then** the list shows only matching bookings.
3. **Given** a staff member, **Then** no cost, margin or profit figures appear anywhere.
4. **Given** the owner, **Then** cost and profit per booking are visible.

---

### User Story 2 - Confirm payments and move bookings through stages (Priority: P1)

Staff confirm or reject submitted payment references. They move a booking through
Request → Quoted → Confirmed → Fully paid → Delivered → Returns settled → Closed, or Cancelled.
The system refuses moves the rules don't allow; e.g. Confirmed needs a confirmed deposit.
Staff can approve or decline rush requests, and record a free date change.

**Why this priority**: Money and commitments are only real once a person confirms them.

**Independent Test**: Confirm a deposit → booking can move to Confirmed; try Confirmed without a
deposit → refused; cancel 10 days before → refund shown as 50% of the deposit.

**Acceptance Scenarios**:

1. **Given** a pending payment, **When** confirmed, **Then** it records who confirmed it and when,
   and paid totals update.
2. **Given** confirmed payments ≥ 50% of total, **Then** the move to Confirmed is allowed; otherwise refused.
3. **Given** confirmed payments = total, **Then** the move to Fully paid is allowed.
4. **Given** a cancellation, **Then** the refund due follows policy: 14+ days → deposit minus 10%;
   7–13 days → 50%; under 7 days → nothing, plus anything paid above the deposit in full, and a
   refund payment record can be created.
5. **Given** a first date change made 7+ days before the event, **Then** it is free; a second
   change or a change inside 7 days is refused, or recorded as an exception by the owner.
6. **Given** every stage change, **Then** a history entry records stage, time and actor.
7. **Given** a rush request, **When** approved, **Then** it can proceed like a normal booking.
8. **Given** a rush request, **When** declined, **Then** the booking is cancelled and everything
   paid is due back in full.
9. **Given** a booking with a provisional delivery fee, **When** admin sets the fee, **Then** the
   total and deposit update; until then it cannot move forward.
10. **Given** the owner, **When** moving a booking back one stage with a note, **Then** it is allowed
    and recorded; staff are refused.

---

### User Story 3 - Calendar of bookings and equipment (Priority: P2)

A month/week calendar shows bookings per day and how many coolers, servers and other add-ons
are committed versus owned on each day.

**Why this priority**: Prevents overcommitting on busy wedding weekends.

**Independent Test**: Two bookings on one Saturday → the calendar shows both and the combined add-on usage.

**Acceptance Scenarios**:

1. **Given** bookings in a month, **Then** each day shows its bookings and add-on usage vs capacity.

---

### User Story 4 - Manage catalog, zones, venues and settings (Priority: P2)

The owner adds and edits products (Swahili/English names, unit, alcohol flag, cost price,
image, returnable glass, empties deposit, active), price tiers, packages and their rules,
add-ons and capacities, zones with delivery fees, areas, saved venues and business settings.

**Why this priority**: The owner must change prices and options without a developer.

**Independent Test**: Change a tier price → the next quote uses it; existing bookings keep their old price.

**Acceptance Scenarios**:

1. **Given** the owner edits a price, **Then** new quotes use it and existing bookings are unchanged.
2. **Given** a product is deactivated, **Then** it disappears from public catalog and packages.
3. **Given** staff (not owner), **Then** catalog cost fields are hidden and settings are read-only.

### Edge Cases

- Two staff confirm the same payment at once → only one confirmation takes effect.
- Rejecting a payment that was already used to move to Confirmed → refused unless the stage is moved back first.
- Deleting a product used in bookings → not allowed; deactivate instead.
- Overlapping tiers for a product → rejected on save.
- Moving to Confirmed when the add-ons have since been taken → refused.
- Cancelling or declining with a payment still pending → refused until it is confirmed or rejected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Admin area MUST require login as staff or owner.
- **FR-002**: System MUST provide Today/Upcoming, booking list with search/filters, and booking detail.
- **FR-003**: System MUST let staff confirm/reject payments, recording actor and time.
- **FR-004**: System MUST enforce stage-transition rules and record every change in history.
- **FR-005**: System MUST compute cancellation refunds by the policy and record refund payments.
- **FR-006**: System MUST enforce one free date change 7+ days ahead, re-checking availability.
- **FR-007**: System MUST let staff approve/decline rush requests.
- **FR-008**: System MUST show a calendar with bookings and add-on usage vs capacity per day.
- **FR-009**: Owner MUST be able to manage products, tiers, packages/rules, add-ons, zones, areas, venues and settings.
- **FR-010**: Staff MUST NOT see cost, margin or profit, and MUST NOT edit settings or cost prices.
- **FR-011**: Admin can record the EFD receipt number and internal notes on a booking.
- **FR-012**: Admin UI MUST be available in Swahili and English.
- **FR-013**: Admin MUST be able to set the delivery fee on a provisional booking in Request or
  Quoted, which recalculates the total and deposit.
- **FR-014**: System MUST re-check add-on capacity on the move to Confirmed.
- **FR-015**: Only the owner MAY move a booking back a stage, one step at a time, with a note.

### Key Entities

- Booking, Payment, Booking status history (from 002); Profile (staff/owner roles);
  catalog entities, Zone, Area, Venue, Setting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can confirm a payment and move a booking to Confirmed in under 1 minute.
- **SC-002**: 100% of disallowed stage moves are refused, with the reason shown.
- **SC-003**: No staff-visible screen or response contains cost or profit (verified by tests).
- **SC-004**: The owner can change a price and see it in a new quote with no developer help.

## Assumptions

- Staff and owner accounts are created by the owner (planner self-signup is feature 005).
- Stock reservation on Confirm, and settlement on Delivered/Returns, come in feature 004.
- "Quoted" means admin sent a reviewed quote to a customer whose request needed adjustment.
- Confirming a payment does not move the stage; moving is a separate action offered right after.
- A product image is a URL; uploading files is out of scope.
