"""The deterministic workflow. It applies a turn interpretation to the session state,
enforces every gate, and returns a brief describing what the reply must say.

Gates enforced here, whatever the model proposes:
- no claim data before verification (claim lookups need a verified party ID);
- only the verified subject's claims (every lookup is scoped to that party);
- no email without an explicit send decision on the current summary preview;
- a human handoff is requested, never reported as connected."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from app.claims.access import NEXT_STEP_TOPIC, ClaimAccess
from app.claims.importer import FixtureStore
from app.clock import Clock
from app.contracts.fixtures import Claim
from app.conversation.interpretation import Interpretation
from app.identity.normalize import Problem, normalize
from app.identity.verify import verify
from app.policies import IdentityField, Policy
from app.workflow.state import CaseHints, SessionState, SummaryState

Action = Literal["send_summary", "skip_summary", "request_human", "end_conversation"]
FIELD_LABELS: dict[str, str] = {
    "full_name": "full name",
    "dob": "date of birth",
    "phone": "phone number on file",
    "email": "email address on file",
    "ssn_last4": "last four digits of your SSN",
}


class ActionNotAvailable(ValueError):
    pass


@dataclass
class Brief:
    situation: str
    ask: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    facts: dict[str, Any] | None = None
    candidates: list[dict[str, str]] = field(default_factory=list)
    guidance: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, str] | None = None
    offer_human: bool = False
    problems: dict[str, str] = field(default_factory=dict)


class Mailer:
    """Interface: deliver one summary; must be idempotent on summary_id."""

    def send(self, summary_id: str, to: str, subject: str, body: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class WorkflowEngine:
    def __init__(self, policy: Policy, store: FixtureStore, access: ClaimAccess, clock: Clock, mailer: Mailer) -> None:
        self.policy = policy
        self.store = store
        self.access = access
        self.clock = clock
        self.mailer = mailer

    # ------------------------------------------------------------------ entry points

    def start(self, state: SessionState) -> Brief:
        return Brief("greeting", ask=self._missing_fields(state))

    def on_message(self, state: SessionState, interp: Interpretation, now: datetime) -> Brief:
        notes = self._expire_if_idle(state, now)
        brief = self._route(state, interp, now)
        brief.notes = notes + brief.notes
        return brief

    def _route(self, state: SessionState, interp: Interpretation, now: datetime) -> Brief:
        if state.lifecycle == "CLOSED":
            return Brief("closed")
        if state.lifecycle == "HANDOFF_PENDING":
            return Brief("handoff_waiting")
        self._remember(state, interp)
        if interp.wants_human:
            return self._handoff(state, "caller_request")
        if interp.scope == "out_of_scope" and not interp.has_substance():
            return self._off_topic(state)
        state.off_topic_count = 0
        handler = {
            "VERIFY_ID": self._verify_turn,
            "RESOLVE_INTENT": self._resolve_turn,
            "PROCESS_CASE": self._process_turn,
            "POST_PROCESS": self._post_turn,
        }[state.phase]
        return handler(state, interp, now)

    def on_action(self, state: SessionState, action: Action, now: datetime) -> Brief:
        if state.lifecycle != "ACTIVE":
            raise ActionNotAvailable(action)
        if action == "request_human":
            return self._handoff(state, "caller_request")
        if action == "end_conversation":
            if state.verified_party_id and state.discussed and state.summary.status == "none":
                return self._offer_summary(state)
            return self._close(state, "goodbye")
        if state.phase != "POST_PROCESS" or state.summary.status != "offered":
            raise ActionNotAvailable(action)
        return self._send_summary(state) if action == "send_summary" else self._skip_summary(state)

    def available_actions(self, state: SessionState) -> list[Action]:
        if state.lifecycle != "ACTIVE":
            return []
        actions: list[Action] = ["request_human", "end_conversation"]
        if state.phase == "POST_PROCESS" and state.summary.status == "offered":
            actions = ["send_summary", "skip_summary", *actions]
        return actions

    # ------------------------------------------------------------------ cross-phase

    def _remember(self, state: SessionState, interp: Interpretation) -> None:
        """Memory carried across phases, e.g. an intent stated before verification."""
        if interp.intent:
            state.intent = interp.intent
        if interp.followup_topic and interp.followup_topic in self.access.guidance.topics:
            state.followup_topic = interp.followup_topic
        state.emotion = interp.emotion
        if interp.case_hints.any() and state.phase == "VERIFY_ID":
            state.case_hints = state.case_hints.merged_with(interp.case_hints)

    def _expire_if_idle(self, state: SessionState, now: datetime) -> list[str]:
        idle = timedelta(minutes=self.policy.verification.idle_expiry_minutes)
        if state.verified_party_id and now - state.last_activity_at > idle:
            # Resume at verification without exposing what was discussed before.
            state.verified_party_id = None
            state.verified_fields = []
            state.selected_case_id = None
            state.candidate_case_ids = []
            state.case_hints = CaseHints()
            state.intent = None
            state.followup_topic = None
            state.discussed = []
            state.summary = SummaryState()
            state.phase = "VERIFY_ID"
            state.visible_from = len(state.messages)
            return ["verification_expired"]
        return []

    def _handoff(self, state: SessionState, reason: str) -> Brief:
        state.lifecycle = "HANDOFF_PENDING"
        state.handoff_reason = reason
        return Brief("handoff", notes=[reason])

    def _off_topic(self, state: SessionState) -> Brief:
        state.off_topic_count += 1
        recovery = self.policy.recovery
        if state.off_topic_count >= recovery.unrelated_stop_at:
            return self._handoff(state, "repeated_off_topic")
        ask = self._missing_fields(state) if state.phase == "VERIFY_ID" else []
        return Brief("out_of_scope", ask=ask, offer_human=state.off_topic_count >= recovery.unrelated_offer_human_at)

    def _close(self, state: SessionState, situation: str) -> Brief:
        state.lifecycle = "CLOSED"
        return Brief(situation)

    # ------------------------------------------------------------------ VERIFY_ID

    def _missing_fields(self, state: SessionState) -> list[str]:
        return [FIELD_LABELS[f] for f in self.policy.verification.permitted_fields if f not in state.evidence]

    def _still_needed(self, state: SessionState) -> int:
        return max(self.policy.verification.required_matching_fields - len(state.evidence), 0)

    def _verify_turn(self, state: SessionState, interp: Interpretation, now: datetime) -> Brief:
        mentions = interp.identity.present()
        if interp.representative and not mentions:
            return Brief("representative", offer_human=True)
        if interp.refuses_identity and not mentions:
            state.refusal_count += 1
            stop = state.refusal_count >= self.policy.recovery.refusal_stop_at
            return Brief("identity_refusal", ask=self._missing_fields(state), offer_human=stop)

        problems: dict[str, str] = {}
        for identity_field, raw in mentions.items():
            if identity_field not in self.policy.verification.permitted_fields:
                continue
            result = normalize(identity_field, raw, self.policy)
            if result.value is not None:
                state.evidence[identity_field] = result.value
            elif result.problem is Problem.INCOMPLETE and identity_field in state.evidence:
                continue  # a partial repeat of a detail already given, such as just a first name
            elif result.problem is Problem.AMBIGUOUS and result.candidates:
                problems[FIELD_LABELS[identity_field]] = "could be read two ways: " + " or ".join(
                    _spoken_date(c) for c in result.candidates
                )
            else:
                problems[FIELD_LABELS[identity_field]] = _problem_text(result.problem)

        outcome = verify(state.evidence, self.store.policyholders, self.policy.verification)
        if outcome.kind == "need_more":
            if not mentions and not problems:
                situation = "verification_needed"
            else:
                situation = "verification_progress"
            brief = Brief(situation, ask=self._missing_fields(state), problems=problems)
            brief.notes.append(f"details_still_needed={self._still_needed(state)}")
            return brief
        if outcome.kind == "verified":
            state.verified_party_id = outcome.party_id
            state.verified_fields = list(outcome.matched_fields)
            state.verified_at = now
            state.evidence = {}
            state.refusal_count = 0
            state.phase = "RESOLVE_INTENT"
            return self._after_verification(state)
        if outcome.kind == "ambiguous":
            return Brief("need_another_field", ask=self._missing_fields(state))
        state.failed_attempts += 1
        state.evidence = {}
        limit = self.policy.verification.max_failed_submissions
        if state.failed_attempts >= limit:
            return self._handoff(state, "verification_limit")
        brief = Brief("verification_failed", ask=self._missing_fields(state))
        brief.notes.append(f"attempts_remaining={limit - state.failed_attempts}")
        return brief

    # ------------------------------------------------------------------ RESOLVE_INTENT

    def _after_verification(self, state: SessionState) -> Brief:
        party = self._party(state)
        notes = ["just_verified"]
        if state.case_hints.any():
            claims = self.access.resolve(party, state.case_hints)
            if len(claims) == 1:
                return self._select(state, claims[0], notes)
            if claims:
                return self._choose(state, claims, notes)
            return Brief("no_matching_case", candidates=self._labels(self.access.owned(party)), notes=notes)
        owned = self.access.owned(party)
        if len(owned) == 1 and state.intent:
            return self._select(state, owned[0], notes)
        return Brief("ask_what_help", candidates=self._labels(owned), notes=notes)

    def _resolve_turn(self, state: SessionState, interp: Interpretation, now: datetime) -> Brief:
        party = self._party(state)
        if interp.done:
            return self._wrap_up(state)
        hints = interp.case_hints
        if hints.any():
            claims = self._resolve_hints(state, hints)
            if len(claims) == 1:
                return self._select(state, claims[0], [])
            if claims:
                return self._choose(state, claims, [])
            return Brief("no_matching_case", candidates=self._labels(self.access.owned(party)))
        owned = self.access.owned(party)
        if len(owned) == 1 and (interp.intent or interp.followup_topic):
            return self._select(state, owned[0], [])
        return Brief("ask_what_help", candidates=self._labels(owned))

    def _resolve_hints(self, state: SessionState, hints: CaseHints) -> list[Claim]:
        party = self._party(state)
        claims = self.access.resolve(party, hints)
        if state.candidate_case_ids:
            narrowed = [c for c in claims if c.case_id in state.candidate_case_ids]
            if narrowed:
                return narrowed
        if len(claims) > 1:
            merged = self.access.resolve(party, state.case_hints.merged_with(hints))
            if merged:
                return merged
        return claims

    def _choose(self, state: SessionState, claims: list[Claim], notes: list[str]) -> Brief:
        state.candidate_case_ids = [c.case_id for c in claims]
        state.phase = "RESOLVE_INTENT"
        return Brief("choose_case", candidates=self._labels(claims), notes=notes)

    def _select(self, state: SessionState, claim: Claim, notes: list[str]) -> Brief:
        state.selected_case_id = claim.case_id
        state.candidate_case_ids = []
        state.phase = "PROCESS_CASE"
        return self._answer(state, claim, [*notes, "case_selected"])

    # ------------------------------------------------------------------ PROCESS_CASE

    def _process_turn(self, state: SessionState, interp: Interpretation, now: datetime) -> Brief:
        claim = self._selected(state)
        if claim is None:
            state.phase = "RESOLVE_INTENT"
            return self._resolve_turn(state, interp, now)
        if interp.done:
            return self._wrap_up(state)
        if interp.case_hints.any() and not _describes(claim, interp.case_hints):
            # A different claim mid-case: start resolution again from the new description only,
            # so hints about the previous claim cannot steer the choice.
            state.selected_case_id = None
            state.phase = "RESOLVE_INTENT"
            state.candidate_case_ids = []
            state.case_hints = interp.case_hints
            return self._resolve_turn(state, interp, now)
        return self._answer(state, claim, [])

    def _answer(self, state: SessionState, claim: Claim, notes: list[str]) -> Brief:
        facts = self.access.facts(claim, self.clock.business_date())
        guidance = self.access.guidance_for(claim, state.followup_topic, state.intent)
        topic = state.followup_topic or state.intent or "claim overview"
        entry = f"{claim.case_id}: {topic.replace('_', ' ')}"
        if entry not in state.discussed:
            state.discussed.append(entry)
        state.followup_topic = None
        return Brief("answer", facts=facts, guidance=guidance, notes=notes)

    # ------------------------------------------------------------------ POST_PROCESS

    def _wrap_up(self, state: SessionState) -> Brief:
        if state.discussed:
            return self._offer_summary(state)
        return self._close(state, "goodbye")

    def _offer_summary(self, state: SessionState) -> Brief:
        state.phase = "POST_PROCESS"
        subject, body = self._build_summary(state)
        state.summary = SummaryState(status="offered", summary_id=uuid.uuid4().hex, subject=subject, body=body)
        return Brief("summary_offer", summary=self._summary_view(state))

    def _post_turn(self, state: SessionState, interp: Interpretation, now: datetime) -> Brief:
        if state.summary.status == "offered":
            if interp.summary_decision == "send":
                return self._send_summary(state)
            if interp.summary_decision == "skip":
                return self._skip_summary(state)
            if interp.case_hints.any() or interp.followup_topic or interp.intent:
                # A new question withdraws the preview; a fresh one is offered at the end.
                state.summary = SummaryState()
                state.phase = "PROCESS_CASE"
                return self._process_turn(state, interp, now)
            return Brief("summary_offer_repeat", summary=self._summary_view(state))
        return self._close(state, "goodbye")

    def _send_summary(self, state: SessionState) -> Brief:
        holder = self.store.policyholder(self._party(state))
        assert holder is not None and state.summary.summary_id and state.summary.body and state.summary.subject
        try:
            self.mailer.send(state.summary.summary_id, holder.email, state.summary.subject, state.summary.body)
        except Exception:
            return Brief("summary_send_failed", summary=self._summary_view(state))
        state.summary.status = "sent"
        state.lifecycle = "CLOSED"
        notes = [] if getattr(self.mailer, "delivers", True) else ["no_mail_server"]
        return Brief("summary_sent", summary=self._summary_view(state), notes=notes)

    def _skip_summary(self, state: SessionState) -> Brief:
        state.summary.status = "skipped"
        state.lifecycle = "CLOSED"
        return Brief("summary_skipped")

    def _build_summary(self, state: SessionState) -> tuple[str, str]:
        holder = self.store.policyholder(self._party(state))
        assert holder is not None
        business_date = self.clock.business_date()
        case_ids = list(dict.fromkeys(entry.split(":")[0] for entry in state.discussed))
        lines = [f"Hello {holder.name.split()[0]},", "", "Here is a summary of your conversation with the claims assistant.", ""]
        lines.append("What we discussed:")
        lines += [f"- {entry}" for entry in state.discussed]
        for case_id in case_ids:
            claim = self.access.claim_for(holder.party_id, case_id)
            if claim is None:
                continue
            facts = self.access.facts(claim, business_date)
            lines += ["", f"Claim {claim.case_id} ({claim.case_type}), filed {facts['filed']}", f"- Status: {claim.status}"]
            if claim.denial_reason:
                lines.append(f"- Reason: {claim.denial_reason}")
            if claim.documents_needed:
                lines.append(f"- Documents needed: {', '.join(claim.documents_needed)}")
            if "appeal_deadline" in facts:
                if facts["appeal_deadline_passed"]:
                    lines.append(f"- Appeal deadline: {facts['appeal_deadline']} (this date has passed)")
                else:
                    lines.append(
                        f"- Appeal deadline: {facts['appeal_deadline']} ({facts['days_until_appeal_deadline']} days from {business_date.isoformat()})"
                    )
            topic = NEXT_STEP_TOPIC if claim.documents_needed else None
            steps = [g["text"] for g in self.access.guidance_for(claim, topic, state.intent) if g["topic"].startswith("followup:")]
            if steps:
                lines.append("- Next steps: " + " ".join(steps))
        lines += ["", "If anything here looks wrong, reply to this message or contact support.", "", "Claims Assistant"]
        subject = f"Summary of your claims conversation ({', '.join(case_ids)})" if case_ids else "Summary of your claims conversation"
        return subject, "\n".join(lines)

    def _summary_view(self, state: SessionState) -> dict[str, str]:
        holder = self.store.policyholder(self._party(state))
        return {
            "subject": state.summary.subject or "",
            "body": state.summary.body or "",
            "recipient": mask_email(holder.email) if holder else "",
        }

    # ------------------------------------------------------------------ helpers

    def _party(self, state: SessionState) -> str:
        if not state.verified_party_id:
            raise PermissionError("claim access requires a verified caller")
        return state.verified_party_id

    def _selected(self, state: SessionState) -> Claim | None:
        if not state.selected_case_id:
            return None
        return self.access.claim_for(self._party(state), state.selected_case_id)

    def _labels(self, claims: Any) -> list[dict[str, str]]:
        return [ClaimAccess.label(c) for c in claims]


def _describes(claim: Claim, hints: CaseHints) -> bool:
    return (
        (hints.case_id is None or hints.case_id == claim.case_id)
        and (hints.case_type is None or hints.case_type == claim.case_type)
        and (hints.status is None or hints.status == claim.status)
        and (hints.month is None or hints.month == claim.created_at.month)
        and (hints.year is None or hints.year == claim.created_at.year)
    )


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}{'*' * max(len(local) - 1, 3)}@{domain}"


def _problem_text(problem: Problem | None) -> str:
    return {
        Problem.INCOMPLETE: "looks incomplete",
        Problem.INVALID: "could not be read",
        Problem.AMBIGUOUS: "is ambiguous",
        Problem.CONTROL_CHARACTERS: "contains hidden characters",
    }.get(problem, "could not be read") if problem else "could not be read"


def _spoken_date(iso: str) -> str:
    months = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December")
    year, month, day = (int(p) for p in iso.split("-"))
    return f"{months[month - 1]} {day}, {year}"
