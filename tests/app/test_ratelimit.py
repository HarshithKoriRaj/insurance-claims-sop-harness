from fastapi.testclient import TestClient

from app.main import create_app
from app.ratelimit import RateLimiter, parse_limit
from app.runtime import build_runtime
from app.settings import load_settings


def test_a_sliding_window_allows_the_limit_then_refuses_until_it_slides():
    limiter = RateLimiter(2, 60)
    assert limiter.allow("a", now=0) and limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)  # per client
    assert limiter.allow("a", now=60.5)


def test_parse_limit():
    assert parse_limit("30/600") == (30, 600.0)


def test_a_refusal_says_how_long_until_the_oldest_request_leaves_the_window():
    limiter = RateLimiter(1, 600)
    assert limiter.check("a", now=100) == 0
    assert limiter.check("a", now=160) == 540


def test_the_api_returns_429_past_the_limits(tmp_path):
    settings = load_settings({
        "DATABASE_PATH": str(tmp_path / "s.sqlite3"),
        "WEB_DIST_DIR": str(tmp_path / "none"),
        "SESSION_RATE_LIMIT": "2/600",
        "MESSAGE_RATE_LIMIT": "3/60",
    })
    client = TestClient(create_app(build_runtime(settings)))
    first = client.post("/api/sessions").json()
    assert client.post("/api/sessions").status_code == 201
    refused = client.post("/api/sessions")
    assert refused.status_code == 429
    assert refused.headers["Retry-After"] == "600" and "about 10 minutes" in refused.json()["detail"]
    headers = {"Authorization": f"Bearer {first['token']}"}
    path = f"/api/sessions/{first['session_id']}/messages"
    codes = [client.post(path, json={"text": "hello"}, headers=headers).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
