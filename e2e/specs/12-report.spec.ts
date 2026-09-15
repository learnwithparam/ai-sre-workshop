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

  // Tool calls and tokens are per conversation; "to proposal" stops at the first propose_remediation.
  const scenario = (s: { conversationId: string; openedAt: number; proposedAt: number }) => {
    const calls = chatToolCalls(s.conversationId);
    return {
      tool_calls_to_proposal: calls.findIndex((c) => c.startsWith("propose_remediation")) + 1,
      tool_calls_total: calls.length,
      tokens: chatTokens(s.conversationId),
      time_to_root_cause_s: Math.round((s.proposedAt - s.openedAt) / 1000),
    };
  };
  const report = {
    model,
    generated_at: new Date().toISOString(),
    // OpenRouter bills per key, so cost is measured across both investigations together.
    total_cost_usd: Number((usageAfter - run.badRelease.usageBefore).toFixed(4)),
    bad_release: scenario(run.badRelease),
    docs_hang: scenario(run.docsHang),
  };

  for (const s of [report.bad_release, report.docs_hang]) {
    expect(s.tool_calls_to_proposal).toBeGreaterThanOrEqual(3);
    expect(s.tokens).toBeGreaterThan(0);
    expect(s.time_to_root_cause_s).toBeGreaterThan(0);
  }
  expect(report.total_cost_usd).toBeGreaterThan(0);
  mkdirSync(resolve(ROOT, "evidence"), { recursive: true });
  writeFileSync(resolve(ROOT, "evidence/e2e-report.json"), `${JSON.stringify(report, null, 2)}\n`);
});
