"""What the model may say about one caller message, and a deterministic rule-based
interpreter used for tests and when no model key is configured. An interpretation can
propose facts and labels; it can never set workflow state."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.policies import IdentityField
from app.workflow.state import CaseHints

Intent = Literal["status_inquiry", "denial_question", "document_submission", "next_steps", "general_claim_question"]
Emotion = Literal["neutral", "frustrated", "anxious", "angry", "confused"]
IDENTITY_FIELDS: tuple[IdentityField, ...] = ("full_name", "dob", "phone", "email", "ssn_last4")


class IdentityMention(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str | None = None
    dob: str | None = None
    phone: str | None = None
    email: str | None = None
    ssn_last4: str | None = None

    def present(self) -> dict[IdentityField, str]:
        return {field: value.strip() for field in IDENTITY_FIELDS if (value := getattr(self, field)) and value.strip()}


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    identity: IdentityMention = Field(default_factory=IdentityMention)
    refuses_identity: bool = False
    representative: bool = False
    intent: Intent | None = None
    case_hints: CaseHints = Field(default_factory=CaseHints)
    followup_topic: str | None = None
    scope: Literal["in_scope", "out_of_scope"] = "in_scope"
    emotion: Emotion = "neutral"
    wants_human: bool = False
    summary_decision: Literal["send", "skip"] | None = None
    done: bool = False

    @field_validator("case_hints", mode="before")
    @classmethod
    def _clean_hints(cls, value: Any) -> Any:
        # Models sometimes send empty strings or out-of-range months; drop them rather than fail.
        if not isinstance(value, dict):
            return value
        cleaned = {k: v for k, v in value.items() if v not in ("", None)}
        if not (isinstance(cleaned.get("month"), int) and 1 <= cleaned["month"] <= 12):
            cleaned.pop("month", None)
        if not isinstance(cleaned.get("year"), int):
            cleaned.pop("year", None)
        for key in ("case_type", "status"):
            if isinstance(cleaned.get(key), str):
                cleaned[key] = cleaned[key].strip().lower()
        if isinstance(cleaned.get("case_id"), str):
            cleaned["case_id"] = cleaned["case_id"].strip().upper()
        return {k: v for k, v in cleaned.items() if k in CaseHints.model_fields}

    def has_substance(self) -> bool:
        """Anything the workflow must act on even if the message also looks off-topic."""
        return bool(
            self.identity.present()
            or self.case_hints.any()
            or self.intent
            or self.summary_decision
            or self.done
            or self.refuses_identity
        )


# JSON schema for the model's tool call. Written out by hand so it has no $refs.
_NULLABLE_STRING = {"type": ["string", "null"]}
INTERPRETATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "identity": {
            "type": "object",
            "properties": {field: _NULLABLE_STRING for field in IDENTITY_FIELDS},
            "additionalProperties": False,
        },
        "refuses_identity": {"type": "boolean"},
        "representative": {"type": "boolean"},
        "intent": {"type": ["string", "null"], "enum": [*Intent.__args__, None]},
        "case_hints": {
            "type": "object",
            "properties": {
                "case_id": _NULLABLE_STRING,
                "case_type": {"type": ["string", "null"], "enum": ["healthcare", "dental", "auto", None]},
                "status": {"type": ["string", "null"], "enum": ["denied", "open", "closed", None]},
                "month": {"type": ["integer", "null"], "minimum": 1, "maximum": 12},
                "year": {"type": ["integer", "null"]},
            },
            "additionalProperties": False,
        },
        "followup_topic": _NULLABLE_STRING,
        "scope": {"type": "string", "enum": ["in_scope", "out_of_scope"]},
        "emotion": {"type": "string", "enum": list(Emotion.__args__)},
        "wants_human": {"type": "boolean"},
        "summary_decision": {"type": ["string", "null"], "enum": ["send", "skip", None]},
        "done": {"type": "boolean"},
    },
    "required": ["identity", "scope", "emotion", "wants_human", "done"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------- rule-based interpreter

_MONTHS = {
    name: number
    for number, names in enumerate(
        [("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",), ("june", "jun"),
         ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"), ("october", "oct"),
         ("november", "nov"), ("december", "dec")],
        start=1,
    )
    for name in names
}
_NAME = re.compile(r"(?i:my name is|my name's|this is|name is|i am|i'm)\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+)")
_DOB = re.compile(
    r"(?i:dob|date of birth|birth ?date|born on|born)\s*(?:is|was|:|-)?\s*"
    r"([0-9]{4}-[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}[/.-][0-9]{1,2}[/.-][0-9]{2,4}|[A-Za-z]+\.? [0-9]{1,2}(?:st|nd|rd|th)?,? [0-9]{2,4}|[0-9]{1,2}(?:st|nd|rd|th)? [A-Za-z]+,? [0-9]{2,4})"
)
_SSN = re.compile(r"(?i:ssn|social security|last (?:four|4))[^0-9]{0,25}?([0-9][0-9 -]{2,10}[0-9])\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w-])\+?[0-9][0-9 ().-]{8,}[0-9](?![\w-])")
_CASE_ID = re.compile(r"\bCL-?\s?([0-9]{3,6})\b", re.IGNORECASE)
_IN_SCOPE = re.compile(
    r"(?i)claim|polic|denied|denial|document|upload|submit|appeal|status|pay|reimburs|deductible|coverage|insur|"
    r"patholog|office note|report|deadline|verif|identity|ssn|social|birth|email|phone|summary|human|agent|"
    r"representative|person|hello|hi\b|hey|thank|help|yes|no\b|ok|sure|skip|send|bye|done|that's all|frustrat|"
    r"angry|worried|confus|upset"
)
_QUESTIONISH = re.compile(r"(?i)^\s*(what|who|how|why|when|where|can you|could you|tell me|explain|write|is it)\b|\?")


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def rule_interpret(text: str, *, summary_offer_active: bool = False) -> Interpretation:
    lowered = text.lower()
    identity = IdentityMention(
        full_name=_first(_NAME, text),
        dob=_first(_DOB, text),
        ssn_last4=_first(_SSN, text),
        email=(match.group(0) if (match := _EMAIL.search(text)) else None),
    )
    for candidate in _PHONE.findall(text):
        if len(re.sub(r"[^0-9]", "", candidate)) >= 10 and candidate.strip() != (identity.dob or ""):
            identity.phone = candidate.strip()
            break

    hints: dict[str, Any] = {}
    if match := _CASE_ID.search(text):
        hints["case_id"] = f"CL-{match.group(1)}"
    for case_type, words in (("healthcare", ("healthcare", "medical", "health")), ("dental", ("dental", "dentist")),
                             ("auto", ("auto", "car", "vehicle"))):
        if any(re.search(rf"\b{word}\b", lowered) for word in words):
            hints["case_type"] = case_type
            break
    for status, words in (("denied", ("denied", "denial", "rejected")), ("open", ("open", "pending")),
                          ("closed", ("closed",))):
        if any(re.search(rf"\b{word}\b", lowered) for word in words):
            hints["status"] = status
            break
    # A month counts as a claim hint only in claim phrasing ("from January", "January claim"),
    # never inside a date of birth.
    months = "|".join(sorted(_MONTHS, key=len, reverse=True))
    if match := re.search(rf"\b(?:from|in|filed in|back in|during|since)\s+({months})\b|\b({months})\s+claim\b", lowered):
        hints["month"] = _MONTHS[match.group(1) or match.group(2)]
        if year := re.search(rf"\b(?:{months})\s*,?\s*(20[0-9]{{2}})\b", lowered):
            hints["year"] = int(year.group(1))

    intent: str | None = None
    if re.search(r"denied|denial|why was|rejected", lowered):
        intent = "denial_question"
    elif re.search(r"upload|submit|send (the|my) (documents|files)|documents?", lowered):
        intent = "document_submission"
    elif re.search(r"next steps?|what's next|what is next|what now|what should i do|what do i do", lowered):
        intent = "next_steps"
    elif re.search(r"\bstatus\b|where is my claim|update on", lowered):
        intent = "status_inquiry"
    elif "claim" in lowered:
        intent = "general_claim_question"

    topic = None
    for name, pattern in (
        ("processing_time_after_submission", r"how long|processing time|how soon will"),
        ("submission_method", r"how (do|can) i (submit|upload|send)|where do i (send|upload)"),
        ("file_format_requirements", r"format|pdf|file type|scan"),
        ("missing_required_material_alternatives", r"can't get|cannot get|don't have|do not have|not available|lost"),
        ("receipt_confirmation", r"did you (get|receive)|received|confirm (receipt|you got)"),
        ("submission_timing", r"by when|when should i (submit|send)|how much time do i have"),
    ):
        if re.search(pattern, lowered):
            topic = name
            break

    emotion = "neutral"
    for label, pattern in (
        ("angry", r"angry|furious|unacceptable|outrageous"),
        ("frustrated", r"frustrat|annoy|ridiculous|fed up|waste of time"),
        ("anxious", r"worried|anxious|scared|nervous|stress"),
        ("confused", r"confus|don't understand|do not understand|not sure what"),
    ):
        if re.search(pattern, lowered):
            emotion = label
            break

    wants_human = bool(re.search(r"(talk|speak|connect|transfer).{0,20}(human|person|agent|representative)|real person|\bhuman\b", lowered))
    representative = bool(re.search(r"on behalf of|calling for my|for my (mother|father|mom|dad|son|daughter|wife|husband|client)", lowered))
    refuses = bool(re.search(r"(don't|do not|won't|will not|not comfortable|rather not).{0,30}(giv|shar|provid|tell)|why do you need", lowered))

    decision = None
    if summary_offer_active:
        if re.search(r"^\s*(yes|yeah|yep|sure|please|ok|okay|send)\b", lowered):
            decision = "send"
        elif re.search(r"^\s*(no|nope|skip|don't|do not|no thanks)\b", lowered):
            decision = "skip"
    done = bool(re.search(r"that's all|that is all|nothing else|no more questions|i'm done|that's it|\bbye\b|goodbye", lowered))

    has_identity = bool(identity.present())
    in_scope = has_identity or hints or intent or decision or done or _IN_SCOPE.search(text)
    scope = "out_of_scope" if (not in_scope and _QUESTIONISH.search(text)) else "in_scope"
    return Interpretation(
        identity=identity,
        refuses_identity=refuses and not has_identity,
        representative=representative,
        intent=intent,
        case_hints=CaseHints(**hints),
        followup_topic=topic,
        scope=scope,
        emotion=emotion,
        wants_human=wants_human,
        summary_decision=decision,
        done=done,
    )
