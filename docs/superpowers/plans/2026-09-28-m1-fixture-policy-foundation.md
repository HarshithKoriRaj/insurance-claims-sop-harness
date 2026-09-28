# Milestone 1: Fixture and Policy Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the tested, offline foundation of the SOP harness: strict fixture contracts, a read-only fixture importer, document codes, approved-guidance rendering, money and deadline handling, versioned policy defaults, the clock, and identity-value normalization.

**Architecture:** A Python package `app` under `services/api/`, following the layout in `docs/2026-09-28-sop-harness-plan.md`. Everything in this milestone is pure and deterministic: no model, database, or network. Policy values live in `policies/*.toml`. Fixtures are validated but never modified.

**Tech Stack:** Python 3.13, uv, Pydantic 2, pytest, stdlib `tomllib` and `zoneinfo`.

**Scope:** Milestone 1 of the architecture plan's delivery sequence. Its acceptance gate: all six fixtures validate; document aliases resolve; date and Decimal behavior tested; national ID cannot count as SSN; original fixtures unchanged. Verification decisions and receipts (Milestone 3), the workflow kernel (Milestone 2), tools, API, AI, email, and UI each get their own plan.

---

## File structure

| Path | Responsibility |
|---|---|
| `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore` | Python project, pinned dependencies, ignored files |
| `policies/defaults.toml` | Versioned demo defaults (limits, expiry, phone, demo business date) |
| `policies/document_codes.toml` | Every fixture document label mapped to one document code |
| `services/api/app/__init__.py` | Backend package marker |
| `services/api/app/policies.py` | Loads and validates `policies/defaults.toml`; defines `IdentityField` |
| `services/api/app/clock.py` | Real session time plus a demo-overridable business date |
| `services/api/app/contracts/fixtures.py` | Strict Pydantic schemas for the six fixture files |
| `services/api/app/claims/documents.py` | Document catalog: label → code |
| `services/api/app/claims/importer.py` | Read-only fixture loading, cross-file reference checks, claim content versions |
| `services/api/app/claims/money.py` | USD formatting from `Decimal` |
| `services/api/app/claims/deadlines.py` | Appeal-deadline status against the business date |
| `services/api/app/claims/guidance.py` | Approved guidance snippets with provenance; follow-up template rendering |
| `services/api/app/identity/normalize.py` | Deterministic normalization of caller identity values |
| `services/api/app/identity/fields.py` | Normalized values a policyholder record holds per permitted field |
| `tests/conftest.py` | Shared paths and fixtures (`policy`, `catalog`, `store`, `fixture_copy`) |
| `tests/unit/test_*.py` | One test module per unit above |

Run every command from the repository root: `/Users/harshithkoriraj/Downloads/apps/insurance_claims`.

---

### Task 1: Repository and project scaffold

**Files:**
- Create: `.gitignore`, `.python-version`, `pyproject.toml`, `services/api/app/__init__.py`, `tests/conftest.py`, `tests/unit/test_scaffold.py`, `tests/unit/test_fixture_integrity.py`

- [ ] **Step 1: Initialize git and commit the supplied material on `main`**

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.hypothesis/
.env
.env.*
!.env.example
node_modules/
dist/
build/
.DS_Store
```

```bash
git init -b main
git add .gitignore fixtures docs
git commit -m "chore: import supplied fixtures and design docs"
git switch -c m1-foundation
```

Expected: a root commit on `main`, then `Switched to a new branch 'm1-foundation'`.

- [ ] **Step 2: Create the Python project**

`.python-version`:

```text
3.13
```

`pyproject.toml`:

```toml
[project]
name = "insurance-claims-sop"
version = "0.1.0"
description = "SOP harness for an insurance claims support agent"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9,<3",
    "tzdata>=2024.1",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["services/api"]
addopts = "-ra"
```

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`; installs pydantic, tzdata, pytest.

- [ ] **Step 3: Write the failing smoke test and shared test paths**

`tests/conftest.py`:

```python
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return ROOT / "fixtures"


@pytest.fixture(scope="session")
def policies_dir() -> Path:
    return ROOT / "policies"


@dataclass
class FixtureCopy:
    """A writable copy of the fixture directory, for tests that need bad data."""

    path: Path

    def edit(self, name: str, change: Callable[[Any], None]) -> None:
        file = self.path / name
        data = json.loads(file.read_text(encoding="utf-8"))
        change(data)
        file.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def fixture_copy(tmp_path: Path, fixtures_dir: Path) -> FixtureCopy:
    target = tmp_path / "fixtures"
    shutil.copytree(fixtures_dir, target)
    return FixtureCopy(target)
```

`tests/unit/test_scaffold.py`:

```python
import app


def test_backend_package_is_importable():
    assert app.__doc__ == "Insurance claims SOP harness backend."
```

- [ ] **Step 4: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 5: Create the package**

`services/api/app/__init__.py`:

```python
"""Insurance claims SOP harness backend."""
```

- [ ] **Step 6: Run it to verify it passes**

Run: `uv run pytest tests/unit/test_scaffold.py -v`
Expected: PASS

- [ ] **Step 7: Add the fixture-integrity guard**

`tests/unit/test_fixture_integrity.py`:

```python
"""The supplied fixtures are read-only inputs. These are the SHA-256 hashes of the
files as delivered; a mismatch means a fixture was edited instead of the policy overlay."""

import hashlib

DELIVERED_SHA256 = {
    "claim_schema.json": "f95f0b49b4522e56b4b65dbdf4d74204b348bf43a333920a07d8d6589969ec4a",
    "claims.json": "16466e43f33eb7fb4f8aa0a3120f5e636ff38e337fc2673ee5aacdd9deaad76f",
    "consent_scenarios.json": "e1c49b14f21d7f956042f0737a4f5b9c2b09f63e5b4abfbe203df089cd678304",
    "policyholders.json": "7eb92602a256cabe628ddbe31d739609ebf00d9672e327f73ff31ae9bee1189c",
    "representatives.json": "ebc55c04c068a762e3596048fef0ebfeef21b19f595b64e0bdd64cc2c26c8b34",
    "required_document_guideline.json": "bc5425b0970c6e4c4c64b262f1c3c0020287e3e9adc437034c2f96fa6ff36c4b",
}


def test_fixture_files_are_unchanged(fixtures_dir):
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(fixtures_dir.glob("*.json"))
    }
    assert actual == DELIVERED_SHA256
```

Run: `uv run pytest tests/unit/test_fixture_integrity.py -v`
Expected: PASS. This test guards the delivered files; it has no implementation step.

- [ ] **Step 8: Commit**

```bash
git add .python-version pyproject.toml uv.lock services tests
git commit -m "chore: scaffold Python project and guard the supplied fixtures"
```

---

### Task 2: Policy defaults

**Files:**
- Create: `policies/defaults.toml`, `services/api/app/policies.py`, `tests/unit/test_policies.py`
- Modify: `tests/conftest.py` (append the `policy` fixture)

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_policies.py`:

```python
from datetime import date

import pytest
from pydantic import ValidationError

from app.policies import load_policy


def _write_variant(policies_dir, tmp_path, old, new):
    text = (policies_dir / "defaults.toml").read_text()
    assert old in text, f"test setup: {old!r} not found in defaults.toml"
    path = tmp_path / "defaults.toml"
    path.write_text(text.replace(old, new))
    return path


