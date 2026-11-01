"""Human-in-the-loop remediation: the agent proposes, a human decides, the control plane acts.

Every transition is an event in the audit log, and state is derived from those events alone.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any, Protocol

from sre_control.policy import validate_action
from sre_control.store import Event, Store, new_id, utcnow

GROUNDING_HOURS = 6  # evidence must have been reported within this window
TRACE_LEAD = timedelta(minutes=15)  # a failing request can start just before the detector notices


class ApprovalRequired(PermissionError):
    pass


class InvalidTransition(ValueError):
    pass


class Ungrounded(ValueError):
    pass


@dataclass(frozen=True)
class TraceSeen:
    trace_id: str
    first_seen: datetime
    services: frozenset[str]


class Telemetry(Protocol):
    def trace_window(self, trace_ids: list[str]) -> list[TraceSeen]: ...
    def service_seen(self, service: str) -> bool: ...
    def release_seen(self, service: str, release: str) -> bool: ...


class Runner(Protocol):
    def run(self, action: str, target: str, params: dict[str, str]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ActionState:
    action_id: str
    incident_id: str
    state: str
    action: str
    target: str
    params: dict[str, str]
    root_cause: str
    service: str
    release: str
    trace_ids: list[str]
    proposed_by: str
    proposed_at: datetime
    result: dict[str, Any] | None = None
    verification: str | None = None
    history: list[Event] = field(default_factory=list)


class Remediations:
    def __init__(self, *, store: Store, telemetry: Telemetry, runner: Runner, clock: Callable = utcnow):
        self.store, self.telemetry, self.runner, self.clock = store, telemetry, runner, clock
        # One process runs the control plane; this lock makes a double click execute once.
        self._lock = threading.Lock()

    def propose(
        self,
        *,
        incident_id: str,
        action: str,
        target: str,
        params: dict[str, str],
        root_cause: str,
        service: str,
        release: str,
        trace_ids: list[str],
        proposed_by: str,
    ) -> ActionState:
        validate_action(action, target, params)
        # One live proposal per incident: a retried or repeated call returns the one already waiting,
        # so a human never sees two approval requests for the same outage.
        live = [a for a in self.actions_for(incident_id) if a.state in ("pending", "approved")]
        if live:
            return live[0]
        now = self.clock()
        # The model wrote "subscription-backend.v2" for release v2 and was refused three times
        # (e2e run of 21 Oct 2026); the service prefix adds nothing, so it is dropped.
        release = release.removeprefix(f"{service}.")
        self._ground(incident_id, service, release, trace_ids)
        action_id = new_id("act")
        payload = {
            "action": action,
            "target": target,
            "params": params,
            "root_cause": root_cause,
            "service": service,
            "release": release,
            "trace_ids": trace_ids,
        }
        self.store.append(Event(now, incident_id, action_id, "remediation_proposed", proposed_by, payload))
        return self.status(action_id)

    def _ground(self, incident_id: str, service: str, release: str, trace_ids: list[str]) -> None:
        """Evidence must exist, belong to this incident's service, and not predate the incident."""
        window = f"the last {GROUNDING_HOURS} hours"
        if not trace_ids:
            raise Ungrounded("cite at least one trace id returned by a tool")
        if not self.telemetry.service_seen(service):
            raise Ungrounded(f"service {service!r} has no telemetry in {window}")
        if release and not self.telemetry.release_seen(service, release):
            raise Ungrounded(f"release {release!r} of {service} has no telemetry in {window}")
        seen = {t.trace_id: t for t in self.telemetry.trace_window(trace_ids)}
        missing = [t for t in trace_ids if t not in seen]
        if missing:
            raise Ungrounded(f"these trace ids have no spans in {window}: {', '.join(missing)}")
        incident = self.store.incident(incident_id)
        too_old = [t for t in trace_ids if seen[t].first_seen < incident.opened_at - TRACE_LEAD]
        if too_old:
            raise Ungrounded(
                f"these traces began before this incident opened, so they cannot explain it: "
                f"{', '.join(too_old)}"
            )
        elsewhere = [t for t in trace_ids if incident.service not in seen[t].services]
        if elsewhere:
            raise Ungrounded(f"these traces never touched {incident.service}: {', '.join(elsewhere)}")

    def status(self, action_id: str) -> ActionState:
        events = self.store.events(action_id=action_id)
        if not events or events[0].kind != "remediation_proposed":
            raise KeyError(action_id)
        first = events[0]
        p = first.payload
        state = ActionState(
            action_id=action_id,
            incident_id=first.incident_id,
            state="pending",
            action=p["action"],
            target=p["target"],
            params=p["params"],
            root_cause=p["root_cause"],
            service=p["service"],
            release=p["release"],
            trace_ids=p["trace_ids"],
            proposed_by=first.actor,
            proposed_at=first.ts,
            history=events,
        )
        for e in events[1:]:
            match e.kind:
                case "remediation_approved":
                    state = replace(state, state="approved")
                case "remediation_rejected":
                    state = replace(state, state="rejected")
                case "remediation_expired":
                    state = replace(state, state="expired")
                case "remediation_edited":
                    state = replace(state, state="pending", **e.payload)
                case "remediation_executed":
                    state = replace(state, state="executed", result=e.payload.get("result"))
                case "remediation_failed":
                    state = replace(state, state="failed", result=e.payload.get("result"))
                case "verification_passed" | "verification_failed":
                    state = replace(state, verification=e.kind.removeprefix("verification_"))
        return state

    def actions_for(self, incident_id: str) -> list[ActionState]:
        proposed = self.store.events(incident_id=incident_id, kind="remediation_proposed")
        return [self.status(e.action_id) for e in proposed]

    def _decide(self, action_id: str, kind: str, actor: str, payload: dict, allowed_from: set[str]):
        with self._lock:
            current = self.status(action_id)
            if current.state not in allowed_from:
                raise InvalidTransition(f"{action_id} is {current.state}; cannot record {kind}")
            self.store.append(Event(self.clock(), current.incident_id, action_id, kind, actor, payload))
        return self.status(action_id)

    def approve(self, action_id: str, *, approver: str) -> ActionState:
        return self._decide(action_id, "remediation_approved", approver, {}, {"pending"})

    def reject(self, action_id: str, *, approver: str, reason: str) -> ActionState:
        return self._decide(action_id, "remediation_rejected", approver, {"reason": reason}, {"pending"})

    def expire(self, action_id: str, *, reason: str) -> ActionState:
        """The outage it answered is over, so approving it now would change a healthy system."""
        return self._decide(action_id, "remediation_expired", "sre-control", {"reason": reason}, {"pending"})

    def edit(self, action_id: str, *, editor: str, action: str, target: str, params: dict) -> ActionState:
        validate_action(action, target, params)
        # An edit can come long after the proposal; the evidence it still rests on must still exist.
        current = self.status(action_id)
        self._ground(current.incident_id, current.service, current.release, current.trace_ids)
        payload = {"action": action, "target": target, "params": params}
        return self._decide(action_id, "remediation_edited", editor, payload, {"pending", "rejected"})

    def execute(self, action_id: str, *, executed_by: str) -> dict[str, Any]:
        with self._lock:
            current = self.status(action_id)
            if current.state == "executed":
                return current.result or {}
            if current.state != "approved":
                self.store.append(
                    Event(self.clock(), current.incident_id, action_id, "remediation_refused", executed_by,
                          {"state": current.state})
                )  # fmt: skip
                raise ApprovalRequired(
                    f"{action_id} is {current.state}; a human must approve it at /actions/{action_id} first"
                )
            result = self.runner.run(current.action, current.target, current.params)
            kind = "remediation_executed" if result.get("exit_code") == 0 else "remediation_failed"
            payload = {"action": current.action, "target": current.target, "params": current.params}
            self.store.append(
                Event(
                    self.clock(),
                    current.incident_id,
                    action_id,
                    kind,
                    executed_by,
                    {**payload, "result": result},
                )
            )
            return result

    def record_verification(self, action_id: str, *, passed: bool, evidence: dict) -> None:
        current = self.status(action_id)
        kind = "verification_passed" if passed else "verification_failed"
        now = self.clock()
        self.store.append(Event(now, current.incident_id, action_id, kind, "sre-control", evidence))
        if passed:
            self.store.resolve_incident(
                current.incident_id,
                actor="sre-control",
                at=now,
                note="Recovery confirmed on a full minute of traffic after the approved change",
            )
