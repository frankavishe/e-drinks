# Feature Specification: Booking Wizard, Tracking & Payment References

**Feature Branch**: `002-booking-wizard` (specs tracked on `build`)

**Created**: 2026-11-03

**Status**: Draft

**Input**: Build-order phase 3 of `Frank plan.md`: "Booking wizard + track page + payment-reference submission + WhatsApp handoff + Resend emails."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Book an event without an account (Priority: P1)

A customer goes through a step-by-step wizard: event details (type, date, start time, hours,
guests, venue/area, setup and collection time) → package or custom crates → add-ons → review
quote → contact details → confirmation. They accept the cancellation policy and confirm they
are 18 or older, then submit. They get a booking number (ED-YYYY-NNNN) and payment
instructions.

**Why this priority**: It is how the business gets orders.

**Independent Test**: Complete the wizard in Swahili for a 300-guest Silver wedding at a
Masaki venue and receive a booking number with the same totals as the quote.

**Acceptance Scenarios**:

1. **Given** a valid quote, **When** the customer submits contact details with policy and 18+
   accepted, **Then** a booking is created at stage "Request" with a unique number and the
   prices snapshotted.
2. **Given** policy or 18+ not accepted, **Then** submission is blocked.
3. **Given** the event falls inside the notice period, **Then** the booking is saved as a rush
   request and the confirmation says the business will confirm availability.
4. **Given** a saved venue is chosen, **Then** its area and address fill in automatically.
5. **Given** the language is switched to English mid-wizard, **Then** entered data is kept.

---

### User Story 2 - Hand off to WhatsApp (Priority: P1)

On the confirmation screen, a "Continue on WhatsApp" button opens WhatsApp with a prefilled
message containing the booking number, addressed to the business WhatsApp number.

**Why this priority**: WhatsApp is how customers in Dar es Salaam expect to talk to the business.

**Independent Test**: Tap the button and see a WhatsApp link with the business number and the
booking number in the message text.

**Acceptance Scenarios**:

1. **Given** a submitted booking, **When** the button is tapped, **Then** a WhatsApp link opens
   with the configured number and a message in the current language containing the booking number.

---

### User Story 3 - Track a booking and submit a payment reference (Priority: P1)

A customer enters their booking number and phone number to see the booking's status, items,
totals, amounts paid and due, and payment instructions (M-Pesa, Tigo Pesa, Airtel Money till
numbers and bank details). They pay by mobile money or bank, then submit the method, amount and
transaction reference, which shows as "pending confirmation".

**Why this priority**: Deposits lock dates; without this the business cannot collect money.

**Independent Test**: Look up a booking with the right number + phone → details shown; wrong
phone → not found; submit a deposit reference → shows as pending.

**Acceptance Scenarios**:

1. **Given** matching booking number and phone, **Then** the tracking page shows status, lines,
   totals, payments and balance due.
2. **Given** a non-matching phone, **Then** the response is the same "not found" as for an unknown
   booking number.
3. **Given** a reference is submitted, **Then** a pending payment record is created and shown.
4. **Given** the same reference is submitted twice for the booking, **Then** the duplicate is rejected.

---

### User Story 4 - The business is told by email (Priority: P2)

The business receives an email when a new booking is submitted and when a payment reference is
submitted. The customer gets a confirmation email if they gave an email address.

**Why this priority**: Staff must react quickly, but the booking itself works without email.

**Independent Test**: Submit a booking and a payment reference with the email service in test
mode → two notification emails recorded with the booking number.

**Acceptance Scenarios**:

1. **Given** a new booking, **Then** an email with booking number, event date and total goes to
   the business address.
2. **Given** a payment reference submission, **Then** an email with amount, method and
   reference goes to the business address.
3. **Given** the email service fails, **Then** the booking or payment is still saved and the
   failure is logged.

### Edge Cases

- Quote changes between review and submit (e.g. add-on taken by another booking) → submit
  re-checks and shows the new problem instead of saving.
- Phone numbers entered as 07xx, +2557xx or 2557xx are treated as the same number.
- Booking number lookups are rate-limited to slow down guessing.
- Customer with the same phone books again → linked to the same customer record.
- Submitted amount larger than the balance → accepted as pending; admin decides.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a multi-step booking wizard covering event, order (package or
  custom), add-ons, quote review, contact and confirmation.
- **FR-002**: System MUST re-price and re-check availability on submit, server-side, and save
  only if valid.
- **FR-003**: System MUST create bookings with a sequential yearly number ED-YYYY-NNNN, stage
  "Request", rush flag, policy-accepted time, 18+ confirmation and snapshotted prices.
- **FR-004**: System MUST store customers by name, phone (normalised) and optional email.
- **FR-005**: System MUST show payment instructions from settings after submission and on the
  tracking page.
- **FR-006**: System MUST provide a WhatsApp handoff link with the business number from settings.
- **FR-007**: System MUST let a customer view a booking only with booking number + matching phone.
- **FR-008**: System MUST accept payment reference submissions (kind deposit/balance, method,
  amount, reference) as pending payments, rejecting duplicates per booking.
- **FR-009**: System MUST send notification emails for new bookings and payment references, and
  must not fail the customer action if email fails.
- **FR-010**: All wizard, tracking and email text MUST be in Swahili (default) and English.
- **FR-011**: Wizard MUST be usable on a mobile phone screen.

### Key Entities

- **Booking**: number, customer, event details, setup/collect times, stage, rush flag, totals
  snapshot, deposit due, balance due date, policy/age confirmations, notes, language.
- **Booking item / Booking add-on**: product or add-on, quantity, snapshotted unit price and cost.
- **Customer**: name, phone, email.
- **Payment**: booking, kind, amount, method, reference, status (pending/confirmed/rejected).
- **Booking status history**: stage changes with time and actor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time customer can complete a booking on a phone in under 5 minutes.
- **SC-002**: 100% of saved bookings have totals equal to the quote shown at review.
- **SC-003**: Business notification emails arrive within 1 minute of submission.
- **SC-004**: A booking cannot be viewed without both its number and the matching phone.

## Assumptions

- Depends on 001 for quotes and availability.
- Notification recipient address is a setting.
- Admin confirmation of payments and stage changes is in feature 003.
- Automatic WhatsApp/SMS messages are phase 2.
