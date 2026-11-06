"""Cancellation refund and deposit amounts. Expected figures are hand-calculated."""

import pytest

from app.services.pricing import cancellation_refund, deposit_for, refund_due


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (30, 90_000),
        (15, 90_000),
        (14, 90_000),  # first day of "14+"
        (13, 50_000),  # last day of "7-13"
        (10, 50_000),
        (7, 50_000),
        (6, 0),  # first day of "under 7"
        (3, 0),
        (0, 0),
        (-2, 0),  # cancelled after the event date
    ],
)
def test_cancellation_refund_follows_the_policy(days, expected):
    assert cancellation_refund(100_000, days) == expected


@pytest.mark.parametrize(
    ("deposit", "days", "expected"),
    [
        (903_251, 14, 812_925),  # 812,925.9 rounds down
        (903_251, 10, 451_625),  # 451,625.5 rounds down
        (1, 14, 0),
        (1, 10, 0),
    ],
)
def test_cancellation_refund_rounds_down_to_whole_shillings(deposit, days, expected):
    assert cancellation_refund(deposit, days) == expected


def test_cancellation_refund_of_nothing_is_nothing():
    assert cancellation_refund(0, 30) == 0


@pytest.mark.parametrize(
    ("paid", "days", "expected"),
    [
        (0, 30, 0),  # nothing paid
        (0, 3, 0),
        (40_000, 14, 36_000),  # part of the deposit: policy on what was paid
        (40_000, 10, 20_000),
        (40_000, 3, 0),
        (100_000, 14, 90_000),  # exactly the deposit
        (100_000, 10, 50_000),
        (100_000, 3, 0),
        (150_000, 14, 140_000),  # above the deposit: the extra comes back in full
        (150_000, 10, 100_000),
        (150_000, 3, 50_000),
        (200_000, 14, 190_000),  # fully paid
        (200_000, 10, 150_000),
        (200_000, 3, 100_000),
    ],
)
def test_refund_due_penalises_only_the_deposit(paid, days, expected):
    assert refund_due(paid=paid, deposit_due=100_000, days_ahead=days) == expected


@pytest.mark.parametrize(
    ("total", "percent", "expected"),
    [
        (1_806_500, 50, 903_250),
        (1_806_501, 50, 903_251),  # rounds up, as the quote always has
        (1000, 33, 330),
        (1001, 33, 331),
        (0, 50, 0),
        (1000, 100, 1000),
    ],
)
def test_deposit_for_rounds_up(total, percent, expected):
    assert deposit_for(total, percent) == expected
