from datetime import UTC, datetime, timedelta

import pytest

# sre_control is imported inside fixtures, so a broken module fails its own tests and
# never aborts collection for the whole gate (which would zero every phase of the score).

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
KNOWN_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


class FakeTelemetry:
    """Telemetry that knows one service, one release and one failing trace."""

    services = {"subscription-backend": {"v1", "v2"}, "docs-loader": {"1.0.0"}}
    traces = {KNOWN_TRACE}

    def missing_trace_ids(self, trace_ids):
        return [t for t in trace_ids if t not in self.traces]

    def service_seen(self, service):
        return service in self.services

    def release_seen(self, service, release):
        return release in self.services.get(service, set())


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, action, target, params):
        self.calls.append((action, target, dict(params)))
        return {"exit_code": 0, "output": f"{action} {target} ok"}


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def known_trace():
    return KNOWN_TRACE


@pytest.fixture
def store():
    from sre_control.store import MemoryStore

    return MemoryStore()


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def remediations(store, runner):
    from sre_control.approvals import Remediations

    return Remediations(store=store, telemetry=FakeTelemetry(), runner=runner, clock=Clock())


@pytest.fixture
def incident(store):
    return store.open_incident(
        rule="error_rate",
        service="subscription-backend",
        summary="error rate 34% against a 3 sigma bound of 2%",
        opened_at=NOW,
    )


@pytest.fixture
def rollback(remediations, incident):
    return remediations.propose(
        incident_id=incident.id,
        action="rollback_release",
        target="subscription-app",
        params={"release": "v1"},
        root_cause="Release v2 of subscription-backend exhausts the database pool on /api/subscribe",
        service="subscription-backend",
        release="v2",
        trace_ids=[KNOWN_TRACE],
        proposed_by="ai-sre",
    )
