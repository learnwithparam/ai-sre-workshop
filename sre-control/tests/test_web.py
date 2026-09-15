"""The approval pages: login first, and every decision is recorded against the logged-in human."""

import pytest
from fastapi.testclient import TestClient

from sre_control.config import load_settings
from sre_control.web import create_app


@pytest.fixture
def settings():
    return load_settings(
        {
            "CLICKHOUSE_HOST": "clickstack",
            "CLICKHOUSE_READER_USER": "sre_agent",
            "CLICKHOUSE_READER_PASSWORD": "r",
            "CLICKHOUSE_WRITER_USER": "sre_control",
            "CLICKHOUSE_WRITER_PASSWORD": "w",
            "SRE_MCP_TOKEN": "mcp-token",
            "SRE_APPROVER_EMAIL": "oncall@example.com",
            "SRE_APPROVER_PASSWORD": "correct horse",
            "SRE_SESSION_SECRET": "session-secret",
            "SRE_PUBLIC_URL": "http://localhost:8090",
            "CHAT_PUBLIC_URL": "http://localhost:3080",
            "WORKSHOP_DIR": "/srv/ai-sre-workshop",
        }
    )


@pytest.fixture
def client(settings, remediations, store):
    app = create_app(settings=settings, remediations=remediations, store=store)
    with TestClient(app, follow_redirects=False) as c:
        yield c


def login(client):
    r = client.post("/login", data={"email": "oncall@example.com", "password": "correct horse"})
    assert r.status_code == 303


@pytest.mark.parametrize("path", ["/", "/incidents/abc", "/actions/abc"])
def test_pages_require_login(client, path):
    r = client.get(path)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login")


def test_wrong_password_is_refused(client):
    r = client.post("/login", data={"email": "oncall@example.com", "password": "guess"})
    assert r.status_code == 401


def test_mcp_requires_a_token(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


def test_approval_page_shows_the_evidence(client, rollback, known_trace):
    login(client)
    page = client.get(f"/actions/{rollback.action_id}").text
    for expected in ("rollback_release", "subscription-app", "exhausts the database pool", known_trace):
        assert expected in page


def test_approval_records_the_logged_in_approver(client, rollback, remediations, store):
    login(client)
    r = client.post(f"/actions/{rollback.action_id}/approve")
    assert r.status_code == 303
    assert remediations.status(rollback.action_id).state == "approved"
    (event,) = store.events(action_id=rollback.action_id, kind="remediation_approved")
    assert event.actor == "oncall@example.com"


def test_reject_then_edit_from_the_page(client, rollback, remediations):
    login(client)
    client.post(f"/actions/{rollback.action_id}/reject", data={"reason": "restart is enough"})
    assert remediations.status(rollback.action_id).state == "rejected"
    client.post(
        f"/actions/{rollback.action_id}/edit",
        data={"action": "restart_service", "target": "subscription-app"},
    )
    state = remediations.status(rollback.action_id)
    assert (state.state, state.action) == ("pending", "restart_service")


def test_decisions_require_login(client, rollback, remediations):
    r = client.post(f"/actions/{rollback.action_id}/approve")
    assert r.status_code == 303
    assert remediations.status(rollback.action_id).state == "pending"
