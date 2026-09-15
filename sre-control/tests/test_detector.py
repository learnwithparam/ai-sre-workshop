"""The detector opens one incident per failing signal, and a fresh one only after resolution."""

from datetime import UTC, datetime, timedelta

from sre_control.detector import Detector, ErrorRateSample, StuckRequests

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
STEADY = [0.01, 0.012, 0.009, 0.011, 0.01, 0.013, 0.008, 0.01, 0.011, 0.012]


class Signals:
    def __init__(self):
        self.current = 0.01
        self.stuck = 0

    def error_rates(self, service):
        return ErrorRateSample(baseline=STEADY, current=self.current, requests=120)

    def stuck_requests(self, service):
        return StuckRequests(count=self.stuck, oldest_s=45 if self.stuck else 0)


def detector(store, signals):
    return Detector(signals=signals, store=store, clock=lambda: NOW)


def test_quiet_signals_open_nothing(store):
    detector(store, Signals()).tick()
    assert store.incidents() == []


def test_error_spike_opens_one_incident(store):
    signals = Signals()
    signals.current = 0.34
    d = detector(store, signals)
    d.tick()
    d.tick()
    (incident,) = store.incidents()
    assert (incident.rule, incident.service, incident.state) == ("error_rate", "subscription-backend", "open")
    assert "34%" in incident.summary


def test_stuck_requests_open_an_incident(store):
    signals = Signals()
    signals.stuck = 6
    detector(store, signals).tick()
    (incident,) = store.incidents()
    assert (incident.rule, incident.service) == ("stuck_requests", "docs-loader")


def test_a_resolved_incident_lets_a_new_one_open(store):
    signals = Signals()
    signals.current = 0.34
    d = detector(store, signals)
    d.tick()
    (first,) = store.incidents()
    store.resolve_incident(first.id, actor="ai-sre", at=NOW, note="rolled back")
    d.tick()
    assert len(store.incidents()) == 2


def test_an_incident_that_heals_on_its_own_closes_itself(store, remediations):
    signals = Signals()
    signals.current = 0.34
    now = [NOW]
    d = Detector(signals=signals, store=store, clock=lambda: now[0], remediations=remediations)
    d.tick()
    signals.current = 0.01
    now[0] = NOW + timedelta(minutes=1)
    d.tick()
    assert store.incidents()[0].state == "open"
    now[0] = NOW + timedelta(minutes=3)
    d.tick()
    (incident,) = store.incidents()
    assert incident.state == "resolved"
    (resolved,) = store.events(incident_id=incident.id, kind="incident_resolved")
    assert resolved.actor == "detector"
