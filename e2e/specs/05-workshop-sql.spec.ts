import { clickhouse, clickhouseError, probe } from "../lib/stack";
import { expect, test } from "../lib/ui";

type QueryRun = { name: string; rows: number; error: string | null };

test("every workshop query runs as sre_agent", async () => {
  const runs = probe<QueryRun[]>("sql");
  expect(runs.length).toBeGreaterThanOrEqual(8);
  for (const run of runs) {
    expect(run.error, run.name).toBeNull();
  }
  const silent = runs.filter((r) => r.rows === 0 && !r.name.startsWith("create_")).map((r) => r.name);
  expect(silent, "queries that returned no rows").toEqual([]);
});

test("sre_agent cannot write", async () => {
  expect(clickhouseError("INSERT INTO sre.incident_events (kind) VALUES ('forged')")).toMatch(
    /READONLY|Not enough privileges|readonly/i,
  );
  expect(clickhouseError("DROP TABLE default.otel_logs")).toMatch(/READONLY|Not enough privileges|readonly/i);
});

test("anomaly materialized view is populated", async () => {
  const [{ buckets }] = clickhouse<{ buckets: string }>(
    `SELECT count() AS buckets FROM sre.service_minute
     WHERE minute > now() - INTERVAL 10 MINUTE AND ServiceName = 'subscription-backend'`,
  );
  expect(Number(buckets)).toBeGreaterThan(0);
});