def test_defaults_match_the_architecture_plan(policies_dir):
    policy = load_policy(policies_dir / "defaults.toml")
    assert policy.version == "2026-09-28"
    assert policy.verification.required_matching_fields == 3
    assert policy.verification.max_failed_submissions == 3
    assert policy.verification.idle_expiry_minutes == 30
    assert policy.verification.permitted_fields == ("full_name", "dob", "phone", "email", "ssn_last4")
    assert policy.session.max_age_hours == 8
    assert policy.session.max_input_characters == 8000
    assert policy.session.recent_turns == 12
    assert policy.session.max_turns == 60
    assert policy.recovery.unrelated_offer_human_at == 2
    assert policy.recovery.unrelated_stop_at == 3
    assert policy.recovery.refusal_stop_at == 2
    assert policy.claims.fact_max_age_minutes == 5
    assert policy.phone.default_country_calling_code == "1"
    assert policy.phone.national_number_length == 10
    assert policy.business.timezone == "America/Los_Angeles"
    assert policy.demo.business_date == date(2026, 3, 1)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("fact_max_age_minutes = 5", "fact_max_age_minutes = 5\n\n[surprise]\nkey = 1"),
        ("max_failed_submissions = 3", "max_failed_submissions = 3\nsurprise = 1"),
    ],
    ids=["top-level-table", "nested-key"],
)
def test_unknown_keys_are_rejected(policies_dir, tmp_path, old, new):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_policy(_write_variant(policies_dir, tmp_path, old, new))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("required_matching_fields = 3", "required_matching_fields = 2", "greater than or equal to 3"),
        ("required_matching_fields = 3", "required_matching_fields = true", "greater than or equal to 3"),
        ("required_matching_fields = 3", "required_matching_fields = 6", "exceeds the number of permitted fields"),
        (
            'permitted_fields = ["full_name", "dob", "phone", "email", "ssn_last4"]',
            'permitted_fields = ["dob", "dob", "dob"]',
            "must not repeat",
        ),
        ('"ssn_last4"]', '"ssn_last4", "national_id_last4"]', "permitted_fields"),
        ("unrelated_offer_human_at = 2", "unrelated_offer_human_at = 3", "must come before"),
        ("recent_turns = 12", "recent_turns = 61", "cannot exceed max_turns"),
        (
            'default_country_calling_code = "1"\nnational_number_length = 10',
            'default_country_calling_code = "999"\nnational_number_length = 14',
            "exceeds 15 digits",
        ),
        ('timezone = "America/Los_Angeles"', 'timezone = "america/los_angeles"', "unknown IANA time zone"),
        ('version = "2026-09-28"', 'version = ""', "at least 1 character"),
    ],
    ids=[
        "below-three-fields",
        "boolean-threshold",
        "more-fields-than-permitted",
        "repeated-field",
        "national-id-field",
        "offer-after-stop",
        "recent-exceeds-max-turns",
        "phone-longer-than-e164",
        "timezone-wrong-case",
        "empty-version",
    ],
)
def test_unsafe_or_incoherent_settings_are_rejected(policies_dir, tmp_path, old, new, message):
    with pytest.raises(ValidationError, match=message):
        load_policy(_write_variant(policies_dir, tmp_path, old, new))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_policies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.policies'`

- [ ] **Step 3: Write the policy file and loader**

`policies/defaults.toml`:

```toml
# Proposed, configurable demo defaults from docs/2026-09-28-sop-harness-plan.md.
# These are not insurer policy; production values need insurer approval.
version = "2026-09-28"

[verification]
# The architecture requires at least three distinct permitted fields; the loader rejects fewer.
required_matching_fields = 3
max_failed_submissions = 3
idle_expiry_minutes = 30
permitted_fields = ["full_name", "dob", "phone", "email", "ssn_last4"]

[session]
max_age_hours = 8
max_input_characters = 8000
recent_turns = 12
max_turns = 60

[recovery]
# Consecutive unrelated requests: the 2nd offers a human, the 3rd stops answering them.
unrelated_offer_human_at = 2
unrelated_stop_at = 3
# Persuasion stops at the 2nd explicit refusal to continue verification.
refusal_stop_at = 2

[claims]
fact_max_age_minutes = 5

[phone]
# Applied only to national-length numbers given without a country code.
default_country_calling_code = "1"
national_number_length = 10

[business]
# Used in every mode for business dates such as appeal deadlines.
timezone = "America/Los_Angeles"

[demo]
# Demo mode pins the business date; production mode rejects any override.
business_date = 2026-03-01
```

`services/api/app/policies.py`:

```python
"""Loads the explicit, versioned defaults in policies/defaults.toml."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Literal, Self
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IdentityField = Literal["full_name", "dob", "phone", "email", "ssn_last4"]

MIN_MATCHING_FIELDS = 3  # Non-negotiable invariant 2 in docs/2026-09-28-sop-harness-plan.md.
E164_MAX_DIGITS = 15


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VerificationPolicy(_Strict):
    required_matching_fields: int = Field(ge=MIN_MATCHING_FIELDS)
    max_failed_submissions: int = Field(ge=1)
    idle_expiry_minutes: int = Field(ge=1)
    permitted_fields: tuple[IdentityField, ...]

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if len(set(self.permitted_fields)) != len(self.permitted_fields):
            raise ValueError("permitted_fields must not repeat a field")
        if self.required_matching_fields > len(self.permitted_fields):
            raise ValueError("required_matching_fields exceeds the number of permitted fields")
        return self


class SessionPolicy(_Strict):
    max_age_hours: int = Field(ge=1)
    max_input_characters: int = Field(ge=1)
    recent_turns: int = Field(ge=1)
    max_turns: int = Field(ge=1)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.recent_turns > self.max_turns:
            raise ValueError("recent_turns cannot exceed max_turns")
        return self


class RecoveryPolicy(_Strict):
    unrelated_offer_human_at: int = Field(ge=1)
    unrelated_stop_at: int = Field(ge=1)
    refusal_stop_at: int = Field(ge=1)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.unrelated_offer_human_at >= self.unrelated_stop_at:
            raise ValueError("unrelated_offer_human_at must come before unrelated_stop_at")
        return self


class ClaimsPolicy(_Strict):
    fact_max_age_minutes: int = Field(ge=1)


class PhonePolicy(_Strict):
    default_country_calling_code: str = Field(pattern=r"^[1-9]\d{0,2}$")
    national_number_length: int = Field(ge=4, le=14)

    @model_validator(mode="after")
    def _fits_e164(self) -> Self:
        if len(self.default_country_calling_code) + self.national_number_length > E164_MAX_DIGITS:
            raise ValueError(f"country code plus national number exceeds {E164_MAX_DIGITS} digits")
        return self


class BusinessPolicy(_Strict):
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        # Exact IANA names only: a case-insensitive filesystem would accept "america/los_angeles".
        if value not in available_timezones():
            raise ValueError(f"unknown IANA time zone {value!r}")
        return value


class DemoPolicy(_Strict):
    business_date: date


class Policy(_Strict):
    version: str = Field(min_length=1)
    verification: VerificationPolicy
    session: SessionPolicy
    recovery: RecoveryPolicy
    claims: ClaimsPolicy
    phone: PhonePolicy
    business: BusinessPolicy
    demo: DemoPolicy


def load_policy(path: Path) -> Policy:
    with path.open("rb") as handle:
        return Policy.model_validate(tomllib.load(handle))
```

Append to `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def policy(policies_dir):
    from app.policies import load_policy

    return load_policy(policies_dir / "defaults.toml")
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_policies.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add policies/defaults.toml services/api/app/policies.py tests
git commit -m "feat: load versioned policy defaults"
```

---

### Task 3: Clock

**Files:**
- Create: `services/api/app/clock.py`, `tests/unit/test_clock.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_clock.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_clock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.clock'`

- [ ] **Step 3: Implement the clock**

`services/api/app/clock.py`:

```python
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
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_clock.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/clock.py tests/unit/test_clock.py
git commit -m "feat: add clock with demo business-date override"
```

---

### Task 4: Fixture contracts

**Files:**
- Create: `services/api/app/contracts/__init__.py`, `services/api/app/contracts/fixtures.py`, `tests/unit/test_fixture_contracts.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_fixture_contracts.py`:

