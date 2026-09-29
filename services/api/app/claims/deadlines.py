"""Appeal-deadline status relative to the business date. Date arithmetic lives in
code, never in a model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.contracts.fixtures import Claim


def _require_date(name: str, value: object) -> None:
    # datetime is a date subclass, so a clock.now() timestamp would otherwise pass for
    # the business date. The message names only the type, never the value.
    if type(value) is not date:
        raise TypeError(f"{name} must be a date, not {type(value).__name__}")


@dataclass(frozen=True)
class DeadlineStatus:
    deadline: date
    business_date: date

    def __post_init__(self) -> None:
        _require_date("deadline", self.deadline)
        _require_date("business_date", self.business_date)

    @property
    def days_remaining(self) -> int:
        return (self.deadline - self.business_date).days

    @property
    def passed(self) -> bool:
        return self.days_remaining < 0


def appeal_deadline_status(claim: Claim, business_date: date) -> DeadlineStatus | None:
    # Checked before the no-deadline return, so misuse fails for every claim, not only denied ones.
    _require_date("business_date", business_date)
    if claim.appeal_deadline is None:
        return None
    return DeadlineStatus(deadline=claim.appeal_deadline, business_date=business_date)
