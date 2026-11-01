"""Read-only access to ClickStack telemetry, always as the sre_agent user, always via workshop SQL."""

from datetime import UTC
from typing import Any

from sre_control.approvals import GROUNDING_HOURS, TraceSeen
from sre_control.queries import Query


class ClickHouseTelemetry:
    def __init__(self, client, queries: dict[str, Query]):
        self.client, self.queries = client, queries

    def rows(self, name: str, **params: Any) -> list[dict[str, Any]]:
        result = self.client.query(self.queries[name].sql, parameters=params)
        return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]

    def trace_window(self, trace_ids: list[str]) -> list[TraceSeen]:
        rows = self.rows("trace_window", trace_ids=trace_ids, hours=GROUNDING_HOURS)
        return [
            TraceSeen(r["trace_id"], r["first_seen"].replace(tzinfo=r["first_seen"].tzinfo or UTC), frozenset(r["services"]))
            for r in rows
        ]

    def releases(self, service: str) -> set[str]:
        return {r["release"] for r in self.rows("service_releases", service=service, hours=GROUNDING_HOURS)}

    def service_seen(self, service: str) -> bool:
        return bool(self.releases(service))

    def release_seen(self, service: str, release: str) -> bool:
        return release in self.releases(service)