```python
import json
from datetime import date
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.fixtures import (
    Claim,
    ClaimSchemaDoc,
    ConsentScenario,
    DocumentGuideline,
    Policyholder,
    Representative,
)

VALID_CLAIM = {
    "case_id": "CL-1",
    "party_id": "P1",
    "case_type": "healthcare",
    "created_at": "2026-01-01",
    "status": "open",
    "summary": "test",
    "expected_reimbursement_amount": "1.00",
    "allowed_max_amount": "1.00",
    "net_pay": "0.00",
    "net_fee": "1.00",
}

VALID_HOLDER = {
    "party_id": "P1",
    "name": "Test Person",
    "policy_number": "POL-1",
    "dob": "1990-01-01",
    "id_type": "ssn_last4",
    "id_last4": "0042",
    "phone": "+16500000000",
    "email": "test@example.com",
}


def _read(fixtures_dir, name):
    return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))


def test_policyholders_validate(fixtures_dir):
    holders = TypeAdapter(tuple[Policyholder, ...]).validate_python(_read(fixtures_dir, "policyholders.json"))
    assert [h.party_id for h in holders] == ["P9", "P7", "P12", "P13"]
    assert holders[0].dob == date(1985, 3, 15)
    assert (holders[0].id_type, holders[0].id_last4) == ("ssn_last4", "4472")
    assert holders[2].id_type == "national_id_last4"
    assert holders[3].name_aliases == ("Yaven Li",)


def test_claims_validate_with_decimal_money_and_real_dates(fixtures_dir):
    claims = TypeAdapter(tuple[Claim, ...]).validate_python(_read(fixtures_dir, "claims.json"))
    denied = next(c for c in claims if c.case_id == "CL-2048")
    assert denied.allowed_max_amount == Decimal("1450.00")
    assert isinstance(denied.net_pay, Decimal)
    assert denied.appeal_deadline == date(2026, 3, 18)
    assert denied.documents_needed == ("pathology report", "office note")


def test_remaining_fixture_files_validate(fixtures_dir):
    ClaimSchemaDoc.model_validate(_read(fixtures_dir, "claim_schema.json"))
    TypeAdapter(dict[str, ConsentScenario]).validate_python(_read(fixtures_dir, "consent_scenarios.json"))
    TypeAdapter(tuple[Representative, ...]).validate_python(_read(fixtures_dir, "representatives.json"))
    DocumentGuideline.model_validate(_read(fixtures_dir, "required_document_guideline.json"))


@pytest.mark.parametrize(
    "bad",
    [
        1450.0,
        "1450",
        "1,450.00",
        "abc",
        "-1.00",
        "١٤٥٠.٠٠",
        Decimal("1450.5"),
        Decimal("-1.00"),
        Decimal("-0.00"),
        Decimal("NaN"),
    ],
)
def test_money_must_be_a_two_place_decimal_string(bad):
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "net_pay": bad})


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "surprise": True})


def test_unknown_keys_are_rejected_in_nested_models(fixtures_dir):
    guideline = _read(fixtures_dir, "required_document_guideline.json")
    guideline["claim_followup_settings"]["surprise"] = {"en": "x"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DocumentGuideline.model_validate(guideline)


def test_id_last4_keeps_leading_zeros():
    assert Policyholder.model_validate(VALID_HOLDER).id_last4 == "0042"


def test_id_last4_must_be_a_four_digit_string():
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, "id_last4": 4472})


@pytest.mark.parametrize(("field", "value"), [("email", "not-an-email"), ("email_aliases", ["a@b"])])
def test_emails_on_file_must_be_addresses(field, value):
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, field: value})


@pytest.mark.parametrize("bad", ["1773792000", 0, "1985-03-15T00:00:00", "03/15/1985", "٢٠٢٦-٠٣-١٨"])
def test_dates_must_be_iso_strings(bad):
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "created_at": bad})


@pytest.mark.parametrize(("field", "value"), [("id_last4", "٠٠٤٢"), ("phone", "+１６５００００００００")])
def test_only_ascii_digits_are_accepted(field, value):
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, field: value})


def test_models_round_trip_through_python_values(fixtures_dir):
    claims = TypeAdapter(tuple[Claim, ...]).validate_python(_read(fixtures_dir, "claims.json"))
    holders = TypeAdapter(tuple[Policyholder, ...]).validate_python(_read(fixtures_dir, "policyholders.json"))
    for record in (*claims, *holders):
        assert type(record).model_validate(record.model_dump()) == record


def test_a_denied_claim_without_a_reason_still_loads():
    claim = Claim.model_validate({**VALID_CLAIM, "status": "denied"})
    assert (claim.denial_reason, claim.appeal_deadline, claim.documents_needed) == (None, None, ())


def test_requires_documents_must_be_a_real_boolean(fixtures_dir):
    guideline = _read(fixtures_dir, "required_document_guideline.json")
    guideline["claim_followup_guidance"][0]["requires_documents"] = "no"
    with pytest.raises(ValidationError):
        DocumentGuideline.model_validate(guideline)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Policyholder, {**VALID_HOLDER, "id_type": "passport_last4"}),
        (Policyholder, {**VALID_HOLDER, "party_id": ""}),
        (ConsentScenario, {"status_sequence": []}),
        (Claim, {**VALID_CLAIM, "status": "denied", "denial_reason": ""}),
    ],
    ids=["unknown-id-type", "empty-party-id", "empty-consent-sequence", "empty-denial-reason"],
)
def test_other_invalid_records_are_rejected(model, data):
    with pytest.raises(ValidationError):
        model.model_validate(data)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_fixture_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.contracts'`

- [ ] **Step 3: Implement the contracts**

`services/api/app/contracts/__init__.py`:

```python
"""Typed contracts shared across the backend."""
```

`services/api/app/contracts/fixtures.py`:

