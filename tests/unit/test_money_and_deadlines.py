from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.claims.deadlines import appeal_deadline_status
from app.claims.money import format_usd


def test_usd_formatting_keeps_cents_and_thousands():
    assert format_usd(Decimal("1450.00")) == "$1,450.00"
    assert format_usd(Decimal("0.00")) == "$0.00"
    assert format_usd(Decimal("3200.5")) == "$3,200.50"
    assert format_usd(Decimal("1234567.89")) == "$1,234,567.89"


@pytest.mark.parametrize(
    "amount",
    [Decimal("-5.00"), Decimal("-0.00"), Decimal("0.125"), Decimal("NaN"), Decimal("Infinity"), 1450.0, 1450],
    ids=["negative", "negative-zero", "fraction-of-a-cent", "nan", "infinity", "float", "int"],
)
def test_usd_formatting_accepts_only_non_negative_whole_cent_decimals(amount):
    with pytest.raises(ValueError):
        format_usd(amount)


def test_appeal_deadline_is_ahead_on_the_demo_date(store):
    status = appeal_deadline_status(store.claim("CL-2048"), date(2026, 3, 1))
    assert (status.days_remaining, status.passed) == (17, False)


def test_deadline_day_itself_is_still_open(store):
    status = appeal_deadline_status(store.claim("CL-2048"), date(2026, 3, 18))
    assert (status.days_remaining, status.passed) == (0, False)


def test_appeal_deadline_has_passed_on_the_real_date(store):
    status = appeal_deadline_status(store.claim("CL-2048"), date(2026, 9, 28))
    assert (status.days_remaining, status.passed) == (-194, True)


def test_claim_without_a_deadline_has_no_status(store):
    assert appeal_deadline_status(store.claim("CL-2011"), date(2026, 3, 1)) is None


def test_a_timestamp_is_not_accepted_as_the_business_date(store):
    with pytest.raises(TypeError, match="not timestamps"):
        appeal_deadline_status(store.claim("CL-2048"), datetime(2026, 3, 1, tzinfo=timezone.utc))
