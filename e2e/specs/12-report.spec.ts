import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { config, ROOT } from "../lib/config";
import { chatTokens, chatToolCalls, state } from "../lib/stack";
import { expect, test } from "../lib/ui";

test("report records tool calls, tokens, cost and time to root cause", async ({ request }) => {
  const run = state.read();
  const usage = await request.get("https://openrouter.ai/api/v1/key", {
    headers: { Authorization: `Bearer ${config.openrouterKey}` },
  });
  const usageAfter = (await usage.json()).data.usage as number;
  // The model id is written once, in the AI SRE model spec (tests/test_librechat.py pins that).
  const model = readFileSync(resolve(ROOT, "librechat/librechat.yaml"), "utf8").match(/^\s+model: (\S+)$/m)![1];

  const scenario = (s: { conversationId: string; openedAt: number; proposedAt: number }) => ({
    tool_calls: chatToolCalls(s.conversationId).length,
    tokens: chatTokens(s.conversationId),
    time_to_root_cause_s: Math.round((s.proposedAt - s.openedAt) / 1000),
  });
  const report = {
    model,
    generated_at: new Date().toISOString(),
    bad_release: {
      ...scenario(run.badRelease),
      // OpenRouter bills per key; the delta spans both investigations, attributed to the first.
      cost_usd: Number((usageAfter - run.badRelease.usageBefore).toFixed(4)),
    },
    docs_hang: scenario(run.docsHang),
  };

  for (const key of ["tool_calls", "tokens", "time_to_root_cause_s", "cost_usd"] as const) {
    expect(report.bad_release[key], key).toBeGreaterThan(0);
  }
  expect(report.docs_hang.tool_calls).toBeGreaterThan(0);
  mkdirSync(resolve(ROOT, "evidence"), { recursive: true });
  writeFileSync(resolve(ROOT, "evidence/e2e-report.json"), `${JSON.stringify(report, null, 2)}\n`);
});
