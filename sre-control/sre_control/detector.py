"""Watches two signals, opens one incident per failure, and verifies recovery after a remediation."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sre_control.anomaly import error_rate, three_sigma
from sre_control.store import Store

log = logging.getLogger(__name__)

MIN_DELTA = 0.05  # an error-rate jump smaller than 5 points never pages anyone
MIN_REQUESTS = 10  # a minute with fewer requests says nothing
STUCK_AFTER_S = 20  # a docs request still open after 20 s is hung
RECOVERY_WINDOW = timedelta(seconds=60)  # recovery is judged only on traffic after the change
SELF_RECOVERY_AFTER = timedelta(minutes=2)  # an incident that heals on its own closes itself


@dataclass(frozen=True)
class ErrorRateSample:
    baseline: list[float]
    current: float
    requests: int


@dataclass(frozen=True)
class StuckRequests:
    count: int
    oldest_s: int


class ClickHouseSignals:
    def __init__(self, telemetry):
        self.telemetry = telemetry

    def error_rates(self, service: str) -> ErrorRateSample:
        (row,) = self.telemetry.rows("error_rate_window", service=service, baseline_minutes=10)
        current = error_rate(row["current_errors"], row["current_requests"])
        return ErrorRateSample(list(row["baseline"]), current, row["current_requests"])

    def stuck_requests(self, service: str) -> StuckRequests:
        (row,) = self.telemetry.rows("stuck_requests", service=service, older_than_s=STUCK_AFTER_S)
        return StuckRequests(row["stuck"], row["oldest_s"] or 0)


class Detector:
    def __init__(self, *, signals, store: Store, clock: Callable[[], datetime], remediations=None):
        self.signals, self.store, self.clock, self.remediations = signals, store, clock, remediations

    def tick(self) -> None:
        self._check_error_rate("subscription-backend")
        self._check_stuck("docs-loader")
        if self.remediations is not None:
            self._verify_executed()

    def _check_error_rate(self, service: str) -> None:
        sample = self.signals.error_rates(service)
        verdict = three_sigma(sample.baseline, sample.current, MIN_DELTA)
        if not verdict.anomalous or sample.requests < MIN_REQUESTS:
            return
        if self.store.open_incident_for("error_rate", service):
            return
        self.store.open_incident(
            rule="error_rate",
            service=service,
            summary=(
                f"{service} error rate {verdict.current:.0%} over the last minute, "
                f"above its 3 sigma bound of {verdict.bound:.1%} (baseline mean {verdict.mean:.1%})"
            ),
            opened_at=self.clock(),
            details={"current": verdict.current, "bound": verdict.bound, "mean": verdict.mean},
        )

    def _check_stuck(self, service: str) -> None:
        stuck = self.signals.stuck_requests(service)
        if stuck.count == 0 or self.store.open_incident_for("stuck_requests", service):
            return
        self.store.open_incident(
            rule="stuck_requests",
            service=service,
            summary=(
                f"{stuck.count} requests to {service} logged 'request received' and never "
                f"'request completed'; the oldest has been open {stuck.oldest_s}s"
            ),
            opened_at=self.clock(),
            details={"stuck": stuck.count, "oldest_s": stuck.oldest_s},
        )

    def _verify_executed(self) -> None:
        now = self.clock()
        for incident in self.store.incidents():
            if incident.state != "open":
                continue
            actions = self.remediations.actions_for(incident.id)
            if (
                not any(a.state == "executed" for a in actions)
                and now - incident.opened_at > SELF_RECOVERY_AFTER
            ):
                healthy, evidence = self._healthy(incident)
                if healthy:
                    note = f"signal recovered with no remediation executed: {evidence}"
                    self.store.resolve_incident(incident.id, actor="detector", at=now, note=note)
                continue
            for action in actions:
                if action.state != "executed" or action.verification is not None:
                    continue
                executed_at = next(e.ts for e in action.history if e.kind == "remediation_executed")
                if now - executed_at < RECOVERY_WINDOW:
                    continue
                healthy, evidence = self._healthy(incident)
                timed_out = now - executed_at > timedelta(minutes=5)
                if healthy or timed_out:
                    self.remediations.record_verification(action.action_id, passed=healthy, evidence=evidence)

    def _healthy(self, incident) -> tuple[bool, dict]:
        if incident.rule == "error_rate":
            sample = self.signals.error_rates(incident.service)
            limit = max(incident.details.get("bound", 0.0), MIN_DELTA)
            ok = sample.current < limit and sample.requests >= MIN_REQUESTS
            return ok, {"error_rate": sample.current, "limit": limit, "requests": sample.requests}
        stuck = self.signals.stuck_requests(incident.service)
        return stuck.count == 0, {"stuck": stuck.count}
