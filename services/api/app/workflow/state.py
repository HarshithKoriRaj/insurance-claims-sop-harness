"""Session state. The model never writes this directly: the workflow engine applies a
validated interpretation of each turn and decides every transition."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.policies import IdentityField

Phase = Literal["VERIFY_ID", "RESOLVE_INTENT", "PROCESS_CASE", "POST_PROCESS"]
Lifecycle = Literal["ACTIVE", "HANDOFF_PENDING", "CLOSED"]
PHASES: tuple[Phase, ...] = ("VERIFY_ID", "RESOLVE_INTENT", "PROCESS_CASE", "POST_PROCESS")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Message(_Model):
    id: int
    role: Literal["user", "assistant"]
    text: str
    phase: Phase
    at: datetime


class CaseHints(_Model):
    case_id: str | None = None
    case_type: str | None = None
    status: str | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = None

    def merged_with(self, newer: CaseHints) -> CaseHints:
        return CaseHints(**{name: getattr(newer, name) or getattr(self, name) for name in type(self).model_fields})

    def any(self) -> bool:
        return any(getattr(self, name) is not None for name in type(self).model_fields)


class SummaryState(_Model):
    status: Literal["none", "offered", "sent", "skipped"] = "none"
    summary_id: str | None = None
    subject: str | None = None
    body: str | None = None


class SessionState(_Model):
    session_id: str
    phase: Phase = "VERIFY_ID"
    lifecycle: Lifecycle = "ACTIVE"
    handoff_reason: str | None = None

    # Identity evidence: normalized values only, cleared as soon as verification succeeds.
    evidence: dict[IdentityField, str] = Field(default_factory=dict)
    verified_party_id: str | None = None
    verified_fields: list[IdentityField] = Field(default_factory=list)
    verified_at: datetime | None = None
    failed_attempts: int = 0

    # Memory carried across phases.
    intent: str | None = None
    followup_topic: str | None = None
    case_hints: CaseHints = Field(default_factory=CaseHints)
    selected_case_id: str | None = None
    candidate_case_ids: list[str] = Field(default_factory=list)
    discussed: list[str] = Field(default_factory=list)
    emotion: str = "neutral"

    # Recovery counters.
    off_topic_count: int = 0
    refusal_count: int = 0

    summary: SummaryState = Field(default_factory=SummaryState)
    messages: list[Message] = Field(default_factory=list)
    # After verification expires, the transcript view starts here, so earlier claim
    # details are not shown again to whoever holds the session now.
    visible_from: int = 0
    created_at: datetime
    last_activity_at: datetime

    def add_message(self, role: Literal["user", "assistant"], text: str, at: datetime) -> Message:
        message = Message(id=len(self.messages) + 1, role=role, text=text, phase=self.phase, at=at)
        self.messages.append(message)
        return message
