"""The audit log. Every incident and remediation is an append-only stream of events; state is derived.

Append-only means the record of who decided what, and when, can never be edited after the fact.
"""

import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class Event:
    ts: datetime
    incident_id: str
    action_id: str
    kind: str
    actor: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Incident:
    id: str
    rule: str
    service: str
    summary: str
    opened_at: datetime
    state: str
    details: dict[str, Any]
    resolved_at: datetime | None = None


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


class Store:
    """Derivations shared by every backend. Subclasses implement append() and events()."""

    def append(self, event: Event) -> None:
        raise NotImplementedError

    def events(
        self, *, incident_id: str | None = None, action_id: str | None = None, kind: str | None = None
    ) -> list[Event]:
        raise NotImplementedError

    def open_incident(
        self, *, rule: str, service: str, summary: str, opened_at: datetime, details: dict | None = None
    ) -> Incident:
        incident_id = new_id("inc")
        payload = {"rule": rule, "service": service, "summary": summary, "details": details or {}}
        self.append(Event(opened_at, incident_id, "", "incident_opened", "detector", payload))
        return self.incident(incident_id)

    def resolve_incident(self, incident_id: str, *, actor: str, at: datetime, note: str) -> None:
        self.append(Event(at, incident_id, "", "incident_resolved", actor, {"note": note}))

    def incident(self, incident_id: str) -> Incident:
        events = self.events(incident_id=incident_id)
        opened = next((e for e in events if e.kind == "incident_opened"), None)
        if opened is None:
            raise KeyError(incident_id)
        resolved = next((e for e in events if e.kind == "incident_resolved"), None)
        p = opened.payload
        return Incident(
            id=incident_id,
            rule=p["rule"],
            service=p["service"],
            summary=p["summary"],
            opened_at=opened.ts,
            state="resolved" if resolved else "open",
            details=p.get("details", {}),
            resolved_at=resolved.ts if resolved else None,
        )

    def incidents(self) -> list[Incident]:
        opened = self.events(kind="incident_opened")
        return [self.incident(e.incident_id) for e in sorted(opened, key=lambda e: e.ts, reverse=True)]

    def incident_windows(
        self, rule: str, service: str, *, now: datetime, margin: timedelta
    ) -> list[tuple[datetime, datetime]]:
        return [
            (i.opened_at - margin, (i.resolved_at or now) + margin)
            for i in self.incidents()
            if (i.rule, i.service) == (rule, service)
        ]

    def open_incident_for(self, rule: str, service: str) -> Incident | None:
        for incident in self.incidents():
            if (incident.rule, incident.service, incident.state) == (rule, service, "open"):
                return incident
        return None


class MemoryStore(Store):
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def events(self, *, incident_id=None, action_id=None, kind=None) -> list[Event]:
        return sorted(
            (
                e
                for e in self._events
                if (incident_id is None or e.incident_id == incident_id)
                and (action_id is None or e.action_id == action_id)
                and (kind is None or e.kind == kind)
            ),
            key=lambda e: e.ts,
        )


SCHEMA = """
CREATE TABLE IF NOT EXISTS sre.incident_events
(
    ts DateTime64(3, 'UTC'),
    incident_id String,
    action_id String,
    kind LowCardinality(String),
    actor String,
    payload String
)
ENGINE = MergeTree
ORDER BY (incident_id, ts)
"""


class ClickHouseStore(Store):
    """Writes as sre_control, the only user allowed to insert into the sre database."""

    def __init__(self, client) -> None:
        self.client = client

    def migrate(self, statements: list[str]) -> None:
        self.client.command("CREATE DATABASE IF NOT EXISTS sre")
        for sql in [SCHEMA, *statements]:
            self.client.command(sql)

    def append(self, event: Event) -> None:
        self.client.insert(
            "sre.incident_events",
            [
                [
                    event.ts,
                    event.incident_id,
                    event.action_id,
                    event.kind,
                    event.actor,
                    json.dumps(event.payload),
                ]
            ],
            column_names=["ts", "incident_id", "action_id", "kind", "actor", "payload"],
        )

    def events(self, *, incident_id=None, action_id=None, kind=None) -> list[Event]:
        # An empty parameter means "any", so the SQL text is fixed and every value is bound.
        params = {"incident_id": incident_id or "", "action_id": action_id or "", "kind": kind or ""}
        rows = self.client.query(
            """SELECT ts, incident_id, action_id, kind, actor, payload FROM sre.incident_events
               WHERE ({incident_id:String} = '' OR incident_id = {incident_id:String})
                 AND ({action_id:String} = '' OR action_id = {action_id:String})
                 AND ({kind:String} = '' OR kind = {kind:String})
               ORDER BY ts LIMIT 10000""",
            parameters=params,
        ).result_rows
        return [
            Event(ts.replace(tzinfo=UTC), i, a, k, actor, json.loads(p)) for ts, i, a, k, actor, p in rows
        ]


def utcnow() -> datetime:
    return datetime.now(UTC)
