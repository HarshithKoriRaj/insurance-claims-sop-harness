"""Glue between the session, the model, and the templates. The model's labels and
wording are always optional: any failure falls back to the rule interpreter or the
templates, and a model reply that would leak claim data before verification is
discarded."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict
from typing import Any

from app.claims.guidance import GuidanceLibrary
from app.contracts.fixtures import Policyholder
from app.conversation.claude import ClaudeModel
from app.conversation.interpretation import Interpretation, rule_interpret
from app.conversation.templates import template_reply
from app.workflow.engine import Brief
from app.workflow.state import SessionState

log = logging.getLogger(__name__)

# What each situation asks of the reply, so the model's wording follows the engine's decision.
SITUATION_GUIDE = {
    "greeting": "Greet the caller. Explain that you must verify identity before discussing any claim, and ask for at least three of the listed details.",
    "verification_needed": "Explain briefly that verification comes first and ask for the listed details (how many are still needed is in notes).",
    "verification_progress": "Thank the caller, mention any problems with what they gave (without revealing whether anything matched), and ask for the remaining details.",
    "need_another_field": "Ask for one more of the listed details; more than one account could match so far. Do not say that.",
    "verification_failed": "Say the details could not be verified, without saying which one. Invite them to re-check and try again; mention attempts remaining.",
    "identity_refusal": "Empathize, explain that verification protects their claim information, offer the alternative identity details, and offer a human if offer_human.",
    "representative": "Explain you can only verify the policyholder directly; acting for someone else needs their authorization, which a human representative can arrange. Offer to request one.",
    "out_of_scope": "Politely decline: you can only help with insurance claims and this conversation. Steer back to the task. Offer a human representative if offer_human.",
    "handoff": "Say a human representative has been requested (not connected). Mention that in this demo the transfer is simulated.",
    "handoff_waiting": "Say a human representative was already requested and the transfer is simulated in this demo.",
    "closed": "Say this conversation has ended and they can start a new one.",
    "goodbye": "Thank the caller and close warmly.",
    "ask_what_help": "Confirm they are verified if notes contain just_verified. List their claims (candidates) briefly and ask what they need help with.",
    "choose_case": "Confirm verification if just_verified. List the candidate claims and ask which one they mean.",
    "no_matching_case": "Confirm verification if just_verified. Say no claim on the account matches that description; list their claims if any.",
    "answer": "Confirm verification if just_verified. Answer the caller's question about the claim using only facts and guidance. Mention the appeal deadline relative to business_date when relevant. End by asking if they need anything else.",
    "summary_offer": "Offer to email the summary shown in the chat to the masked recipient; they can choose Send summary or Skip.",
    "summary_offer_repeat": "Ask again whether to send or skip the summary email.",
    "summary_sent": "Confirm the summary was sent to the masked recipient and close warmly.",
    "summary_skipped": "Confirm no summary will be sent and close warmly.",
    "summary_send_failed": "Say the summary could not be sent and nothing was sent; they can retry or skip.",
}
_UNVERIFIED_LEAK = re.compile(r"\bCL-?\s?[0-9]{3,}|\$\s?[0-9]")


class ConversationService:
    def __init__(self, model: ClaudeModel | None, library: GuidanceLibrary) -> None:
        self.model = model
        self.library = library

    @property
    def mode(self) -> str:
        return "claude" if self.model else "offline"

    def interpret(self, state: SessionState, text: str) -> Interpretation:
        offer_active = state.phase == "POST_PROCESS" and state.summary.status == "offered"
        if self.model is not None:
            context = {
                "phase": state.phase,
                "assistant_previous_message": next(
                    (m.text for m in reversed(state.messages[:-1]) if m.role == "assistant"), ""
                ),
                "summary_offer_active": offer_active,
                "candidate_case_ids": state.candidate_case_ids,
                "followup_topics": {topic: list(self.library.topic_examples(topic)) for topic in self.library.topics},
            }
            try:
                return self.model.interpret(context, text)
            except Exception as error:  # the rule interpreter keeps the demo running
                log.warning("model interpretation failed (%s); using rules", type(error).__name__)
        return rule_interpret(text, summary_offer_active=offer_active)

    def respond(self, state: SessionState, brief: Brief, holder: Policyholder | None) -> str:
        payload = self.brief_payload(state, brief, holder)
        if self.model is not None and brief.situation != "greeting":
            history = [{"role": m.role, "content": m.text} for m in state.messages[state.visible_from:][-12:]]
            try:
                reply = self.model.respond(payload, history)
                if state.verified_party_id or not _UNVERIFIED_LEAK.search(reply):
                    return reply
                log.warning("discarded a model reply that mentioned claim data before verification")
            except Exception as error:
                log.warning("model reply failed (%s); using template", type(error).__name__)
        return template_reply(payload)

    @staticmethod
    def brief_payload(state: SessionState, brief: Brief, holder: Policyholder | None) -> dict[str, Any]:
        payload = asdict(brief)
        payload["what_to_do"] = SITUATION_GUIDE.get(brief.situation, "Help the caller with their claim.")
        payload["phase"] = state.phase
        payload["emotion"] = state.emotion
        payload["verified"] = state.verified_party_id is not None
        if holder is not None and state.verified_party_id:
            payload["customer_first_name"] = holder.name.split()[0]
        return {key: value for key, value in payload.items() if value not in (None, [], {}, "")}
