from datetime import UTC, date, datetime, timedelta

import pytest

from app.clock import ClockConfigError, DemoClock, SystemClock, build_clock


def test_demo_mode_pins_the_business_date(policy):
    clock = build_clock("demo", policy)
    assert isinstance(clock, DemoClock)
    assert clock.business_date() == date(2026, 3, 1)


def test_demo_mode_accepts_a_business_date_override(policy):
    assert build_clock("demo", policy, "2026-09-28").business_date() == date(2026, 9, 28)


def test_demo_mode_can_use_the_real_calendar(policy):
    assert isinstance(build_clock("demo", policy, "today"), SystemClock)


def test_malformed_override_is_a_configuration_error(policy):
    with pytest.raises(ClockConfigError, match="not an ISO date"):
        build_clock("demo", policy, "March 1st")


@pytest.mark.parametrize("override", ["2026-03-01", "today"])
def test_production_mode_rejects_any_business_date_override(policy, override):
    with pytest.raises(ClockConfigError, match="not allowed in production"):
        build_clock("production", policy, override)


def test_production_mode_uses_the_system_clock(policy):
    assert isinstance(build_clock("production", policy), SystemClock)


def test_unknown_mode_is_rejected(policy):
    with pytest.raises(ClockConfigError, match="unknown APP_MODE"):
        build_clock("staging", policy)


def test_business_date_follows_the_business_time_zone(policy, monkeypatch):
    # 05:30 UTC on 2 March is still 1 March in Los Angeles.
    monkeypatch.setattr(SystemClock, "now", lambda self: datetime(2026, 3, 2, 5, 30, tzinfo=UTC))
    assert build_clock("production", policy).business_date() == date(2026, 3, 1)


@pytest.mark.parametrize(
    ("mode", "override"), [("demo", None), ("demo", "2026-09-28"), ("demo", "today"), ("production", None)]
)
def test_session_time_is_real_utc(policy, mode, override):
    now = build_clock(mode, policy, override).now()
    assert now.utcoffset() == timedelta(0)
    assert abs(now - datetime.now(UTC)) < timedelta(seconds=5)
