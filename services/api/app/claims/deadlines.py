"""Appeal-deadline status relative to the business date. Date arithmetic lives in
code, never in a model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.contracts.fixtures import Claim


@dataclass(frozen=True)
class DeadlineStatus:
    deadline: date
    business_date: date

    def __post_init__(self) -> None:
        # datetime is a date subclass. Rejecting it here makes a clock.now() timestamp
        # fail at once rather than when days_remaining is first read.
        if type(self.deadline) is not date or type(self.business_date) is not date:
            raise TypeError("deadline and business_date must be dates, not timestamps")

    @property
    def days_remaining(self) -> int:
        return (self.deadline - self.business_date).days

    @property
    def passed(self) -> bool:
        return self.days_remaining < 0


def appeal_deadline_status(claim: Claim, business_date: date) -> DeadlineStatus | None:
    if claim.appeal_deadline is None:
        return None
    return DeadlineStatus(deadline=claim.appeal_deadline, business_date=business_date)
