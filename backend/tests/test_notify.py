"""Notification emails: contents per the contract table, and failures never reach the customer."""

import logging
from datetime import date

import pytest
import resend
from sqlalchemy import func, select

from app.config import get_settings
from app.models import Booking, Payment
from app.services.notify import (
    Email,
    booking_to_business,
    booking_to_customer,
    payment_to_business,
    send_email,
)
from tests.test_booking_api import booking_body
from tests.test_public_api import ids  # noqa: F401  (ids is a fixture)
from tests.test_tracking_api import payment_body

BUSINESS = "admin@example.test"
CUSTOMER = "asha@example.test"


def tzs(amount: int) -> str:
    return f"TSh {amount:,}"


def shown(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%d/%m/%Y")


def sample_booking(**overrides) -> Booking:
    values = {
        "code": "ED-2030-0001",
        "lang": "sw",
        "event_date": date(2030, 1, 12),
        "balance_due_date": date(2030, 1, 9),
        "total": 1806500,
        "deposit_due": 903250,
        "is_rush": False,
        "delivery_fee_custom": False,
    }
    return Booking(**{**values, **overrides})


NO_DETAILS = {"mpesa_till": "", "tigopesa_lipa": "", "airtel_lipa": "", "bank_details": ""}


async def book(client, ids, **overrides):
    payload = await booking_body(client, ids, **overrides)
    res = await client.post("/public/bookings", json=payload)
    assert res.status_code == 201, res.text
    return payload, res.json()


# New booking, to the business


async def test_new_booking_tells_the_business(client, ids, sent_emails):
    payload, created = await book(client, ids, name="Asha", phone="+255 712-345-678")
    assert len(sent_emails) == 1
    email = sent_emails[0]
    assert email["to"] == [BUSINESS]
    assert email["from"] == get_settings().email_from
    assert created["code"] in email["subject"]
    for expected in (
        created["code"],
        "Asha",
        "255712345678",
        shown(payload["event_date"]),
        tzs(created["total"]),
    ):
        assert expected in email["text"]


def test_business_booking_email_is_in_both_languages():
    email = booking_to_business(BUSINESS, sample_booking(), "Asha", "255712345678")
    for label in ("Jumla", "Total", "Tarehe ya tukio", "Event date"):
        assert label in email.text


def test_business_booking_email_has_no_notes_unless_needed():
    email = booking_to_business(BUSINESS, sample_booking(), "Asha", "255712345678")
    assert "RUSH" not in email.text
    assert "usafirishaji" not in email.text.lower()


def test_business_booking_email_flags_rush_and_provisional():
    booking = sample_booking(is_rush=True, delivery_fee_custom=True)
    email = booking_to_business(BUSINESS, booking, "Asha", "255712345678")
    assert "RUSH" in email.text
    assert "usafirishaji" in email.text.lower()
    assert "delivery" in email.text.lower()


# New booking, to the customer


@pytest.mark.parametrize(
    "lang, expected, other",
    [("sw", "Tarehe ya tukio", "Event date"), ("en", "Event date", "Tarehe ya tukio")],
)
async def test_customer_email_is_in_the_booking_language(
    client, ids, sent_emails, lang, expected, other
):
    payload, created = await book(client, ids, email=CUSTOMER, lang=lang)
    assert [e["to"] for e in sent_emails] == [[BUSINESS], [CUSTOMER]]
    email = sent_emails[1]
    assert created["code"] in email["subject"]
    for value in (
        created["code"],
        shown(payload["event_date"]),
        tzs(created["total"]),
        tzs(created["deposit_due"]),
        shown(created["balance_due_date"]),
        expected,
    ):
        assert value in email["text"]
    assert other not in email["text"]


async def test_customer_email_has_nothing_the_customer_typed(client, ids, sent_emails):
    await book(
        client,
        ids,
        email=CUSTOMER,
        name="TYPEDNAME",
        notes="TYPEDNOTES",
        venue_name="TYPEDVENUE",
        venue_address="TYPEDADDRESS",
    )
    email = sent_emails[1]
    assert email["to"] == [CUSTOMER]
    assert "TYPED" not in email["text"]
    assert "TYPED" not in email["subject"]


async def test_no_customer_email_without_an_address(client, ids, sent_emails):
    await book(client, ids)
    assert [e["to"] for e in sent_emails] == [[BUSINESS]]


def test_customer_email_lists_only_the_payment_details_that_are_set():
    details = {**NO_DETAILS, "mpesa_till": "123456", "bank_details": "CRDB 0150"}
    text = booking_to_customer(CUSTOMER, sample_booking(lang="en"), details).text
    assert "M-Pesa: 123456" in text
    assert "Bank: CRDB 0150" in text
    assert "Tigo Pesa" not in text
    assert "Airtel" not in text


@pytest.mark.parametrize("lang, expected", [("sw", "WhatsApp"), ("en", "WhatsApp")])
def test_customer_email_says_so_when_no_payment_details_are_set(lang, expected):
    text = booking_to_customer(CUSTOMER, sample_booking(lang=lang), NO_DETAILS).text
    assert expected in text


def test_customer_email_warns_about_rush_and_provisional():
    plain = booking_to_customer(CUSTOMER, sample_booking(lang="en"), NO_DETAILS).text
    assert "event is soon" not in plain
    assert "doesn't include delivery" not in plain

    booking = sample_booking(lang="en", is_rush=True, delivery_fee_custom=True)
    text = booking_to_customer(CUSTOMER, booking, NO_DETAILS).text
    assert "event is soon" in text
    assert "doesn't include delivery" in text


# Payment reference, to the business


async def test_payment_reference_tells_the_business(client, ids, sent_emails):
    _, created = await book(client, ids)
    sent_emails.clear()
    res = await client.post(
        f"/public/bookings/{created['code']}/payments",
        json=payment_body(amount=903250, method="mpesa", kind="deposit", reference="abc123"),
    )
    assert res.status_code == 201, res.text
    assert len(sent_emails) == 1
    email = sent_emails[0]
    assert email["to"] == [BUSINESS]
    assert created["code"] in email["subject"]
    for expected in (created["code"], "Amana", "Deposit", tzs(903250), "M-Pesa", "ABC123"):
        assert expected in email["text"]


def test_payment_email_is_in_both_languages():
    payment = Payment(kind="balance", method="bank", amount=5000, reference="R1")
    text = payment_to_business(BUSINESS, "ED-2030-0001", payment).text
    for label in ("Salio", "Balance", "Benki", "Bank", "Kiasi", "Amount"):
        assert label in text


async def test_booking_and_reference_record_two_notifications(client, ids, sent_emails):
    """The story's independent test."""
    _, created = await book(client, ids)
    await client.post(f"/public/bookings/{created['code']}/payments", json=payment_body())
    assert [e["to"] for e in sent_emails] == [[BUSINESS], [BUSINESS]]
    assert all(created["code"] in e["text"] for e in sent_emails)


async def test_refused_actions_send_nothing(client, ids, sent_emails):
    payload = await booking_body(client, ids)
    res = await client.post("/public/bookings", json={**payload, "expected_total": 1})
    assert res.status_code == 409
    assert sent_emails == []

    _, created = await book(client, ids)
    url = f"/public/bookings/{created['code']}/payments"
    await client.post(url, json=payment_body())
    sent_emails.clear()
    assert (await client.post(url, json=payment_body())).status_code == 409
    assert sent_emails == []


# Sending


async def test_sender_failure_is_logged_and_everything_is_still_saved(
    client, ids, seeded_session, monkeypatch, caplog
):
    def fail(params):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(resend.Emails, "send", fail)
    with caplog.at_level(logging.ERROR, logger="app.services.notify"):
        _, created = await book(client, ids, email=CUSTOMER)
        res = await client.post(
            f"/public/bookings/{created['code']}/payments", json=payment_body()
        )
    assert res.status_code == 201, res.text
    assert await seeded_session.scalar(select(func.count()).select_from(Booking)) == 1
    assert await seeded_session.scalar(select(func.count()).select_from(Payment)) == 1
    failures = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(failures) == 3
    assert all(created["code"] in r.getMessage() for r in failures)


def test_empty_api_key_logs_instead_of_sending(monkeypatch, sent_emails, caplog):
    monkeypatch.setattr(get_settings(), "resend_api_key", "")
    with caplog.at_level(logging.INFO, logger="app.services.notify"):
        send_email(Email(to=BUSINESS, subject="ED-2030-0001", text="The body"))
    assert sent_emails == []
    assert BUSINESS in caplog.text
    assert "ED-2030-0001" in caplog.text
    assert "The body" in caplog.text


def test_blank_recipient_warns_and_skips(sent_emails, caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.notify"):
        send_email(Email(to="", subject="ED-2030-0001", text="The body"))
    assert sent_emails == []
    assert "ED-2030-0001" in caplog.text


async def test_booking_succeeds_with_no_business_address(client, ids, monkeypatch, sent_emails):
    monkeypatch.setattr(get_settings(), "admin_email", "")
    await book(client, ids)
    assert sent_emails == []
