# Data Model: Booking Wizard, Tracking & Payment References

Most tables already exist from the base migration. This feature adds one table and two constraints.

## Schema changes (one migration)

| Change | Detail |
|---|---|
| New `booking_counters` | `year` integer PK, `last_no` integer. RLS enabled, no policies. |
| `customers.phone` | Index becomes unique. |
| `payments` | Partial unique index `uq_payments_booking_reference` on `(booking_id, reference)` where `reference <> '' AND status <> 'rejected'`. |

## Written at booking creation

**Customer**: `name`, `phone` (`255XXXXXXXXX`), `email`. Existing phone: linked; name kept; blank email filled.

**Booking**

| Field | Value |
|---|---|
| `code` | `ED-YYYY-NNNN`, from the counter |
| `status` | `request` |
| `is_rush` | from the server's quote |
| `subtotal`, `addons_total`, `delivery_fee`, `empties_deposit`, `total`, `deposit_due`, `balance_due_date` | snapshot of the server's quote |
| `delivery_fee_custom`, `custom_area` | set for an unlisted area |
| `venue_id`, `venue_name`, `venue_address` | snapshotted from the saved venue, otherwise as typed |
| `policy_accepted_at`, `age_confirmed` | server time; true |
| `lang` | `sw` or `en` |

**BookingItem**: `product_id`, `qty`, `unit_price` (from the quote), `unit_cost` (from `Product.cost_price`).

**BookingAddon**: `addon_id`, `qty`, `unit_price`.

**BookingStatusHistory**: first row `None → request`, `changed_by` null.

## Written at payment submission

**Payment**: `kind` (`deposit`/`balance`), `method` (`mpesa`/`tigopesa`/`airtel`/`bank`), `amount`,
`reference` (trimmed, upper-case), `status=pending`.

## Derived, never stored

- `amount_paid` = sum of **confirmed** deposit and balance payments
- `amount_pending` = sum of **pending** deposit and balance payments
- `balance_due` = `total − amount_paid`, not below 0

## Validation

- Name 1–120 characters; email optional and shaped like an address; notes up to 1000 characters.
- `accept_policy` and `age_confirmed` must be true.
- `event_type`: `wedding`, `corporate`, `birthday`, `other`.
- A `venue_id` must exist and belong to `area_id`.
- Payment amount ≥ 1 (above the balance is allowed); reference 1–80 characters.
- Payments are refused on `cancelled` and `closed` bookings.
