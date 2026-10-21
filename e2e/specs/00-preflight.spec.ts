import { execFileSync } from "node:child_process";
import { config } from "../lib/config";
import { clickhouse, state } from "../lib/stack";
import { expect, test } from "../lib/ui";

test("keys, ingest and memory are ready", async ({ request }) => {
  state.merge({ runStartedAt: new Date().toISOString() });

  const key = await request.get("https://api.anthropic.com/v1/models", {
    headers: { "x-api-key": config.anthropicKey, "anthropic-version": "2023-06-01" },
  });
  expect(key.status(), "ANTHROPIC_API_KEY is accepted by Anthropic").toBe(200);

  const ingest = await request.post(`${config.otlpUrl}/v1/logs`, {
    headers: { authorization: config.hyperdxKey, "content-type": "application/json" },
    data: { resourceLogs: [] },
  });
  expect(ingest.status(), "HYPERDX_API_KEY is accepted by the collector").toBe(200);

  const dockerBytes = Number(execFileSync("docker", ["info", "--format", "{{.MemTotal}}"], { encoding: "utf8" }));
  expect(dockerBytes, "Docker needs at least 7 GB of memory").toBeGreaterThan(7 * 1024 ** 3);
  expect(clickhouse("SELECT 1 AS ok")).toEqual([{ ok: 1 }]);
});
