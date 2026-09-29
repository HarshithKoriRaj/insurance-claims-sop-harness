import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime import build_runtime
from app.settings import load_settings


class RecordingMailer:
    def __init__(self):
        self.sent = {}

    def send(self, summary_id, to, subject, body):
        self.sent.setdefault(summary_id, (to, subject, body))


class Chat:
    def __init__(self, client):
        self.client = client
        response = client.post("/api/sessions")
        assert response.status_code == 201, response.text
        data = response.json()
        self.session_id = data["session_id"]
        self.headers = {"Authorization": f"Bearer {data['token']}"}
        self.view = data["view"]

    def say(self, text):
        response = self.client.post(f"/api/sessions/{self.session_id}/messages", json={"text": text}, headers=self.headers)
        assert response.status_code == 200, response.text
        self.view = response.json()["view"]
        return self.last_reply

    def act(self, action, expect=200):
        response = self.client.post(f"/api/sessions/{self.session_id}/actions", json={"action": action}, headers=self.headers)
        assert response.status_code == expect, response.text
        if expect == 200:
            self.view = response.json()["view"]
        return response

    @property
    def last_reply(self):
        return self.view["messages"][-1]["text"]

    @property
    def transcript(self):
        return "\n".join(m["text"] for m in self.view["messages"])


@pytest.fixture
def mailer():
    return RecordingMailer()


@pytest.fixture
def runtime(mailer, tmp_path):
    settings = load_settings(
        {"DATABASE_PATH": str(tmp_path / "sessions.sqlite3"), "WEB_DIST_DIR": str(tmp_path / "no-web")}
    )
    return build_runtime(settings, mailer=mailer)


@pytest.fixture
def client(runtime):
    return TestClient(create_app(runtime))


@pytest.fixture
def chat(client):
    return Chat(client)
