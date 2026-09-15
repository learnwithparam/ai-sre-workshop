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

  const [{ openrouter }] = clickhouse<{ openrouter: string }>(
    `SELECT count() AS openrouter FROM default.otel_traces
     WHERE Timestamp >= fromUnixTimestamp64Milli(${since}) AND ServiceName = 'librechat'
       AND (SpanAttributes['server.address'] = 'openrouter.ai' OR SpanAttributes['net.peer.name'] = 'openrouter.ai')`,
  );
  expect(Number(openrouter), "LLM calls are visible as spans").toBeGreaterThan(0);
});
