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
