"""Claim access scoped to the verified subject. Every lookup takes the subject's party
ID; an unknown case ID and another customer's case ID give the same empty answer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.claims.deadlines import appeal_deadline_status
from app.claims.guidance import GuidanceLibrary, UnknownTopic
from app.claims.importer import FixtureStore
from app.claims.money import format_usd
from app.contracts.fixtures import Claim
from app.workflow.state import CaseHints

# Which follow-up template answers each intent when the caller did not name a topic.
INTENT_TOPICS = {
    "document_submission": "submission_method",
    "next_steps": "submission_timing",
    "denial_question": "submission_timing",
}
NEXT_STEP_TOPIC = "submission_timing"
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


@dataclass(frozen=True)
class ClaimAccess:
    store: FixtureStore
    guidance: GuidanceLibrary

    def owned(self, party_id: str) -> tuple[Claim, ...]:
        return tuple(sorted(self.store.claims_for_party(party_id), key=lambda c: c.created_at, reverse=True))

    def claim_for(self, party_id: str, case_id: str) -> Claim | None:
        claim = self.store.claim(case_id.strip().upper())
        return claim if claim is not None and claim.party_id == party_id else None

    def resolve(self, party_id: str, hints: CaseHints) -> list[Claim]:
        if hints.case_id:
            claim = self.claim_for(party_id, hints.case_id)
            return [claim] if claim else []
        matches = []
        for claim in self.owned(party_id):
            if hints.case_type and claim.case_type != hints.case_type:
                continue
            if hints.status and claim.status != hints.status:
                continue
            if hints.month and claim.created_at.month != hints.month:
                continue
            if hints.year and claim.created_at.year != hints.year:
                continue
            matches.append(claim)
        return matches

    @staticmethod
    def label(claim: Claim) -> dict[str, str]:
        created = f"{MONTHS[claim.created_at.month - 1]} {claim.created_at.day}, {claim.created_at.year}"
        return {"case_id": claim.case_id, "case_type": claim.case_type, "status": claim.status, "filed": created}

    def facts(self, claim: Claim, business_date: date) -> dict[str, Any]:
        facts: dict[str, Any] = {
            **self.label(claim),
            "summary": claim.summary,
            "expected_reimbursement": format_usd(claim.expected_reimbursement_amount),
            "allowed_maximum": format_usd(claim.allowed_max_amount),
            "net_pay": format_usd(claim.net_pay),
            "patient_responsibility_or_fee": format_usd(claim.net_fee),
        }
        if claim.denial_reason:
            facts["denial_reason"] = claim.denial_reason
        if claim.documents_needed:
            facts["documents_needed"] = list(claim.documents_needed)
        deadline = appeal_deadline_status(claim, business_date)
        if deadline is not None:
            facts["appeal_deadline"] = deadline.deadline.isoformat()
            facts["appeal_deadline_passed"] = deadline.passed
            facts["days_until_appeal_deadline"] = max(deadline.days_remaining, 0)
            facts["business_date"] = business_date.isoformat()
        return facts

    def guidance_for(self, claim: Claim, topic: str | None, intent: str | None) -> list[dict[str, str]]:
        snippets = []
        # With documents outstanding, the next step is always worth stating, whatever the intent.
        chosen = topic or INTENT_TOPICS.get(intent or "") or (NEXT_STEP_TOPIC if claim.documents_needed else None)
        if chosen:
            try:
                snippets.append(self.guidance.followup(claim, chosen))
            except UnknownTopic:
                snippets.append(self.guidance.fallback())
        for snippet in self.guidance.for_documents(claim.case_type, claim.documents_needed):
            if snippet.topic != "default":
                snippets.append(snippet)
        return [{"topic": s.topic, "text": s.text, "source": s.source} for s in snippets]
