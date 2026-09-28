"""Money formatting. Amounts stay Decimal from fixture to display; no floats."""

from decimal import Decimal

_CENT = Decimal("0.01")


def format_usd(amount: Decimal) -> str:
    """Formats whole cents as "$1,450.00". Refuses floats, negative amounts, and
    fractions of a cent instead of printing them, so the display always shows
    exactly the recorded amount."""
    if type(amount) is not Decimal or not amount.is_finite() or amount.is_signed():
        raise ValueError("expected a finite, non-negative Decimal")
    if amount.quantize(_CENT) != amount:
        raise ValueError("expected whole cents")
    return f"${amount:,.2f}"
