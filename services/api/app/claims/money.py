"""Money formatting. Amounts stay Decimal from fixture to display; no floats."""

from decimal import Decimal


def format_usd(amount: Decimal) -> str:
    """Formats whole cents as "$1,450.00". Refuses floats, negative amounts, and
    fractions of a cent instead of printing them, so the display always shows
    exactly the recorded amount. No Decimal arithmetic is done, so the caller's
    Decimal context cannot change the result."""
    if type(amount) is not Decimal or not amount.is_finite() or amount.is_signed():
        raise ValueError("expected a finite, non-negative Decimal")
    _, digits, exponent = amount.as_tuple()
    # Digits past the second decimal place must all be zero: 1.250 is whole cents, 0.125 is not.
    if exponent < -2 and any(digits[exponent + 2 :]):
        raise ValueError("expected whole cents")
    return f"${amount:,.2f}"
