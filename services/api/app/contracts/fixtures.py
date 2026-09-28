"""Strict schemas for the six supplied fixture files. Unknown keys are rejected, so
a changed fixture fails loudly instead of being partly read."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

_MONEY = re.compile(r"^\d+\.\d{2}$")


def _money(value: object) -> Decimal:
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        raise ValueError("money must be a decimal string with two places, such as '1450.00'")
    return Decimal(value)


Money = Annotated[Decimal, BeforeValidator(_money)]
E164 = Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{7,14}$")]
Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Last4 = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
CaseType = Literal["healthcare", "dental", "auto"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Policyholder(_Strict):
    party_id: str
    name: str
    name_aliases: tuple[str, ...] = ()
    policy_number: str
    dob: date
    id_type: Literal["ssn_last4", "national_id_last4"]
    id_last4: Last4
    phone: E164
    phone_aliases: tuple[E164, ...] = ()
    email: Email
    email_aliases: tuple[Email, ...] = ()


class Claim(_Strict):
    case_id: str
    party_id: str
    case_type: CaseType
    created_at: date
    status: Literal["denied", "closed", "open"]
    summary: str
    denial_reason: str | None = None
    documents_needed: tuple[str, ...] = ()
    appeal_deadline: date | None = None
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
    rep_name: str
    relationship: str
    buyer_name: str
    buyer_party_id: str


class LocalizedText(_Strict):
    en: str


class FollowupRule(_Strict):
    topic: str
    intent_hints: tuple[str, ...]
    requires_documents: bool
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
