"""Plain-text notification emails. Sending never raises: a booking must not fail because of email."""

import logging
from dataclasses import dataclass
from datetime import date

import resend

from app.config import get_settings
from app.models import Booking, Payment

logger = logging.getLogger(__name__)

_KINDS = {"deposit": "Amana / Deposit", "balance": "Salio / Balance"}
_METHODS = {
    "mpesa": "M-Pesa",
    "tigopesa": "Tigo Pesa",
    "airtel": "Airtel Money",
    "bank": "Benki / Bank",
}

_CUSTOMER_TEXT = {
    "sw": {
        "subject": "Oda yako {code} imepokelewa",
        "received": "Oda yako imepokelewa.",
        "code": "Namba ya oda",
        "event_date": "Tarehe ya tukio",
        "total": "Jumla",
        "deposit": "Amana",
        "balance_date": "Salio linalipwa kabla ya",
        "rush": "Tukio lako liko karibu. Tutakuthibitishia kama tunaweza kulihudumia kabla hujalipa amana.",
        "provisional": "Jumla hii haina usafirishaji. Tutakuthibitishia bei ya usafirishaji.",
        "how_to_pay": "Jinsi ya kulipa",
        "bank": "Benki",
        "no_details": "Tutakutumia namba za malipo kupitia WhatsApp.",
    },
    "en": {
        "subject": "Your booking {code} has been received",
        "received": "Your booking has been received.",
        "code": "Booking number",
        "event_date": "Event date",
        "total": "Total",
        "deposit": "Deposit",
        "balance_date": "Balance due by",
        "rush": "Your event is soon. We'll confirm whether we can serve it before you pay a deposit.",
        "provisional": "This total doesn't include delivery. We'll confirm the delivery price.",
        "how_to_pay": "How to pay",
        "bank": "Bank",
        "no_details": "We'll send you the payment numbers on WhatsApp.",
    },
}


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


def _tzs(amount: int) -> str:
    return f"TSh {amount:,}"


def _date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def booking_to_business(to: str, booking: Booking, name: str, phone: str) -> Email:
    lines = [
        "Oda mpya / New booking",
        "",
        f"Namba ya oda / Booking number: {booking.code}",
        f"Mteja / Customer: {name}",
        f"Simu / Phone: {phone}",
        f"Tarehe ya tukio / Event date: {_date(booking.event_date)}",
        f"Jumla / Total: {_tzs(booking.total)}",
    ]
    if booking.is_rush:
        lines.append("RUSH: Tukio liko ndani ya muda wa taarifa / Event is inside the notice period")
    if booking.delivery_fee_custom:
        lines.append(
            "Bei ya usafirishaji bado haijathibitishwa / Delivery price still to be confirmed"
        )
    return Email(to, f"Oda mpya / New booking: {booking.code}", "\n".join(lines))


def booking_to_customer(to: str, booking: Booking, public: dict[str, str]) -> Email:
    """Only our own text and settings, so this can't relay a message to someone else's address."""
    words = _CUSTOMER_TEXT[booking.lang]
    lines = [
        words["received"],
        "",
        f"{words['code']}: {booking.code}",
        f"{words['event_date']}: {_date(booking.event_date)}",
        f"{words['total']}: {_tzs(booking.total)}",
        f"{words['deposit']}: {_tzs(booking.deposit_due)}",
        f"{words['balance_date']}: {_date(booking.balance_due_date)}",
    ]
    if booking.is_rush:
        lines += ["", words["rush"]]
    if booking.delivery_fee_custom:
        lines += ["", words["provisional"]]

    details = [
        ("M-Pesa", public["mpesa_till"]),
        ("Tigo Pesa", public["tigopesa_lipa"]),
        ("Airtel Money", public["airtel_lipa"]),
        (words["bank"], public["bank_details"]),
    ]
    lines += ["", f"{words['how_to_pay']}:"]
    lines += [f"{label}: {value}" for label, value in details if value.strip()] or [
        words["no_details"]
    ]
    return Email(to, words["subject"].format(code=booking.code), "\n".join(lines))


def payment_to_business(to: str, code: str, payment: Payment) -> Email:
    lines = [
        "Malipo mapya / New payment reference",
        "",
        f"Namba ya oda / Booking number: {code}",
        f"Malipo ya / Payment for: {_KINDS[payment.kind]}",
        f"Kiasi / Amount: {_tzs(payment.amount)}",
        f"Njia ya malipo / Method: {_METHODS[payment.method]}",
        f"Namba ya muamala / Reference: {payment.reference}",
    ]
    return Email(to, f"Malipo mapya / New payment reference: {code}", "\n".join(lines))


def send_email(email: Email) -> None:
    """Run as a background task, after the booking or payment is committed."""
    if not email.to:
        logger.warning("No address to send to, skipped: %s", email.subject)
        return
    settings = get_settings()
    if not settings.resend_api_key:
        logger.info(
            "RESEND_API_KEY is empty, not sending.\nTo: %s\nSubject: %s\n\n%s",
            email.to,
            email.subject,
            email.text,
        )
        return
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [email.to],
                "subject": email.subject,
                "text": email.text,
            }
        )
    except Exception:
        logger.exception("Could not send email: %s", email.subject)
