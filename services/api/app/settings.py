"""Runtime settings, read once from environment variables. Model API keys are read
here and nowhere else, and are never logged or returned by the API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
PROVIDERS = ("anthropic", "openai", "offline")


@dataclass(frozen=True)
class Settings:
    provider: str
    anthropic_api_key: str | None
    anthropic_model: str
    openai_api_key: str | None
    openai_model: str
    app_mode: str
    business_date_override: str | None
    database_path: Path
    fixtures_dir: Path
    policies_dir: Path
    web_dist_dir: Path
    smtp_host: str | None
    smtp_port: int
    mail_from: str

    @property
    def model(self) -> str:
        return {"anthropic": self.anthropic_model, "openai": self.openai_model}.get(self.provider, "rules")

    def __repr__(self) -> str:
        # Keep the keys out of tracebacks and logs.
        return f"Settings(provider={self.provider!r}, model={self.model!r}, app_mode={self.app_mode!r})"


def _provider(env: Mapping[str, str]) -> str:
    chosen = (env.get("LLM_PROVIDER") or "").strip().lower()
    if chosen:
        if chosen not in PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}")
        key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(chosen)
        if key and not env.get(key):
            raise ValueError(f"LLM_PROVIDER={chosen} needs {key}")
        return chosen
    if env.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if env.get("OPENAI_API_KEY"):
        return "openai"
    return "offline"


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    def path(name: str, default: Path) -> Path:
        return Path(env.get(name) or default)

    return Settings(
        provider=_provider(env),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        anthropic_model=env.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
        openai_api_key=env.get("OPENAI_API_KEY") or None,
        openai_model=env.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
        app_mode=env.get("APP_MODE") or "demo",
        # An empty value means unset, so a blank line in .env never becomes an override.
        business_date_override=env.get("BUSINESS_DATE_OVERRIDE") or None,
        database_path=path("DATABASE_PATH", ROOT / "data" / "sessions.sqlite3"),
        fixtures_dir=path("FIXTURES_DIR", ROOT / "fixtures"),
        policies_dir=path("POLICIES_DIR", ROOT / "policies"),
        web_dist_dir=path("WEB_DIST_DIR", ROOT / "apps" / "web" / "dist"),
        smtp_host=env.get("SMTP_HOST") or None,
        smtp_port=int(env.get("SMTP_PORT") or 1025),
        mail_from=env.get("MAIL_FROM") or "claims-assistant@example.com",
    )
