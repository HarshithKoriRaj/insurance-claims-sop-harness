"""Deterministic replies built from a brief. Used when no model key is configured, when a
model call fails, and when a model reply fails the safety check."""

from __future__ import annotations

from typing import Any

_EMPATHY = {
    "frustrated": "I'm sorry this has been frustrating.",
    "angry": "I understand you're upset, and I want to help sort this out.",
    "anxious": "I understand this is worrying, and I'll go through it with you step by step.",
    "confused": "No problem, let me make this clearer.",
}


def _list(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + f", or {items[-1]}"


def _claims(candidates: list[dict[str, str]]) -> str:
    return "\n".join(f"- {c['case_id']}: {c['case_type']} claim filed {c['filed']}, {c['status']}" for c in candidates)


def template_reply(brief: dict[str, Any]) -> str:
    situation = brief["situation"]
    ask: list[str] = brief.get("ask", [])
    parts: list[str] = []
    if (empathy := _EMPATHY.get(brief.get("emotion", "neutral"))) and situation not in ("greeting",):
        parts.append(empathy)
    notes = brief.get("notes", [])
    if "verification_expired" in notes:
        parts.append("For your security, your verification expired after a period of inactivity, so I need to confirm your identity again.")
    needed = next((int(n.split("=")[1]) for n in notes if n.startswith("details_still_needed=")), 3)
    name = brief.get("customer_first_name")

    if situation == "greeting":
        parts.append(
            "Hi, I'm the claims assistant. Before I can discuss any claim, I need to verify your identity. "
            f"Please share at least three of the following: {_list(ask)}."
        )
    elif situation in ("verification_needed", "verification_progress"):
        for label, problem in brief.get("problems", {}).items():
            parts.append(f"The {label} you gave {problem}. Could you give it again, with the month written out (for example March 4, 1985)?"
                         if "two ways" in problem else f"The {label} you gave {problem}; could you check it?")
        if situation == "verification_progress" and not brief.get("problems"):
            parts.append("Thanks.")
        parts.append(
            f"To protect your account I need {needed} more detail{'s' if needed != 1 else ''} to verify you. "
            f"You can use any of: {_list(ask)}."
        )
    elif situation == "need_another_field":
        parts.append(f"Thanks. I need one more detail to be sure I have the right account: {_list(ask)}.")
    elif situation == "verification_failed":
        remaining = next((n.split("=")[1] for n in notes if n.startswith("attempts_remaining=")), "")
        parts.append(
            "I couldn't verify your identity with those details. Please check them and try again "
            f"with at least three of: {_list(ask)}."
            + (f" You have {remaining} attempt{'s' if remaining != '1' else ''} left." if remaining else "")
        )
    elif situation == "identity_refusal":
        parts.append(
            "I understand. I ask for these details only to make sure I share claim information with the right person. "
            f"You can use any three of: {_list(ask)}."
        )
        if brief.get("offer_human"):
            parts.append("If you'd rather not share them here, I can request a human representative instead.")
    elif situation == "representative":
        parts.append(
            "I can only verify the policyholder directly in this chat. Acting for someone else needs their authorization, "
            "which a human representative can arrange. Would you like me to request one?"
        )
    elif situation == "out_of_scope":
        parts.append("Sorry, I can only help with your insurance claims, policy documents, and this conversation.")
        if ask:
            parts.append(f"To get started, please share at least three of: {_list(ask)}.")
        if brief.get("offer_human"):
            parts.append("If you need help with something else, I can request a human representative.")
    elif situation == "handoff":
        reason = notes[-1] if notes else ""
        why = {
            "verification_limit": "I wasn't able to verify your identity after several attempts, so I've stopped automated verification.",
            "repeated_off_topic": "It sounds like you need help beyond what I can do here.",
        }.get(reason, "")
        parts.append((why + " " if why else "") + "I've requested a human representative to take over this conversation. "
                     "In this demo the transfer is simulated, so no one will join the chat.")
    elif situation == "handoff_waiting":
        parts.append("A human representative has already been requested for this conversation. In this demo the transfer is simulated.")
    elif situation in ("closed", "goodbye"):
        parts.append("Thanks for contacting us. This conversation is now closed; you can start a new one any time.")
    elif situation == "ask_what_help":
        greeting = f"Thanks{', ' + name if name else ''}, you're verified."
        candidates = brief.get("candidates", [])
        if candidates:
            parts.append(f"{greeting} These are the claims on your account:\n{_claims(candidates)}\nWhich one can I help with?")
        else:
            parts.append(f"{greeting} I don't see any claims on your account. What can I help you with?")
    elif situation == "choose_case":
        lead = f"Thanks{', ' + name if name else ''}, you're verified. " if "just_verified" in notes else ""
        parts.append(f"{lead}I found more than one claim that could match:\n{_claims(brief['candidates'])}\nWhich one do you mean?")
    elif situation == "no_matching_case":
        lead = f"Thanks{', ' + name if name else ''}, you're verified. " if "just_verified" in notes else ""
        candidates = brief.get("candidates", [])
        listing = f" These are the claims on your account:\n{_claims(candidates)}" if candidates else ""
        parts.append(f"{lead}I couldn't find a claim on your account matching that description.{listing}")
    elif situation == "answer":
        parts.append(_answer(brief, name))
    elif situation in ("summary_offer", "summary_offer_repeat"):
        summary = brief["summary"]
        parts.append(
            f"Would you like me to email a summary of this conversation to {summary['recipient']}? "
            "You can review it above and choose Send summary or Skip."
        )
    elif situation == "summary_sent":
        parts.append(f"Done: the summary was sent to {brief['summary']['recipient']}. Thanks for contacting us.")
    elif situation == "summary_skipped":
        parts.append("No problem, I won't send a summary. Thanks for contacting us.")
    elif situation == "summary_send_failed":
        parts.append("I couldn't send the summary just now. Nothing was sent; you can try Send summary again or skip it.")
    else:
        parts.append("How can I help with your claim?")
    return " ".join(part for part in parts if part).replace(" \n", "\n")


def _answer(brief: dict[str, Any], name: str | None) -> str:
    facts = brief["facts"]
    followups = [g["text"] for g in brief.get("guidance", []) if g["topic"].startswith("followup:")]
    if "case_selected" not in brief.get("notes", []) and followups:
        # A follow-up question on the same claim: answer it without restating everything.
        answer = followups[0] if followups[0].startswith("For claim") else f"For claim {facts['case_id']}: {followups[0]}"
        return f"{answer} Is there anything else I can help with?"
    lead = f"Thanks{', ' + name if name else ''}, you're verified. " if "just_verified" in brief.get("notes", []) else ""
    lines = [f"{lead}Claim {facts['case_id']} ({facts['case_type']}), filed {facts['filed']}, is {facts['status']}."]
    if "denial_reason" in facts:
        lines.append(f"It was denied because {facts['denial_reason']}.")
    if "documents_needed" in facts:
        lines.append(f"Documents needed: {', '.join(facts['documents_needed'])}.")
    if "appeal_deadline" in facts:
        if facts["appeal_deadline_passed"]:
            lines.append(f"The appeal deadline was {facts['appeal_deadline']}, which has passed.")
        else:
            lines.append(
                f"The appeal deadline is {facts['appeal_deadline']}, {facts['days_until_appeal_deadline']} days from today ({facts['business_date']})."
            )
    if followups:
        lines.append(followups[0])
    lines.append("Is there anything else about this claim I can help with?")
    return " ".join(lines)
