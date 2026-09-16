"""Watches two signals, opens one incident per failure, and verifies recovery after a remediation."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sre_control.anomaly import clean_baseline, error_rate, three_sigma
from sre_control.store import Store

log = logging.getLogger(__name__)

MIN_DELTA = 0.05  # an error-rate jump smaller than 5 points never pages anyone
MIN_REQUESTS = 10  # a minute with fewer requests says nothing
MIN_BASELINE_BUCKETS = 12  # two clean minutes of 10 s buckets before 3 sigma is trusted
SLO_ERROR_RATE = 0.10  # the fixed ceiling that still pages when there is no clean baseline yet
INCIDENT_MARGIN = timedelta(minutes=1)  # buckets this close to a past incident are not baseline
STUCK_AFTER_S = 20  # a docs request still open after 20 s is hung
RECOVERY_WINDOW = timedelta(seconds=60)  # recovery is judged only on traffic after the change
SELF_RECOVERY_AFTER = timedelta(minutes=2)  # an incident that heals on its own closes itself


@dataclass(frozen=True)
class ErrorRateSample:
    buckets: list[tuple[datetime, float]]  # baseline buckets, before past incidents are removed
    current: float
    requests: int


@dataclass(frozen=True)
class StuckRequests:
    count: int
    oldest_s: int
    trace_ids: list[str] = field(default_factory=list)


class ClickHouseSignals:
    def __init__(self, telemetry):
        self.telemetry = telemetry

    def error_rates(self, service: str) -> ErrorRateSample:
        (row,) = self.telemetry.rows("error_rate_window", service=service, baseline_minutes=15)
        current = error_rate(row["current_errors"], row["current_requests"])
        buckets = [(at.replace(tzinfo=UTC), rate) for at, rate in row["baseline"]]
        return ErrorRateSample(buckets, current, row["current_requests"])

    def stuck_requests(self, service: str) -> StuckRequests:
        (row,) = self.telemetry.rows("stuck_requests", service=service, older_than_s=STUCK_AFTER_S)
        return StuckRequests(row["stuck"], row["oldest_s"] or 0, list(row["example_trace_ids"]))


class Detector:
    def __init__(self, *, signals, store: Store, clock: Callable[[], datetime], remediations=None):
        self.signals, self.store, self.clock, self.remediations = signals, store, clock, remediations

    def tick(self) -> None:
        self._check_error_rate("subscription-backend")
        self._check_stuck("docs-loader")
        if self.remediations is not None:
            self._verify_executed()

    def _check_error_rate(self, service: str) -> None:
        now = self.clock()
        sample = self.signals.error_rates(service)
        if sample.requests < MIN_REQUESTS or self.store.open_incident_for("error_rate", service):
            return
        windows = self.store.incident_windows("error_rate", service, now=now, margin=INCIDENT_MARGIN)
        baseline = clean_baseline(sample.buckets, windows)
        verdict = three_sigma(baseline, sample.current, MIN_DELTA)
        if len(baseline) >= MIN_BASELINE_BUCKETS and verdict.anomalous:
            why = (
                f"above its 3 sigma bound of {verdict.bound:.1%} "
                f"(mean {verdict.mean:.1%} over {len(baseline)} clean 10 s buckets)"
            )
            bound = verdict.bound
        elif sample.current >= SLO_ERROR_RATE:
            if len(baseline) < MIN_BASELINE_BUCKETS:
                reason = f"only {len(baseline)} clean baseline buckets, too few for 3 sigma"
            else:
                reason = f"the baseline itself is elevated, mean {verdict.mean:.1%}"
            why = f"above the {SLO_ERROR_RATE:.0%} SLO ceiling ({reason})"
            bound = 0.0
        else:
            return
        self.store.open_incident(
            rule="error_rate",
            service=service,
            summary=f"{service} error rate {sample.current:.0%} over the last minute, {why}",
            opened_at=now,
            details={"current": sample.current, "bound": bound, "baseline_buckets": len(baseline)},
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
            details={"stuck": stuck.count, "oldest_s": stuck.oldest_s, "trace_ids": stuck.trace_ids},
        )

    def _verify_executed(self) -> None:
        now = self.clock()
        for incident in self.store.incidents():
            if incident.state != "open":
                continue
            actions = self.remediations.actions_for(incident.id)
            # Nothing is waiting on a verdict: either nothing ran, or what ran has been judged.
            # Without the second case a failed verification would hold the incident open forever,
            # and an open incident stops the same signal from ever opening the next one.
            awaiting = [a for a in actions if a.state == "executed" and a.verification is None]
            if not awaiting and now - incident.opened_at > SELF_RECOVERY_AFTER:
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
