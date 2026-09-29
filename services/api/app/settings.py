"""Runtime settings, read once from environment variables. The model API key is read
here and nowhere else, and is never logged or returned by the API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    model: str
    app_mode: str
    business_date_override: str | None
    database_path: Path
    fixtures_dir: Path
    policies_dir: Path
    web_dist_dir: Path
    smtp_host: str | None
    smtp_port: int
    mail_from: str

    def __repr__(self) -> str:
        # Keep the key out of tracebacks and logs.
        key = "set" if self.anthropic_api_key else "missing"
        return f"Settings(model={self.model!r}, app_mode={self.app_mode!r}, api_key={key})"


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    def path(name: str, default: Path) -> Path:
        return Path(env.get(name) or default)

    return Settings(
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        model=env.get("ANTHROPIC_MODEL") or DEFAULT_MODEL,
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
