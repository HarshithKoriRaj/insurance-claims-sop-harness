"""Loads the explicit, versioned defaults in policies/defaults.toml."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IdentityField = Literal["full_name", "dob", "phone", "email", "ssn_last4"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VerificationPolicy(_Strict):
    required_matching_fields: int = Field(ge=1)
    max_failed_submissions: int = Field(ge=1)
    idle_expiry_minutes: int = Field(ge=1)
    permitted_fields: tuple[IdentityField, ...]


class SessionPolicy(_Strict):
    max_age_hours: int = Field(ge=1)
    max_input_characters: int = Field(ge=1)
    recent_turns: int = Field(ge=1)
    max_turns: int = Field(ge=1)


class RecoveryPolicy(_Strict):
    unrelated_offer_human_at: int = Field(ge=1)
    unrelated_stop_at: int = Field(ge=1)
    refusals_before_stop: int = Field(ge=1)


class ClaimsPolicy(_Strict):
    fact_max_age_minutes: int = Field(ge=1)


class PhonePolicy(_Strict):
    default_country_calling_code: str = Field(pattern=r"^[1-9]\d{0,2}$")
    national_number_length: int = Field(ge=4, le=14)


class DemoPolicy(_Strict):
    business_date: date
    business_timezone: str


class Policy(_Strict):
    version: str
    verification: VerificationPolicy
    session: SessionPolicy
    recovery: RecoveryPolicy
    claims: ClaimsPolicy
    phone: PhonePolicy
    demo: DemoPolicy


def load_policy(path: Path) -> Policy:
    with path.open("rb") as handle:
        return Policy.model_validate(tomllib.load(handle))
