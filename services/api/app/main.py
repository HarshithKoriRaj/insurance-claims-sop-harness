"""HTTP API for the chat UI. Run with:
uvicorn app.main:create_app --factory --app-dir services/api"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.persistence.store import SessionNotFound, StaleSession
from app.ratelimit import RateLimiter, parse_limit
from app.runtime import Runtime, build_runtime
from app.settings import load_settings
from app.workflow.engine import ActionNotAvailable, mask_email
from app.workflow.state import SessionState

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class MessageIn(BaseModel):
    text: str = Field(min_length=1)


class ActionIn(BaseModel):
    action: Literal["send_summary", "skip_summary", "request_human", "end_conversation"]


def create_app(runtime: Runtime | None = None) -> FastAPI:
    rt = runtime or build_runtime(load_settings())
    app = FastAPI(title="Claims SOP harness", docs_url="/api/docs", openapi_url="/api/openapi.json")
    session_limiter = RateLimiter(*parse_limit(rt.settings.session_rate_limit))
    message_limiter = RateLimiter(*parse_limit(rt.settings.message_rate_limit))

    def throttle(limiter: RateLimiter, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many requests; please wait a minute and try again")

    def now() -> datetime:
        return rt.clock.now()

    def token_from(authorization: str | None) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing session token")
        return authorization.removeprefix("Bearer ").strip()

    def load(session_id: str, authorization: str | None) -> tuple[int, SessionState]:
        try:
            version, raw = rt.sessions.load(session_id, token_from(authorization))
        except SessionNotFound:
            raise HTTPException(404, "Session not found") from None
        return version, SessionState.model_validate_json(raw)

    def save(state: SessionState, version: int) -> None:
        try:
            rt.sessions.save(state.session_id, version, state.model_dump_json(), now())
        except StaleSession:
            raise HTTPException(409, "This conversation changed in another tab; reload it") from None

    def view(state: SessionState) -> dict[str, Any]:
        verification = rt.policy.verification
        holder = rt.fixtures.policyholder(state.verified_party_id) if state.verified_party_id else None
        selected = None
        if state.verified_party_id and state.selected_case_id:
            claim = rt.engine.access.claim_for(state.verified_party_id, state.selected_case_id)
            if claim:
                selected = {"case_id": claim.case_id, "case_type": claim.case_type, "status": claim.status}
        show_summary = state.summary.status in ("offered", "sent")
        return {
            "session_id": state.session_id,
            "phase": state.phase,
            "lifecycle": state.lifecycle,
            "messages": [m.model_dump(mode="json") for m in state.messages[state.visible_from:]],
            "verification": {
                "verified": state.verified_party_id is not None,
                "fields_provided": state.verified_fields if state.verified_party_id else list(state.evidence),
                "fields_required": verification.required_matching_fields,
                "failed_attempts": state.failed_attempts,
                "max_attempts": verification.max_failed_submissions,
            },
            "selected_case": selected,
            "memory": {
                "intent": state.intent,
                "followup_topic": state.followup_topic,
                "case_hints": state.case_hints.model_dump(),
            },
            "recovery": {"off_topic": state.off_topic_count, "refusals": state.refusal_count},
            "summary": {
                "status": state.summary.status,
                "subject": state.summary.subject if show_summary else None,
                "body": state.summary.body if show_summary else None,
                "recipient": mask_email(holder.email) if holder and show_summary else None,
                "delivered": state.summary.status == "sent" and bool(getattr(rt.mailer, "delivers", True)),
            },
            "available_actions": rt.engine.available_actions(state),
            "business_date": rt.clock.business_date().isoformat(),
            "model_mode": rt.conversation.mode,
        }

    def reply(state: SessionState, brief: Any) -> None:
        holder = rt.fixtures.policyholder(state.verified_party_id) if state.verified_party_id else None
        text = rt.conversation.respond(state, brief, holder)
        state.add_message("assistant", text, now())

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model": rt.settings.model, "model_mode": rt.conversation.mode}

    @app.post("/api/sessions", status_code=201)
    def create_session(request: Request) -> dict[str, Any]:
        throttle(session_limiter, request)
        session_id, token = rt.sessions.new_credentials()
        at = now()
        state = SessionState(session_id=session_id, created_at=at, last_activity_at=at)
        reply(state, rt.engine.start(state))
        rt.sessions.create(session_id, token, state.model_dump_json(), at)
        return {"session_id": session_id, "token": token, "view": view(state)}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _, state = load(session_id, authorization)
        return {"view": view(state)}

    @app.post("/api/sessions/{session_id}/messages")
    def post_message(
        session_id: str, body: MessageIn, request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        throttle(message_limiter, request)
        version, state = load(session_id, authorization)
        limits = rt.policy.session
        text = body.text.strip()
        if not text:
            raise HTTPException(422, "Message is empty")
        if len(text) > limits.max_input_characters:
            raise HTTPException(422, f"Message is longer than {limits.max_input_characters} characters")
        if sum(1 for m in state.messages if m.role == "user") >= limits.max_turns:
            state.lifecycle = "CLOSED"
        at = now()
        state.add_message("user", text, at)
        interpretation = rt.conversation.interpret(state, text)
        brief = rt.engine.on_message(state, interpretation, at)
        reply(state, brief)
        state.last_activity_at = at
        save(state, version)
        return {"view": view(state)}

    @app.post("/api/sessions/{session_id}/actions")
    def post_action(
        session_id: str, body: ActionIn, request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        throttle(message_limiter, request)
        version, state = load(session_id, authorization)
        at = now()
        try:
            brief = rt.engine.on_action(state, body.action, at)
        except ActionNotAvailable:
            raise HTTPException(409, "That action isn't available right now") from None
        reply(state, brief)
        state.last_activity_at = at
        save(state, version)
        return {"view": view(state)}

    dist = rt.settings.web_dist_dir
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app
