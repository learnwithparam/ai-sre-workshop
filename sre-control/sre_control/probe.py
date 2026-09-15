"""Diagnostics run inside the sre-control container, where the whole stack network is reachable.

python -m sre_control.probe sql                         run every workshop query as sre_agent
python -m sre_control.probe tools INCIDENT_ID ACTION_ID  call every read tool on both MCP servers
python -m sre_control.probe no-token                     POST to both MCP servers without a token
python -m sre_control.probe write-attempt                ask mcp-clickhouse to INSERT
Prints JSON on stdout for the e2e suite.
"""

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

from fastmcp import Client

from sre_control.config import load_settings
from sre_control.main import clickhouse
from sre_control.queries import load_queries
from sre_control.telemetry import ClickHouseTelemetry

SERVERS = {
    "sre": ("http://localhost:8090/mcp", "SRE_MCP_TOKEN"),
    "clickhouse": ("http://mcp-clickhouse:8000/mcp", "CLICKHOUSE_MCP_AUTH_TOKEN"),
}


def run_sql() -> list[dict]:
    settings = load_settings(os.environ)
    queries = load_queries(settings.workshop_sql)
    telemetry = ClickHouseTelemetry(
        clickhouse(settings, settings.reader_user, settings.reader_password), queries
    )
    trace_ids = [r["trace_id"] for r in telemetry.rows("sample_error_traces", service="subscription-backend",
                                                        minutes=60)]  # fmt: skip
    results = []
    for name, query in queries.items():
        if name.startswith("create_"):
            continue
        params = {}
        for key, value in query.example.items():
            if value == "@sample_error_traces":
                params[key] = trace_ids if key == "trace_ids" else trace_ids[0]
            else:
                params[key] = value
        try:
            results.append({"name": name, "rows": len(telemetry.rows(name, **params)), "error": None})
        except Exception as err:  # the e2e report needs every failure, not the first one
            results.append({"name": name, "rows": 0, "error": str(err)[:500]})
    return results


def count(data) -> int:
    if isinstance(data, dict):
        return sum(count(v) for v in data.values()) or len(data)
    if isinstance(data, list):
        return len(data)
    return 1 if data not in (None, "") else 0


async def call_tools(incident_id: str, action_id: str) -> list[dict]:
    settings = load_settings(os.environ)
    telemetry = ClickHouseTelemetry(
        clickhouse(settings, settings.reader_user, settings.reader_password),
        load_queries(settings.workshop_sql),
    )
    trace_id = telemetry.rows("sample_error_traces", service="subscription-backend", minutes=60)[0][
        "trace_id"
    ]
    calls = {
        "sre": [
            ("list_sources", {}),
            ("service_timeseries", {"service": "subscription-backend"}),
            ("analyze_service_anomalies", {}),
            ("get_event_deltas", {"service": "subscription-backend"}),
            ("event_patterns", {"service": "docs-loader"}),
            ("get_trace_waterfall", {"trace_id": trace_id}),
            ("search_logs", {"service": "subscription-backend", "text": "GET"}),
            ("list_incidents", {"state": "all"}),
            ("get_incident", {"incident_id": incident_id}),
            ("get_remediation_status", {"action_id": action_id}),
        ],
        "clickhouse": [
            ("run_query", {"query": "SELECT ServiceName, count() FROM default.otel_traces GROUP BY 1"})
        ],
    }
    results = []
    for server, tool_calls in calls.items():
        url, token_env = SERVERS[server]
        async with Client(url, auth=os.environ[token_env]) as client:
            for tool, args in tool_calls:
                try:
                    r = await client.call_tool(tool, args)
                    data = r.structured_content if r.structured_content is not None else r.content[0].text
                    if isinstance(data, str):
                        data = json.loads(data)
                    results.append(
                        {"server": server, "tool": tool, "ok": True, "items": count(data), "error": None}
                    )
                except Exception as err:
                    results.append(
                        {"server": server, "tool": tool, "ok": False, "items": 0, "error": str(err)}
                    )
    return results


def no_token() -> list[dict]:
    results = []
    for server, (url, _) in SERVERS.items():
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
        request = urllib.request.Request(  # noqa: S310  fixed internal URLs
            url,
            data=body,
            headers={"content-type": "application/json", "accept": "application/json, text/event-stream"},
        )
        try:
            status = urllib.request.urlopen(request, timeout=5).status  # noqa: S310
        except urllib.error.HTTPError as err:
            status = err.code
        results.append({"server": server, "status": status})
    return results


async def write_attempt() -> list[dict]:
    url, token_env = SERVERS["clickhouse"]
    async with Client(url, auth=os.environ[token_env]) as client:
        try:
            r = await client.call_tool(
                "run_query", {"query": "INSERT INTO sre.incident_events (kind) VALUES ('forged')"}
            )
            text = r.content[0].text
            return [{"ok": "error" not in text.lower(), "error": text[:500]}]
        except Exception as err:
            return [{"ok": False, "error": str(err)[:500]}]


def main(argv: list[str]) -> None:
    command = argv[0]
    if command == "sql":
        out = run_sql()
    elif command == "tools":
        out = asyncio.run(call_tools(argv[1], argv[2]))
    elif command == "no-token":
        out = no_token()
    elif command == "write-attempt":
        out = asyncio.run(write_attempt())
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1:])
