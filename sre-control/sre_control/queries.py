"""Loads the named SQL blocks from workshop/*.sql, the same files attendees write."""

import re
from dataclasses import dataclass, field
from pathlib import Path

# Which named query backs each read tool. tests/test_queries.py checks every one exists.
TOOL_QUERIES = {
    "list_sources": "list_services",
    "service_timeseries": "service_timeseries",
    "analyze_service_anomalies": "analyze_service_anomalies",
    "get_event_deltas": "get_event_deltas",
    "event_patterns": "event_patterns",
    "get_trace_waterfall": "get_trace_waterfall",
    "search_logs": "search_logs",
}

BLOCK = re.compile(r"^-- name: (\w+)\n(.*?)(?=^-- name: |\Z)", re.M | re.S)
EXAMPLE = re.compile(r"^-- example: (.*)$", re.M)


@dataclass(frozen=True)
class Query:
    name: str
    sql: str
    example: dict[str, str] = field(default_factory=dict)


def load_queries(directory: Path) -> dict[str, Query]:
    queries: dict[str, Query] = {}
    for path in sorted(Path(directory).glob("*.sql")):
        for name, body in BLOCK.findall(path.read_text()):
            if name in queries:
                raise ValueError(f"query {name} is defined twice")
            example = EXAMPLE.search(body)
            # key=value pairs; a value may contain spaces and runs until the next key=
            example_line = example.group(1) if example else ""
            pairs = dict(re.findall(r"(\w+)=(.*?)(?=\s+\w+=|$)", example_line))
            sql = "\n".join(line for line in body.splitlines() if not line.startswith("--")).strip()
            queries[name] = Query(name=name, sql=sql.rstrip(";").strip(), example=pairs)
    return queries