```python
"""Strict schemas for the six supplied fixture files. Unknown keys are rejected, so
a changed fixture fails loudly instead of being partly read. Frozen models block
attribute assignment; their dicts are shared and must be treated as read-only."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StringConstraints

_MONEY = re.compile(r"^[0-9]+\.[0-9]{2}$")
_ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _money(value: object) -> Decimal:
    """Two-place decimal strings from JSON, or an equivalent Decimal on round trips. Never floats."""
    if isinstance(value, Decimal):
        if value.is_finite() and not value.is_signed() and value.as_tuple().exponent == -2:
            return value
    elif isinstance(value, str) and _MONEY.fullmatch(value):
        return Decimal(value)
    raise ValueError("money must be a decimal string with two places, such as '1450.00'")


def _iso_date(value: object) -> date:
    """ISO date strings, or a date (not a datetime) on round trips. Never timestamps."""
    if type(value) is date:
        return value
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        return date.fromisoformat(value)
    raise ValueError("date must be an ISO string such as '2026-03-18'")


Money = Annotated[Decimal, BeforeValidator(_money)]
IsoDate = Annotated[date, BeforeValidator(_iso_date)]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]
E164 = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{7,14}$")]
Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Last4 = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")]
CaseType = Literal["healthcare", "dental", "auto"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Policyholder(_Strict):
    party_id: NonEmpty
    name: NonEmpty
    name_aliases: tuple[NonEmpty, ...] = ()
    policy_number: NonEmpty
    dob: IsoDate
    id_type: Literal["ssn_last4", "national_id_last4"]
    id_last4: Last4
    phone: E164
    phone_aliases: tuple[E164, ...] = ()
    email: Email
    email_aliases: tuple[Email, ...] = ()


class Claim(_Strict):
    case_id: NonEmpty
    party_id: NonEmpty
    case_type: CaseType
    created_at: IsoDate
    status: Literal["denied", "closed", "open"]
    summary: NonEmpty
    denial_reason: NonEmpty | None = None
    documents_needed: tuple[NonEmpty, ...] = ()
    appeal_deadline: IsoDate | None = None
    expected_reimbursement_amount: Money
    allowed_max_amount: Money
    net_pay: Money
    net_fee: Money


class FieldDescription(_Strict):
    type: str
    example: str
    description: str


class ClaimSchemaDoc(_Strict):
    notes: tuple[str, ...]
    field_descriptions: dict[str, FieldDescription]


class ConsentScenario(_Strict):
    status_sequence: tuple[Literal["pending", "approved", "denied", "revoked"], ...] = Field(min_length=1)


class Representative(_Strict):
    rep_name: NonEmpty
    relationship: NonEmpty
    buyer_name: NonEmpty
    buyer_party_id: NonEmpty


class LocalizedText(_Strict):
    en: str


class FollowupRule(_Strict):
    topic: NonEmpty
    intent_hints: tuple[str, ...]
    requires_documents: StrictBool
    match_any: tuple[str, ...] = ()
    en: str


class FollowupSettings(_Strict):
    average_processing_time_after_submission: LocalizedText
    human_review_after_document_alternatives_exhausted: LocalizedText


class DocumentGuideline(_Strict):
    default_guidance: LocalizedText
    case_type_guidance: dict[CaseType, LocalizedText]
    document_guidance: dict[str, LocalizedText]
    document_alternative_guidance: dict[str, LocalizedText]
    claim_followup_settings: FollowupSettings
    claim_followup_guidance: tuple[FollowupRule, ...]
    claim_followup_fallback: LocalizedText
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_fixture_contracts.py -v`
Expected: PASS (33 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/contracts tests/unit/test_fixture_contracts.py
git commit -m "feat: add strict schemas for the supplied fixtures"
```

---

### Task 5: Document catalog

**Files:**
- Create: `policies/document_codes.toml`, `services/api/app/claims/__init__.py`, `services/api/app/claims/documents.py`, `tests/unit/test_documents.py`
- Modify: `tests/conftest.py` (append the `catalog` fixture)

- [ ] **Step 1: Write the failing tests**

Append to `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def catalog(policies_dir):
    from app.claims.documents import load_document_catalog

    return load_document_catalog(policies_dir / "document_codes.toml")
```

`tests/unit/test_documents.py`:

```python
import pytest
from pydantic import ValidationError

from app.claims.documents import UnknownDocumentLabel, load_document_catalog


@pytest.mark.parametrize(
    ("label", "code"),
    [
        ("pathology report", "PATHOLOGY_REPORT"),
        ("original pathology report", "PATHOLOGY_REPORT"),
        ("office note", "PROVIDER_OFFICE_NOTE"),
        ("treating provider office note", "PROVIDER_OFFICE_NOTE"),
        ("diagnosis report", "DIAGNOSIS_REPORT"),
        ("repair estimate", "REPAIR_ESTIMATE"),
        ("supplemental accident scene photos", "ACCIDENT_SCENE_PHOTOS"),
    ],
)
def test_every_fixture_label_maps_to_its_code(catalog, label, code):
    assert catalog.code_for(label) == code


def test_catalog_version(catalog):
    assert catalog.version == "2026-09-28"


def test_labels_ignore_case_and_extra_spaces(catalog):
    assert catalog.code_for("  Pathology   REPORT ") == "PATHOLOGY_REPORT"


@pytest.mark.parametrize("label", ["x-ray", "   ", ""])
def test_unknown_or_blank_label_fails_closed(catalog, label):
    with pytest.raises(UnknownDocumentLabel):
        catalog.code_for(label)


def test_the_mapping_is_read_only(catalog):
    with pytest.raises(TypeError):
        catalog.label_to_code["x-ray"] = "PATHOLOGY_REPORT"


def test_a_label_cannot_map_to_two_codes(tmp_path):
    path = tmp_path / "codes.toml"
    path.write_text('version = "t"\n[codes.A]\nlabels = ["note"]\n[codes.B]\nlabels = ["Note"]\n')
    with pytest.raises(ValueError, match="maps to both"):
        load_document_catalog(path)


@pytest.mark.parametrize(
    "text",
    [
        '[codes.A]\nlabels = ["note"]\n',
        'version = ""\n[codes.A]\nlabels = ["note"]\n',
        'version = 2026-09-28\n[codes.A]\nlabels = ["note"]\n',
        'version = "t"\n',
        'version = "t"\ncodes = 1\n',
        'version = "t"\n[codes.A]\n',
        'version = "t"\n[codes.A]\nlabels = []\n',
        'version = "t"\n[codes.A]\nlabels = ["   "]\n',
        'version = "t"\n[codes.A]\nlabels = "note"\n',
        'version = "t"\n[codes.A]\nlabels = [1]\n',
        'version = "t"\n[codes."pathology report"]\nlabels = ["note"]\n',
        'version = "t"\n[codes.A]\nlabels = ["note"]\nsurprise = 1\n',
        'version = "t"\nsurprise = 1\n[codes.A]\nlabels = ["note"]\n',
    ],
    ids=[
        "missing-version",
        "empty-version",
        "date-version",
        "missing-codes",
        "codes-not-a-table",
        "missing-labels",
        "no-labels",
        "blank-label",
        "labels-not-a-list",
        "label-not-a-string",
        "code-not-an-identifier",
        "unknown-entry-key",
        "unknown-top-level-key",
    ],
)
def test_malformed_catalog_files_are_rejected(tmp_path, text):
    path = tmp_path / "codes.toml"
    path.write_text(text)
    with pytest.raises(ValidationError):
        load_document_catalog(path)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_documents.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.claims'`

- [ ] **Step 3: Write the catalog and loader**

`policies/document_codes.toml`:

```toml
# Every document label used in the fixtures, from claims and from guidance keys,
# mapped to one document code. Callers see the claim's own label as the document's
# name, so a guidance key's "original" never becomes a stated requirement; approved
# guidance text may still mention an original conditionally.
version = "2026-09-28"

[codes.PATHOLOGY_REPORT]
labels = ["pathology report", "original pathology report"]

[codes.PROVIDER_OFFICE_NOTE]
labels = ["office note", "treating provider office note"]

[codes.DIAGNOSIS_REPORT]
labels = ["diagnosis report"]

[codes.REPAIR_ESTIMATE]
labels = ["repair estimate"]

[codes.ACCIDENT_SCENE_PHOTOS]
labels = ["supplemental accident scene photos"]
```

`services/api/app/claims/__init__.py`:

```python
"""Claim data, document codes, and approved guidance."""
```

`services/api/app/claims/documents.py`:

```python
"""Maps document labels from claims and guidance onto shared document codes."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]


class UnknownDocumentLabel(KeyError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _CodeEntry(_Strict):
    labels: tuple[Label, ...] = Field(min_length=1)


class _CatalogFile(_Strict):
    version: str = Field(min_length=1)
    codes: dict[Code, _CodeEntry] = Field(min_length=1)


def normalize_label(label: str) -> str:
    return " ".join(label.casefold().split())


@dataclass(frozen=True)
class DocumentCatalog:
    version: str
    label_to_code: Mapping[str, str]

    def code_for(self, label: str) -> str:
        try:
            return self.label_to_code[normalize_label(label)]
        except KeyError:
            raise UnknownDocumentLabel(label) from None


def load_document_catalog(path: Path) -> DocumentCatalog:
    with path.open("rb") as handle:
        parsed = _CatalogFile.model_validate(tomllib.load(handle))
    label_to_code: dict[str, str] = {}
    for code, entry in parsed.codes.items():
        for label in entry.labels:
            key = normalize_label(label)
            if key in label_to_code:
                raise ValueError(f"document label {label!r} maps to both {label_to_code[key]} and {code}")
            label_to_code[key] = code
    return DocumentCatalog(version=parsed.version, label_to_code=MappingProxyType(label_to_code))
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_documents.py -v`
Expected: PASS (27 tests)

- [ ] **Step 5: Commit**

```bash
git add policies/document_codes.toml services/api/app/claims tests
git commit -m "feat: map fixture document labels to shared codes"
```

---

### Task 6: Fixture importer

**Files:**
- Create: `services/api/app/claims/importer.py`, `tests/unit/test_importer.py`
- Modify: `tests/conftest.py` (append the `store` fixture)

- [ ] **Step 1: Write the failing tests**

Append to `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def store(fixtures_dir, catalog):
    from app.claims.importer import load_fixtures

    return load_fixtures(fixtures_dir, catalog)
```

`tests/unit/test_importer.py`:

```python
import hashlib

import pytest

from app.claims.importer import FixtureError, load_fixtures


def _hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob("*.json")}


def test_store_holds_every_fixture_record(store):
    assert len(store.policyholders) == 4
    assert len(store.claims) == 5
    assert len(store.representatives) == 1
    assert set(store.consent_scenarios) == {"default", "timeout"}


def test_claims_are_indexed_by_owner(store):
    assert [c.case_id for c in store.claims_for_party("P9")] == ["CL-2048", "CL-2011", "CL-1899", "CL-2102"]
    assert [c.case_id for c in store.claims_for_party("P12")] == ["CL-3001"]
    assert store.claims_for_party("P7") == ()
    assert store.claims_for_party("P13") == ()


def test_lookups_return_none_for_unknown_ids(store):
    assert store.claim("CL-9999") is None
    assert store.policyholder("P99") is None


def test_store_mappings_are_read_only(store):
    with pytest.raises(TypeError):
        store.claim_versions["CL-2048"] = "tampered"
    with pytest.raises(TypeError):
        store.consent_scenarios["surprise"] = store.consent_scenarios["default"]


def test_claim_versions_are_stable_content_hashes(store, fixtures_dir, catalog):
    assert load_fixtures(fixtures_dir, catalog).claim_versions == store.claim_versions
    assert len(set(store.claim_versions.values())) == 5


def test_a_changed_claim_gets_a_new_version(store, fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims[0].update(status="open"))
    changed = load_fixtures(fixture_copy.path, catalog).claim_versions
    assert changed["CL-2048"] != store.claim_versions["CL-2048"]
    assert changed["CL-2011"] == store.claim_versions["CL-2011"]


def test_loading_leaves_fixture_files_untouched(fixtures_dir, catalog):
    before = _hashes(fixtures_dir)
    load_fixtures(fixtures_dir, catalog)
    assert _hashes(fixtures_dir) == before


def test_claim_owned_by_an_unknown_party_is_rejected(fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims[0].update(party_id="P99"))
    with pytest.raises(FixtureError, match="unknown party P99"):
        load_fixtures(fixture_copy.path, catalog)


def test_representative_must_name_their_policyholder(fixture_copy, catalog):
    fixture_copy.edit("representatives.json", lambda reps: reps[0].update(buyer_name="Someone Else"))
    with pytest.raises(FixtureError, match="does not match a policyholder"):
        load_fixtures(fixture_copy.path, catalog)


def test_document_label_without_a_code_is_rejected(fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims[0].update(documents_needed=["x-ray"]))
    with pytest.raises(FixtureError, match="'x-ray' has no document code"):
        load_fixtures(fixture_copy.path, catalog)


def test_invalid_file_is_named_in_the_error(fixture_copy, catalog):
    fixture_copy.edit(
        "consent_scenarios.json", lambda scenarios: scenarios.update(surprise={"status_sequence": ["maybe"]})
    )
    with pytest.raises(FixtureError, match="consent_scenarios.json"):
        load_fixtures(fixture_copy.path, catalog)


def test_duplicate_case_ids_are_rejected(fixture_copy, catalog):
    fixture_copy.edit("claims.json", lambda claims: claims.append(dict(claims[0])))
    with pytest.raises(FixtureError, match="duplicate case_id: CL-2048"):
        load_fixtures(fixture_copy.path, catalog)


def test_duplicate_followup_topics_are_rejected(fixture_copy, catalog):
    def duplicate_topic(guideline):
        rules = guideline["claim_followup_guidance"]
        rules[1]["topic"] = rules[0]["topic"]

    fixture_copy.edit("required_document_guideline.json", duplicate_topic)
    with pytest.raises(FixtureError, match="duplicate follow-up topic: missing_required_material_alternatives"):
        load_fixtures(fixture_copy.path, catalog)


def test_validation_errors_do_not_echo_record_values(fixture_copy, catalog):
    fixture_copy.edit("policyholders.json", lambda holders: holders[0].update(id_last4="44720"))
    with pytest.raises(FixtureError) as caught:
        load_fixtures(fixture_copy.path, catalog)
    message = str(caught.value)
    assert "policyholders.json" in message and "id_last4" in message
    assert "44720" not in message
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_reference_errors_do_not_echo_names(fixture_copy, catalog):
    fixture_copy.edit("representatives.json", lambda reps: reps[0].update(buyer_party_id="P99"))
    with pytest.raises(FixtureError, match=r"\[0\] buyer does not match a policyholder \(P99\)") as caught:
        load_fixtures(fixture_copy.path, catalog)
    assert "Chen" not in str(caught.value)


def test_duplicate_policy_numbers_name_the_parties_not_the_number(fixture_copy, catalog):
    fixture_copy.edit("policyholders.json", lambda holders: holders[1].update(policy_number="POL-9921"))
    with pytest.raises(FixtureError, match="parties share a policy number: P7, P9") as caught:
        load_fixtures(fixture_copy.path, catalog)
    assert "POL-" not in str(caught.value)


def _drop_default_alternative(guideline):
    del guideline["document_alternative_guidance"]["default"]


def _add_unmapped_guidance_key(guideline):
    guideline["document_guidance"]["x-ray"] = {"en": "text"}


def _add_unmapped_alternative_key(guideline):
    guideline["document_alternative_guidance"]["x-ray"] = {"en": "text"}


def _duplicate_party_id(holders):
    holders[1]["party_id"] = holders[0]["party_id"]


@pytest.mark.parametrize(
    ("name", "change", "message"),
    [
        ("required_document_guideline.json", _drop_default_alternative, "has no default"),
        (
            "required_document_guideline.json",
            _add_unmapped_guidance_key,
            "document_guidance: document label 'x-ray' has no document code",
        ),
        (
            "required_document_guideline.json",
            _add_unmapped_alternative_key,
            "document_alternative_guidance: document label 'x-ray' has no document code",
        ),
        ("policyholders.json", _duplicate_party_id, "duplicate party_id: P9"),
    ],
    ids=["missing-default-alternative", "unmapped-guidance-key", "unmapped-alternative-key", "duplicate-party-id"],
)
def test_other_reference_errors_are_rejected(fixture_copy, catalog, name, change, message):
    fixture_copy.edit(name, change)
    with pytest.raises(FixtureError, match=message):
        load_fixtures(fixture_copy.path, catalog)


def test_repeated_keys_in_a_json_object_are_rejected(fixture_copy, catalog):
    path = fixture_copy.path / "claims.json"
    text = path.read_text(encoding="utf-8")
    assert '"status": "denied",' in text
    repeated = text.replace('"status": "denied",', '"status": "denied", "status": "open",', 1)
    path.write_text(repeated, encoding="utf-8")
    with pytest.raises(FixtureError, match="claims.json: repeated key in one JSON object: status"):
        load_fixtures(fixture_copy.path, catalog)


@pytest.mark.parametrize(
    "content",
    [b"{not json", '[{"rep_name": "L\u00f3pez"}]'.encode("latin-1"), None],
    ids=["malformed-json", "not-utf8", "missing-file"],
)
def test_unreadable_files_are_named_without_chaining(fixture_copy, catalog, content):
    path = fixture_copy.path / "representatives.json"
    if content is None:
        path.unlink()
    else:
        path.write_bytes(content)
    with pytest.raises(FixtureError, match="representatives.json") as caught:
        load_fixtures(fixture_copy.path, catalog)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_importer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.claims.importer'`

- [ ] **Step 3: Implement the importer**

`services/api/app/claims/importer.py`:

```python
"""Loads the supplied fixtures read-only, validates each file, and checks the
references between files. Nothing here writes to the fixture directory, and no
error message carries a record's personal data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.claims.documents import DocumentCatalog, UnknownDocumentLabel
from app.contracts.fixtures import (
    Claim,
    ClaimSchemaDoc,
    ConsentScenario,
    DocumentGuideline,
    Policyholder,
    Representative,
)


class FixtureError(ValueError):
    pass


@dataclass(frozen=True)
class FixtureStore:
    policyholders: tuple[Policyholder, ...]
    claims: tuple[Claim, ...]
    claim_schema: ClaimSchemaDoc
    consent_scenarios: Mapping[str, ConsentScenario]
    representatives: tuple[Representative, ...]
    guideline: DocumentGuideline
    claim_versions: Mapping[str, str]

    def policyholder(self, party_id: str) -> Policyholder | None:
        return next((p for p in self.policyholders if p.party_id == party_id), None)

    def claim(self, case_id: str) -> Claim | None:
        return next((c for c in self.claims if c.case_id == case_id), None)

    def claims_for_party(self, party_id: str) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.party_id == party_id)


_FILES: dict[str, TypeAdapter[Any]] = {
    "policyholders.json": TypeAdapter(tuple[Policyholder, ...]),
    "claims.json": TypeAdapter(tuple[Claim, ...]),
    "claim_schema.json": TypeAdapter(ClaimSchemaDoc),
    "consent_scenarios.json": TypeAdapter(dict[str, ConsentScenario]),
    "representatives.json": TypeAdapter(tuple[Representative, ...]),
    "required_document_guideline.json": TypeAdapter(DocumentGuideline),
}


def load_fixtures(directory: Path, catalog: DocumentCatalog) -> FixtureStore:
    raw: dict[str, Any] = {}
    parsed: dict[str, Any] = {}
    for name, adapter in _FILES.items():
        try:
            text = (directory / name).read_text(encoding="utf-8")
            raw[name] = json.loads(text, object_pairs_hook=_reject_repeated_keys)
        except (OSError, ValueError) as exc:
            # from None keeps the original error out of rendered tracebacks; its .doc
            # (JSONDecodeError) or .object (UnicodeDecodeError) holds the whole file.
            raise FixtureError(f"{name}: {exc}") from None
        try:
            parsed[name] = adapter.validate_python(raw[name])
        except ValidationError as exc:
            # Report where and why, never the rejected values: fixtures hold personal data.
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_input=False, include_url=False)
            )
            raise FixtureError(f"{name}: {details}") from None

    store = FixtureStore(
        policyholders=parsed["policyholders.json"],
        claims=parsed["claims.json"],
        claim_schema=parsed["claim_schema.json"],
        consent_scenarios=MappingProxyType(parsed["consent_scenarios.json"]),
        representatives=parsed["representatives.json"],
        guideline=parsed["required_document_guideline.json"],
        claim_versions=MappingProxyType(
            {record["case_id"]: _content_hash(record) for record in raw["claims.json"]}
        ),
    )
    _check_references(store, catalog)
    return store


def _reject_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise ValueError(f"repeated key in one JSON object: {', '.join(repeated)}")
    return dict(pairs)


def _content_hash(record: Any) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_references(store: FixtureStore, catalog: DocumentCatalog) -> None:
    party_ids = [p.party_id for p in store.policyholders]
    _require_unique("party_id", party_ids)
    _require_unique_policy_numbers(store.policyholders)
    _require_unique("case_id", [c.case_id for c in store.claims])

    for claim in store.claims:
        if claim.party_id not in party_ids:
            raise FixtureError(f"claims.json: {claim.case_id} belongs to unknown party {claim.party_id}")
        for label in claim.documents_needed:
            _require_code(catalog, label, f"claims.json: {claim.case_id}")

    for index, rep in enumerate(store.representatives):
        holder = store.policyholder(rep.buyer_party_id)
        if holder is None or holder.name != rep.buyer_name:
            raise FixtureError(
                f"representatives.json: [{index}] buyer does not match a policyholder ({rep.buyer_party_id})"
            )

    guideline = store.guideline
    _require_unique("follow-up topic", [rule.topic for rule in guideline.claim_followup_guidance])
    for key in guideline.document_guidance:
        _require_code(catalog, key, "required_document_guideline.json: document_guidance")
    for key in guideline.document_alternative_guidance:
        if key != "default":
            _require_code(catalog, key, "required_document_guideline.json: document_alternative_guidance")
    if "default" not in guideline.document_alternative_guidance:
        raise FixtureError("required_document_guideline.json: document_alternative_guidance has no default")


def _require_unique(field: str, values: list[str]) -> None:
    """For values that are not personal data: IDs and topics."""
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise FixtureError(f"duplicate {field}: {', '.join(duplicates)}")


def _require_unique_policy_numbers(holders: tuple[Policyholder, ...]) -> None:
    # A policy number identifies a customer, so name the pseudonymous party IDs instead.
    parties_by_number: dict[str, list[str]] = {}
    for holder in holders:
        parties_by_number.setdefault(holder.policy_number, []).append(holder.party_id)
    shared = sorted(sorted(ids) for ids in parties_by_number.values() if len(ids) > 1)
    if shared:
        groups = "; ".join(", ".join(ids) for ids in shared)
        raise FixtureError(f"policyholders.json: parties share a policy number: {groups}")


def _require_code(catalog: DocumentCatalog, label: str, where: str) -> None:
    try:
        catalog.code_for(label)
    except UnknownDocumentLabel:
        raise FixtureError(f"{where}: document label {label!r} has no document code") from None
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_importer.py -v`
Expected: PASS (24 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/claims/importer.py tests
git commit -m "feat: load fixtures read-only with cross-file checks"
```

---

### Task 7: Money and appeal deadlines

**Files:**
- Create: `services/api/app/claims/money.py`, `services/api/app/claims/deadlines.py`, `tests/unit/test_money_and_deadlines.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_money_and_deadlines.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_money_and_deadlines.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.claims.deadlines'`

- [ ] **Step 3: Implement money formatting and deadline status**

`services/api/app/claims/money.py`:

```python
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
```

`services/api/app/claims/deadlines.py`:

```python
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
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_money_and_deadlines.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/claims/money.py services/api/app/claims/deadlines.py tests/unit/test_money_and_deadlines.py
git commit -m "feat: format USD and compute appeal-deadline status"
```

---

### Task 8: Guidance library

**Files:**
- Create: `services/api/app/claims/guidance.py`, `tests/unit/test_guidance.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_guidance.py`:

```python
import pytest

from app.claims.guidance import (
    GuidanceLibrary,
    GuidanceRenderError,
    UnknownTopic,
    natural_list,
    render_template,
)


@pytest.fixture(scope="module")
def library(store, catalog):
    return GuidanceLibrary(store.guideline, catalog)


def test_denied_claim_gets_general_case_type_and_document_guidance(library, store):
    claim = store.claim("CL-2048")
    topics = [s.topic for s in library.for_documents(claim.case_type, claim.documents_needed)]
    assert topics == ["default", "case_type:healthcare", "document:PATHOLOGY_REPORT", "document:PROVIDER_OFFICE_NOTE"]


def test_diagnosis_report_has_no_specific_guidance(library, store):
    claim = store.claim("CL-3001")
    topics = [s.topic for s in library.for_documents(claim.case_type, claim.documents_needed)]
    assert topics == ["default", "case_type:healthcare"]


def test_alternatives_are_document_specific_or_default(library):
    assert library.alternatives("pathology report").topic == "alternative:PATHOLOGY_REPORT"
    assert library.alternatives("office note").topic == "alternative:PROVIDER_OFFICE_NOTE"
    assert library.alternatives("diagnosis report").topic == "alternative:default"


def test_submission_timing_is_filled_from_the_claim(library, store):
    snippet = library.followup(store.claim("CL-2048"), "submission_timing")
    assert snippet.text == "For claim CL-2048, please submit pathology report and office note within a week."
    assert snippet.source.endswith("#/claim_followup_guidance/1/en")


def test_every_topic_renders_completely_for_a_claim_with_documents(library, store):
    claim = store.claim("CL-2048")
    for topic in library.topics:
        text = library.followup(claim, topic).text
        assert "{" not in text and "}" not in text
        assert "original" not in text


def test_processing_time_comes_from_the_settings(library, store):
    text = library.followup(store.claim("CL-2048"), "processing_time_after_submission").text
    assert "The average processing time is usually less than a week" in text


def test_templates_do_not_apply_to_a_claim_without_documents(library, store):
    assert library.followup(store.claim("CL-2102"), "submission_method") == library.fallback()


def test_unknown_topic_is_rejected(library, store):
    with pytest.raises(UnknownTopic):
        library.followup(store.claim("CL-2048"), "refund_status")


def test_match_any_phrases_are_exposed_only_as_examples(library):
    assert "how long" in library.topic_examples("processing_time_after_submission")
    assert library.topic_examples("missing_required_material_alternatives") == ()


def test_human_review_rule_comes_with_provenance(library):
    rule = library.human_review_rule()
    assert rule.text.startswith("If the caller still cannot provide the requested item")
    assert rule.source.endswith("#/claim_followup_settings/human_review_after_document_alternatives_exhausted/en")


def test_rendering_refuses_an_empty_placeholder():
    with pytest.raises(GuidanceRenderError):
        render_template("Submit {documents} soon.", {"documents": ""})


def test_natural_list():
    assert natural_list(["a"]) == "a"
    assert natural_list(["a", "b"]) == "a and b"
    assert natural_list(["a", "b", "c"]) == "a, b, and c"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_guidance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.claims.guidance'`

- [ ] **Step 3: Implement the guidance library**

`services/api/app/claims/guidance.py`:

```python
"""Approved guidance snippets with provenance, and rendering of the follow-up
templates. A template renders only when every placeholder has a value."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.claims.documents import DocumentCatalog
from app.contracts.fixtures import Claim, DocumentGuideline, FollowupRule

SOURCE = "required_document_guideline.json"
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class UnknownTopic(KeyError):
    pass


class GuidanceRenderError(ValueError):
    pass


@dataclass(frozen=True)
class GuidanceSnippet:
    topic: str
    text: str
    source: str


def natural_list(items: Sequence[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def render_template(template: str, values: Mapping[str, str]) -> str:
    def fill(match: re.Match[str]) -> str:
        value = values.get(match.group(1))
        if not value:
            raise GuidanceRenderError(f"no value for placeholder {match.group(0)}")
        return value

    return _PLACEHOLDER.sub(fill, template)


class GuidanceLibrary:
    def __init__(self, guideline: DocumentGuideline, catalog: DocumentCatalog) -> None:
        self._guideline = guideline
        self._catalog = catalog
        self._document_keys = _keys_by_code(guideline.document_guidance, catalog)
        self._alternative_keys = _keys_by_code(
            {k: v for k, v in guideline.document_alternative_guidance.items() if k != "default"}, catalog
        )
        self._rules: dict[str, tuple[int, FollowupRule]] = {
            rule.topic: (index, rule) for index, rule in enumerate(guideline.claim_followup_guidance)
        }

    @property
    def topics(self) -> tuple[str, ...]:
        return tuple(self._rules)

    def topic_examples(self, topic: str) -> tuple[str, ...]:
        return self._rule(topic)[1].match_any

    def for_documents(self, case_type: str, labels: Sequence[str]) -> tuple[GuidanceSnippet, ...]:
        guideline = self._guideline
        snippets = [GuidanceSnippet("default", guideline.default_guidance.en, f"{SOURCE}#/default_guidance/en")]
        if case_type in guideline.case_type_guidance:
            snippets.append(
                GuidanceSnippet(
                    f"case_type:{case_type}",
                    guideline.case_type_guidance[case_type].en,
                    f"{SOURCE}#/case_type_guidance/{case_type}/en",
                )
            )
        for label in labels:
            code = self._catalog.code_for(label)
            key = self._document_keys.get(code)
            if key is not None:
                snippets.append(
                    GuidanceSnippet(
                        f"document:{code}",
                        guideline.document_guidance[key].en,
                        f"{SOURCE}#/document_guidance/{key}/en",
                    )
                )
        return tuple(snippets)

    def alternatives(self, label: str) -> GuidanceSnippet:
        code = self._catalog.code_for(label)
        key = self._alternative_keys.get(code)
        if key is None:
            return GuidanceSnippet(
                "alternative:default",
                self._guideline.document_alternative_guidance["default"].en,
                f"{SOURCE}#/document_alternative_guidance/default/en",
            )
        return GuidanceSnippet(
            f"alternative:{code}",
            self._guideline.document_alternative_guidance[key].en,
            f"{SOURCE}#/document_alternative_guidance/{key}/en",
        )

    def human_review_rule(self) -> GuidanceSnippet:
        settings = self._guideline.claim_followup_settings
        return GuidanceSnippet(
            "human_review",
            settings.human_review_after_document_alternatives_exhausted.en,
            f"{SOURCE}#/claim_followup_settings/human_review_after_document_alternatives_exhausted/en",
        )

    def fallback(self) -> GuidanceSnippet:
        return GuidanceSnippet(
            "fallback", self._guideline.claim_followup_fallback.en, f"{SOURCE}#/claim_followup_fallback/en"
        )

    def followup(self, claim: Claim, topic: str) -> GuidanceSnippet:
        index, rule = self._rule(topic)
        if rule.requires_documents and not claim.documents_needed:
            return self.fallback()
        settings = self._guideline.claim_followup_settings
        values = {
            "case_id": claim.case_id,
            "documents": natural_list(claim.documents_needed),
            "average_processing_time_after_submission": settings.average_processing_time_after_submission.en,
        }
        return GuidanceSnippet(
            f"followup:{topic}",
            render_template(rule.en, values),
            f"{SOURCE}#/claim_followup_guidance/{index}/en",
        )

    def _rule(self, topic: str) -> tuple[int, FollowupRule]:
        try:
            return self._rules[topic]
        except KeyError:
            raise UnknownTopic(topic) from None


def _keys_by_code(entries: Mapping[str, object], catalog: DocumentCatalog) -> dict[str, str]:
    keys: dict[str, str] = {}
    for key in entries:
        code = catalog.code_for(key)
        if code in keys:
            raise ValueError(f"guidance keys {keys[code]!r} and {key!r} share document code {code}")
        keys[code] = key
    return keys
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_guidance.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/claims/guidance.py tests/unit/test_guidance.py
git commit -m "feat: render approved guidance with provenance"
```

---

### Task 9: Identity normalization

**Files:**
- Create: `services/api/app/identity/__init__.py`, `services/api/app/identity/normalize.py`, `tests/unit/test_normalize.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_normalize.py`:

```python
import pytest

from app.identity.normalize import (
    Normalized,
    Problem,
    normalize,
    normalize_dob,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_ssn_last4,
)


@pytest.mark.parametrize(
    "raw", ["Margaret Chen", "  MARGARET   chen ", "Mrs. Margaret Chen", "margaret-chen", "Ｍａｒｇａｒｅｔ Ｃｈｅｎ"]
)
def test_name_variants_normalize_to_one_value(raw):
    assert normalize_name(raw) == Normalized("margaretchen")


def test_spacing_inside_a_name_does_not_matter():
    assert normalize_name("Yawen Li").value == normalize_name("Ya-Wen Li").value == "yawenli"


def test_name_word_order_is_not_normalized():
    assert normalize_name("Tian Ma").value != normalize_name("Ma Tian").value


def test_first_name_alone_is_incomplete():
    assert normalize_name("Margaret").problem is Problem.INCOMPLETE


def test_invisible_characters_are_rejected():
    assert normalize_name("Margaret​ Chen").problem is Problem.CONTROL_CHARACTERS
    assert normalize_email("margaret@email.com‍").problem is Problem.CONTROL_CHARACTERS


@pytest.mark.parametrize(
    "raw", ["1985-03-15", "March 15, 1985", "15 March 1985", "Mar 15th 1985", "03/15/1985", "15/03/1985"]
)
def test_unambiguous_dates_of_birth(raw):
    assert normalize_dob(raw) == Normalized("1985-03-15")


def test_day_month_ambiguity_returns_both_readings():
    result = normalize_dob("03/04/1985")
    assert result.problem is Problem.AMBIGUOUS
    assert result.candidates == ("1985-03-04", "1985-04-03")


def test_same_day_and_month_is_not_ambiguous():
    assert normalize_dob("05/05/1990") == Normalized("1990-05-05")


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        ("03/15/85", Problem.INCOMPLETE),
        ("March 15, 85", Problem.INCOMPLETE),
        ("1985-02-30", Problem.INVALID),
        ("sometime in 1985", Problem.INVALID),
    ],
)
def test_unusable_dates_of_birth(raw, problem):
    assert normalize_dob(raw).problem is problem


@pytest.mark.parametrize("raw", ["+1 (650) 521-2836", "650-521-2836", "16505212836", "650.521.2836"])
def test_us_phone_formats(raw):
    assert normalize_phone(raw, default_country_code="1", national_length=10) == Normalized("+16505212836")


def test_explicit_country_code_is_kept():
    result = normalize_phone("+44 20 7946 0958", default_country_code="1", national_length=10)
    assert result == Normalized("+442079460958")


@pytest.mark.parametrize(
    ("raw", "problem"),
    [("521-2836", Problem.INCOMPLETE), ("44 20 7946 0958", Problem.AMBIGUOUS), ("650-CALL-NOW", Problem.INVALID)],
)
def test_unusable_phone_numbers_are_not_guessed(raw, problem):
    assert normalize_phone(raw, default_country_code="1", national_length=10).problem is problem


def test_email_is_trimmed_and_case_folded_but_otherwise_kept():
    assert normalize_email(" Margaret@Email.COM ") == Normalized("margaret@email.com")
    assert normalize_email("yawen.li+claims@gmail.com") == Normalized("yawen.li+claims@gmail.com")


@pytest.mark.parametrize("raw", ["not-an-email", "a@b", "a@@b.com", "a b@c.com"])
def test_invalid_emails(raw):
    assert normalize_email(raw).problem is Problem.INVALID


def test_ssn_last4_keeps_leading_zeros_and_ignores_spacing():
    assert normalize_ssn_last4("0042") == Normalized("0042")
    assert normalize_ssn_last4("44 72") == Normalized("4472")


def test_full_width_digits_are_read_as_ascii(policy):
    assert normalize_ssn_last4("４４７２") == Normalized("4472")
    assert normalize("phone", "６５０-５２１-２８３６", policy) == Normalized("+16505212836")
    assert normalize_dob("１９８５-０３-１５") == Normalized("1985-03-15")


@pytest.mark.parametrize(
    ("normalizer", "raw"),
    [
        (normalize_ssn_last4, "٤٤٧٢"),
        (normalize_dob, "١٩٨٥-٠٣-١٥"),
        (lambda raw: normalize_phone(raw, default_country_code="1", national_length=10), "٦٥٠٥٢١٢٨٣٦"),
    ],
    ids=["ssn", "dob", "phone"],
)
def test_digits_from_other_scripts_are_rejected(normalizer, raw):
    assert normalizer(raw).problem is Problem.INVALID


@pytest.mark.parametrize(
    ("raw", "problem"), [("447", Problem.INCOMPLETE), ("123-45-4472", Problem.INVALID), ("abcd", Problem.INVALID)]
)
def test_unusable_ssn_values(raw, problem):
    assert normalize_ssn_last4(raw).problem is problem


def test_dispatcher_uses_policy_phone_settings(policy):
    assert normalize("phone", "650-521-2836", policy) == Normalized("+16505212836")
    assert normalize("dob", "March 15, 1985", policy) == Normalized("1985-03-15")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.identity'`

- [ ] **Step 3: Implement normalization**

`services/api/app/identity/__init__.py`:

```python
"""Identity evidence normalization and matching."""
```

`services/api/app/identity/normalize.py`:

```python
"""Deterministic normalization of caller-supplied identity values. Nothing here
guesses: unclear input comes back with a problem the conversation can ask about.
Numeric input is NFKC-normalized (full-width digits become ASCII) and then only
ASCII digits are accepted, matching the stored values."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.policies import IdentityField, Policy


class Problem(StrEnum):
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"
    CONTROL_CHARACTERS = "control_characters"


@dataclass(frozen=True)
class Normalized:
    value: str | None
    problem: Problem | None = None
    candidates: tuple[str, ...] = ()


def _problem(problem: Problem, candidates: tuple[str, ...] = ()) -> Normalized:
    return Normalized(None, problem, candidates)


_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Co", "Cs"}
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def has_invisible_characters(text: str) -> bool:
    return any(
        unicodedata.category(ch) in _INVISIBLE_CATEGORIES and ch not in _ALLOWED_CONTROLS for ch in text
    )


_HONORIFICS = {"mr", "mrs", "ms", "miss", "mx", "dr"}
_NAME_WORDS = re.compile(r"[^\W\d_]+")


def normalize_name(raw: str) -> Normalized:
    """Case, spacing, punctuation, and Unicode form are normalized; word order is not."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    words = _NAME_WORDS.findall(unicodedata.normalize("NFKC", raw).casefold())
    while words and words[0] in _HONORIFICS:
        words.pop(0)
    if len(words) < 2:
        return _problem(Problem.INCOMPLETE)
    return Normalized("".join(words))


_MONTH_NAMES = [
    ("january", "jan"),
    ("february", "feb"),
    ("march", "mar"),
    ("april", "apr"),
    ("may",),
    ("june", "jun"),
    ("july", "jul"),
    ("august", "aug"),
    ("september", "sep", "sept"),
    ("october", "oct"),
    ("november", "nov"),
    ("december", "dec"),
]
_MONTHS = {name: number for number, names in enumerate(_MONTH_NAMES, start=1) for name in names}
_ISO = re.compile(r"([0-9]{4})[-/.]([0-9]{1,2})[-/.]([0-9]{1,2})")
_NUMERIC = re.compile(r"([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{2}|[0-9]{4})")
_DATE_FILLER = {"st", "nd", "rd", "th", "of", "the"}


def _date_or_none(year: int, month: int, day: int) -> date | None:
    if not 1900 <= year <= 2100:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def normalize_dob(raw: str) -> Normalized:
    """Returns an ISO date, or a problem. Numeric dates where day and month could be
    swapped come back AMBIGUOUS with both readings; two-digit years are INCOMPLETE."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    text = unicodedata.normalize("NFKC", raw).strip().casefold()

    if match := _ISO.fullmatch(text):
        parsed = _date_or_none(*(int(part) for part in match.groups()))
        return Normalized(parsed.isoformat()) if parsed else _problem(Problem.INVALID)

    if match := _NUMERIC.fullmatch(text):
        first, second, year_text = match.groups()
        if len(year_text) == 2:
            return _problem(Problem.INCOMPLETE)
        year = int(year_text)
        readings = {
            reading
            for reading in (_date_or_none(year, int(first), int(second)), _date_or_none(year, int(second), int(first)))
            if reading is not None
        }
        if not readings:
            return _problem(Problem.INVALID)
        if len(readings) == 2:
            return _problem(Problem.AMBIGUOUS, tuple(sorted(r.isoformat() for r in readings)))
        return Normalized(readings.pop().isoformat())

    tokens = [t for t in re.findall(r"[a-z]+|[0-9]+", text) if t not in _DATE_FILLER]
    months = [t for t in tokens if t in _MONTHS]
    numbers = [t for t in tokens if t.isdigit()]
    if len(tokens) != 3 or len(months) != 1 or len(numbers) != 2:
        return _problem(Problem.INVALID)
    years = [n for n in numbers if len(n) == 4]
    days = [n for n in numbers if len(n) <= 2]
    if not years:
        return _problem(Problem.INCOMPLETE)
    if len(years) != 1 or len(days) != 1:
        return _problem(Problem.INVALID)
    parsed = _date_or_none(int(years[0]), _MONTHS[months[0]], int(days[0]))
    return Normalized(parsed.isoformat()) if parsed else _problem(Problem.INVALID)


_PHONE_CHARACTERS = re.compile(r"[0-9\s()+.\-]+")


def normalize_phone(raw: str, *, default_country_code: str, national_length: int) -> Normalized:
    """Returns E.164. The default country code applies only to national-length numbers;
    anything else without an explicit country code is not guessed."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    text = unicodedata.normalize("NFKC", raw).strip()
    if not _PHONE_CHARACTERS.fullmatch(text) or "+" in text[1:]:
        return _problem(Problem.INVALID)
    digits = re.sub(r"[^0-9]", "", text)
    if text.startswith("+"):
        return Normalized(f"+{digits}") if 8 <= len(digits) <= 15 else _problem(Problem.INVALID)
    if len(digits) == national_length:
        return Normalized(f"+{default_country_code}{digits}")
    if len(digits) == len(default_country_code) + national_length and digits.startswith(default_country_code):
        return Normalized(f"+{digits}")
    if len(digits) < national_length:
        return _problem(Problem.INCOMPLETE)
    return _problem(Problem.AMBIGUOUS)


def normalize_email(raw: str) -> Normalized:
    """Trims and case-folds. Dots and plus tags in the local part are kept as given."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    text = raw.strip()
    local, separator, domain = text.partition("@")
    if (
        not separator
        or not local
        or "@" in domain
        or "." not in domain.strip(".")
        or any(ch.isspace() for ch in text)
    ):
        return _problem(Problem.INVALID)
    return Normalized(f"{local.casefold()}@{domain.casefold()}")


def normalize_ssn_last4(raw: str) -> Normalized:
    """Exactly four digits, leading zeros kept. A full SSN is refused, not trimmed."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    digits = re.sub(r"[\s\-]", "", unicodedata.normalize("NFKC", raw).strip())
    if re.fullmatch(r"[0-9]{4}", digits):
        return Normalized(digits)
    if re.fullmatch(r"[0-9]{1,3}", digits):
        return _problem(Problem.INCOMPLETE)
    return _problem(Problem.INVALID)


def normalize(field: IdentityField, raw: str, policy: Policy) -> Normalized:
    match field:
        case "full_name":
            return normalize_name(raw)
        case "dob":
            return normalize_dob(raw)
        case "phone":
            return normalize_phone(
                raw,
                default_country_code=policy.phone.default_country_calling_code,
                national_length=policy.phone.national_number_length,
            )
        case "email":
            return normalize_email(raw)
        case "ssn_last4":
            return normalize_ssn_last4(raw)
    raise ValueError(f"unknown identity field {field!r}")
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_normalize.py -v`
Expected: PASS (43 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/identity tests/unit/test_normalize.py
git commit -m "feat: normalize caller identity values without guessing"
```

---

### Task 10: Identity field values

**Files:**
- Create: `services/api/app/identity/fields.py`, `tests/unit/test_identity_fields.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_identity_fields.py`:

```python
import pytest

from app.identity.fields import UnusableRecordValue, field_matches, record_values
from app.identity.normalize import normalize_email, normalize_name


def test_ssn_last4_matches_an_ssn_record(store):
    assert field_matches(store.policyholder("P9"), "ssn_last4", "4472")


@pytest.mark.parametrize(("party_id", "digits"), [("P12", "6688"), ("P13", "5317")])
def test_national_id_never_counts_as_ssn(store, party_id, digits):
    holder = store.policyholder(party_id)
    assert record_values(holder, "ssn_last4") == frozenset()
    assert not field_matches(holder, "ssn_last4", digits)


def test_name_aliases_and_spacing_variants_match(store):
    holder = store.policyholder("P13")
    assert field_matches(holder, "full_name", normalize_name("Yaven Li").value)
    assert field_matches(holder, "full_name", normalize_name("Yawen Li").value)


def test_reversed_name_order_does_not_match(store):
    assert not field_matches(store.policyholder("P12"), "full_name", normalize_name("Tian Ma").value)


def test_duplicate_phone_alias_is_one_value(store):
    assert record_values(store.policyholder("P13"), "phone") == frozenset({"+16505212830"})


def test_email_alias_matches(store):
    assert field_matches(store.policyholder("P13"), "email", normalize_email("yawen.li@example.com").value)


def test_phone_one_digit_off_does_not_match(store):
    assert not field_matches(store.policyholder("P9"), "phone", "+16505212830")


def test_dob_matches_the_iso_value(store):
    assert field_matches(store.policyholder("P9"), "dob", "1985-03-15")


def test_every_stored_identity_value_is_usable(store):
    for holder in store.policyholders:
        for field in ("full_name", "dob", "phone", "email"):
            assert record_values(holder, field), (holder.party_id, field)


def test_an_unusable_stored_name_raises_instead_of_being_dropped(store):
    holder = store.policyholder("P9").model_copy(update={"name_aliases": ("Margaret",)})
    with pytest.raises(UnusableRecordValue, match="P9: a stored full_name cannot be normalized"):
        record_values(holder, "full_name")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/unit/test_identity_fields.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.identity.fields'`

- [ ] **Step 3: Implement record field values**

`services/api/app/identity/fields.py`:

```python
"""Which normalized values a policyholder record holds for each permitted field.
Aliases count as the same field, and a national ID never answers for an SSN. A
stored value that cannot be normalized is a data error and raises; it is never
silently dropped."""

from __future__ import annotations

from app.contracts.fixtures import Policyholder
from app.identity.normalize import Normalized, normalize_email, normalize_name
from app.policies import IdentityField


class UnusableRecordValue(ValueError):
    pass


def _usable(result: Normalized, record: Policyholder, field: IdentityField) -> str:
    if result.value is None:
        raise UnusableRecordValue(
            f"{record.party_id}: a stored {field} cannot be normalized ({result.problem})"
        )
    return result.value


def record_values(record: Policyholder, field: IdentityField) -> frozenset[str]:
    match field:
        case "full_name":
            names = (record.name, *record.name_aliases)
            return frozenset(_usable(normalize_name(name), record, field) for name in names)
        case "dob":
            return frozenset({record.dob.isoformat()})
        case "phone":
            return frozenset((record.phone, *record.phone_aliases))
        case "email":
            emails = (record.email, *record.email_aliases)
            return frozenset(_usable(normalize_email(email), record, field) for email in emails)
        case "ssn_last4":
            return frozenset({record.id_last4}) if record.id_type == "ssn_last4" else frozenset()
    raise ValueError(f"unknown identity field {field!r}")


def field_matches(record: Policyholder, field: IdentityField, normalized_value: str) -> bool:
    return normalized_value in record_values(record, field)
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/unit/test_identity_fields.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/identity/fields.py tests/unit/test_identity_fields.py
git commit -m "feat: expose normalized record values per identity field"
```

---

### Task 11: Milestone verification

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest`
Expected: every test passes; no warnings about missing modules.

- [ ] **Step 2: Confirm the acceptance gate**

| Gate item | Evidence |
|---|---|
| All six fixtures validate | `test_fixture_contracts.py`, `test_importer.py::test_store_holds_every_fixture_record` |
| Document aliases resolve | `test_documents.py`, importer label checks, `test_guidance.py` |
| Date and Decimal behavior tested | `test_money_and_deadlines.py`, `test_fixture_contracts.py` money tests, `test_normalize.py` DOB tests |
| National ID cannot count as SSN | `test_identity_fields.py::test_national_id_never_counts_as_ssn`, `test_policies.py::test_unsafe_or_incoherent_settings_are_rejected[national-id-field]` |
| Original fixtures unchanged | `test_fixture_integrity.py`, `test_importer.py::test_loading_leaves_fixture_files_untouched` |

- [ ] **Step 3: Confirm the working tree is clean**

Run: `git status --short`
Expected: no output.
