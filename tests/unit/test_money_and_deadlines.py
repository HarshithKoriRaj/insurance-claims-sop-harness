from datetime import date, datetime, timezone
from decimal import Decimal, Inexact, Rounded, localcontext

import pytest

from app.claims.deadlines import DeadlineStatus, appeal_deadline_status
from app.claims.money import format_usd

_NOT_A_PLAIN_AMOUNT = "expected a finite, non-negative Decimal"


def test_usd_formatting_keeps_cents_and_thousands():
    assert format_usd(Decimal("1450.00")) == "$1,450.00"
    assert format_usd(Decimal("0.00")) == "$0.00"
    assert format_usd(Decimal("3200.5")) == "$3,200.50"
    assert format_usd(Decimal("1234567.89")) == "$1,234,567.89"


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        (Decimal("-5.00"), _NOT_A_PLAIN_AMOUNT),
        (Decimal("-0.00"), _NOT_A_PLAIN_AMOUNT),
        (Decimal("NaN"), _NOT_A_PLAIN_AMOUNT),
        (Decimal("Infinity"), _NOT_A_PLAIN_AMOUNT),
        (1450.0, _NOT_A_PLAIN_AMOUNT),
        (1450, _NOT_A_PLAIN_AMOUNT),
        (Decimal("0.125"), "expected whole cents"),
    ],
    ids=["negative", "negative-zero", "nan", "infinity", "float", "int", "fraction-of-a-cent"],
)
def test_usd_formatting_accepts_only_non_negative_whole_cent_decimals(amount, message):
    with pytest.raises(ValueError, match=message):
        format_usd(amount)


def test_usd_formatting_does_not_depend_on_the_decimal_context():
    with localcontext() as context:
        context.prec = 6
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert format_usd(Decimal("12345.67")) == "$12,345.67"
        assert format_usd(Decimal("1.250")) == "$1.25"
        with pytest.raises(ValueError, match="expected whole cents"):
            format_usd(Decimal("0.125"))
    assert format_usd(Decimal("1E+26")) == "$100,000,000,000,000,000,000,000,000.00"


@pytest.mark.parametrize(
    ("business_date", "expected"),
    [
        (date(2026, 3, 1), (17, False)),
        (date(2026, 3, 17), (1, False)),
        (date(2026, 3, 18), (0, False)),
        (date(2026, 3, 19), (-1, True)),
        (date(2026, 9, 28), (-194, True)),
    ],
    ids=["demo-date", "day-before", "deadline-day", "day-after", "real-date"],
)
def test_appeal_deadline_status_around_the_deadline(store, business_date, expected):
    status = appeal_deadline_status(store.claim("CL-2048"), business_date)
    assert (status.days_remaining, status.passed) == expected


def test_claim_without_a_deadline_has_no_status(store):
    assert appeal_deadline_status(store.claim("CL-2011"), date(2026, 3, 1)) is None


@pytest.mark.parametrize("case_id", ["CL-2048", "CL-2011"], ids=["with-deadline", "without-deadline"])
def test_a_timestamp_is_not_accepted_as_the_business_date(store, case_id):
    with pytest.raises(TypeError, match="business_date must be a date, not datetime"):
        appeal_deadline_status(store.claim(case_id), datetime(2026, 3, 1, tzinfo=timezone.utc))


def test_a_deadline_status_is_built_from_plain_dates():
    with pytest.raises(TypeError, match="deadline must be a date, not datetime"):
        DeadlineStatus(deadline=datetime(2026, 3, 18), business_date=date(2026, 3, 1))
