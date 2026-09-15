"""Read-only access to ClickStack telemetry, always as the sre_agent user, always via workshop SQL."""

from typing import Any

from sre_control.approvals import GROUNDING_HOURS
from sre_control.queries import Query


class ClickHouseTelemetry:
    def __init__(self, client, queries: dict[str, Query]):
        self.client, self.queries = client, queries

    def rows(self, name: str, **params: Any) -> list[dict[str, Any]]:
        result = self.client.query(self.queries[name].sql, parameters=params)
        return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]

    def missing_trace_ids(self, trace_ids: list[str]) -> list[str]:
        rows = self.rows("known_trace_ids", trace_ids=trace_ids, hours=GROUNDING_HOURS)
        found = {r["trace_id"] for r in rows}
        return [t for t in trace_ids if t not in found]

    def releases(self, service: str) -> set[str]:
        return {r["release"] for r in self.rows("service_releases", service=service, hours=GROUNDING_HOURS)}

    def service_seen(self, service: str) -> bool:
        return bool(self.releases(service))

    def release_seen(self, service: str, release: str) -> bool:
        return release in self.releases(service)
