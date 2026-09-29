"""Composition root: loads policy and fixtures once at startup and wires the services.
Bad data or a policy that would strand a policyholder fails here, at boot."""

from __future__ import annotations

from dataclasses import dataclass

from app.claims.access import ClaimAccess
from app.claims.documents import load_document_catalog
from app.claims.guidance import GuidanceLibrary
from app.claims.importer import FixtureStore, load_fixtures
from app.clock import Clock, build_clock
from app.conversation.claude import ClaudeModel
from app.conversation.openai_model import OpenAIModel
from app.conversation.service import ConversationModel, ConversationService
from app.identity.fields import check_every_record_can_verify
from app.persistence.store import SessionStore
from app.policies import Policy, load_policy
from app.settings import Settings
from app.summaries.mailer import SmtpMailer
from app.workflow.engine import Mailer, WorkflowEngine


@dataclass
class Runtime:
    settings: Settings
    policy: Policy
    fixtures: FixtureStore
    clock: Clock
    sessions: SessionStore
    engine: WorkflowEngine
    conversation: ConversationService
    mailer: Mailer


def build_model(settings: Settings) -> ConversationModel | None:
    if settings.provider == "anthropic" and settings.anthropic_api_key:
        return ClaudeModel(settings.anthropic_api_key, settings.anthropic_model)
    if settings.provider == "openai" and settings.openai_api_key:
        return OpenAIModel(settings.openai_api_key, settings.openai_model)
    return None


def build_runtime(settings: Settings, *, model: ConversationModel | None = None, mailer: Mailer | None = None) -> Runtime:
    policy = load_policy(settings.policies_dir / "defaults.toml")
    catalog = load_document_catalog(settings.policies_dir / "document_codes.toml")
    fixtures = load_fixtures(settings.fixtures_dir, catalog)
    check_every_record_can_verify(fixtures.policyholders, policy.verification)
    library = GuidanceLibrary(fixtures.guideline, catalog)
    clock = build_clock(settings.app_mode, policy, settings.business_date_override)
    sessions = SessionStore(settings.database_path)
    mailer = mailer or SmtpMailer(settings.database_path, settings.smtp_host, settings.smtp_port, settings.mail_from)
    model = model or build_model(settings)
    engine = WorkflowEngine(policy, fixtures, ClaimAccess(fixtures, library), clock, mailer)
    return Runtime(settings, policy, fixtures, clock, sessions, engine, ConversationService(model, library), mailer)
