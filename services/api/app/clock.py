"""Time sources. Session expiry always uses real time; the demo overrides only the
business date used for claim deadlines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from app.policies import Policy


class Clock(Protocol):
    def now(self) -> datetime:
        """The current instant as an aware UTC datetime; drives session and verification expiry."""
        ...

    def business_date(self) -> date:
        """The only source of "today" for business rules such as appeal deadlines."""
        ...


@dataclass(frozen=True)
class SystemClock:
    timezone: ZoneInfo

    def now(self) -> datetime:
        return datetime.now(UTC)

    def business_date(self) -> date:
        return self.now().astimezone(self.timezone).date()


@dataclass(frozen=True)
class DemoClock:
    fixed_business_date: date

    def now(self) -> datetime:
        return datetime.now(UTC)

    def business_date(self) -> date:
        return self.fixed_business_date


class ClockConfigError(RuntimeError):
    pass


def build_clock(app_mode: str, policy: Policy, business_date_override: str | None = None) -> Clock:
    timezone = ZoneInfo(policy.business.timezone)
    if app_mode == "production":
        if business_date_override is not None:
            raise ClockConfigError("a business-date override is not allowed in production mode")
        return SystemClock(timezone)
    if app_mode == "demo":
        if business_date_override == "today":
            return SystemClock(timezone)
        if business_date_override is not None:
            try:
                return DemoClock(date.fromisoformat(business_date_override))
            except ValueError:
                raise ClockConfigError(
                    f"business-date override {business_date_override!r} is not an ISO date; "
                    "expected YYYY-MM-DD or 'today'"
                ) from None
        return DemoClock(policy.demo.business_date)
    raise ClockConfigError(f"unknown APP_MODE {app_mode!r}; expected 'demo' or 'production'")
