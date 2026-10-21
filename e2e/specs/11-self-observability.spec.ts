import { clickhouse, state } from "../lib/stack";
import { expect, test } from "../lib/ui";

test("agent, MCP and control-plane spans land in ClickStack", async () => {
  const since = Math.floor(state.read().badRelease.openedAt);
  const rows = clickhouse<{ ServiceName: string; spans: string }>(
    `SELECT ServiceName, count() AS spans FROM default.otel_traces
     WHERE Timestamp >= fromUnixTimestamp64Milli(${since})
       AND ServiceName IN ('librechat', 'mcp-clickhouse', 'sre-control')
     GROUP BY ServiceName ORDER BY ServiceName LIMIT 10`,
  );
  expect(rows.map((r) => r.ServiceName)).toEqual(["librechat", "mcp-clickhouse", "sre-control"]);

  const [{ anthropic }] = clickhouse<{ anthropic: string }>(
    `SELECT count() AS anthropic FROM default.otel_traces
     WHERE Timestamp >= fromUnixTimestamp64Milli(${since}) AND ServiceName = 'librechat'
       AND (SpanAttributes['server.address'] = 'api.anthropic.com' OR SpanAttributes['net.peer.name'] = 'api.anthropic.com')`,
  );
  expect(Number(anthropic), "LLM calls are visible as spans").toBeGreaterThan(0);
});
