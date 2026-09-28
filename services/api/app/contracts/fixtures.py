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
