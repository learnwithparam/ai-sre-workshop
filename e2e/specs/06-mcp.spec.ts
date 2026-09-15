import { config } from "../lib/config";
import { probe } from "../lib/stack";
import { expect, test } from "../lib/ui";

type ToolRun = { server: string; tool: string; ok: boolean; items: number; error: string | null };

test("every SRE read tool returns data", async () => {
  const runs = probe<ToolRun[]>("tools");
  const sre = runs.filter((r) => r.server === "sre");
  expect(sre.map((r) => r.tool).sort()).toEqual(
    [
      "event_patterns", "get_event_deltas", "get_incident", "get_remediation_status",
      "get_trace_waterfall", "list_incidents", "list_sources", "search_logs",
      "service_timeseries", "analyze_service_anomalies",
    ].sort(),
  ); // prettier-ignore
  for (const run of sre) {
    expect(run.error, run.tool).toBeNull();
    expect(run.items, run.tool).toBeGreaterThan(0);
  }
  const clickhouse = runs.filter((r) => r.server === "clickhouse");
  expect(clickhouse.find((r) => r.tool === "run_query")?.items).toBeGreaterThan(0);
});

test("MCP endpoints reject requests without a token", async ({ request }) => {
  const body = { jsonrpc: "2.0", id: 1, method: "tools/list" };
  const headers = { accept: "application/json, text/event-stream" };
  expect((await request.post(`${config.sreUrl}/mcp`, { data: body, headers })).status()).toBe(401);
  const unauthenticated = probe<{ server: string; status: number }[]>("no-token");
  expect(unauthenticated).toEqual([
    { server: "sre", status: 401 },
    { server: "clickhouse", status: 401 },
  ]);
});

test("mcp-clickhouse cannot write", async () => {
  const [result] = probe<{ ok: boolean; error: string }[]>("write-attempt");
  expect(result.ok).toBe(false);
  expect(result.error).toMatch(/read.?only|READONLY|not allowed|privileges/i);
});
