import { clickhouse, waitFor } from "../lib/stack";
import { expect, test } from "../lib/ui";

const WINDOW = "Timestamp > now() - INTERVAL 5 MINUTE";

test("traces and logs arrive for every app service", async () => {
  for (const [table, service] of [
    ["otel_traces", "subscription-backend"],
    ["otel_traces", "docs-loader"],
    ["otel_logs", "subscription-backend"],
    ["otel_logs", "docs-loader"],
  ]) {
    const rows = await waitFor(
      `${service} rows in ${table}`,
      () => {
        const [{ n }] = clickhouse<{ n: string }>(
          `SELECT count() AS n FROM default.${table} WHERE ServiceName = '${service}' AND ${WINDOW}`,
        );
        return Number(n) > 0 && Number(n);
      },
      120_000,
    );
    expect(rows, `${service} in ${table}`).toBeGreaterThan(0);
  }
});

test("docs-loader logs join traces by TraceId", async () => {
  const [{ joined }] = clickhouse<{ joined: string }>(
    `SELECT count() AS joined
     FROM default.otel_logs AS l
     INNER JOIN (SELECT DISTINCT TraceId FROM default.otel_traces WHERE ${WINDOW} LIMIT 10000) AS t
       ON l.TraceId = t.TraceId
     WHERE l.ServiceName = 'docs-loader' AND l.${WINDOW} AND l.TraceId != ''`,
  );
  expect(Number(joined)).toBeGreaterThan(0);
});
