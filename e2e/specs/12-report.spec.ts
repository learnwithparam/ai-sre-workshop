import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { ROOT } from "../lib/config";
import { chatToolCalls, chatUsage, state } from "../lib/stack";
import { expect, test } from "../lib/ui";

// Claude Haiku 5.5 per million tokens for a prompt of 100K tokens or fewer (Anthropic pricing, 21 Oct 2026).
const USD_PER_MTOK = { prompt: 0.1, completion: 0.5 };

test("report records tool calls, tokens, cost and time to root cause", async () => {
  const run = state.read();
  // The model id is written once, in the AI SRE model spec (tests/test_librechat.py pins that).
  const model = readFileSync(resolve(ROOT, "librechat/librechat.yaml"), "utf8").match(/^\s+model: (\S+)$/m)![1];

  // Tool calls and tokens are per conversation; "to proposal" stops at the first propose_remediation.
  const scenario = (s: { conversationId: string; openedAt: number; proposedAt: number }) => {
    const calls = chatToolCalls(s.conversationId);
    const usage = chatUsage(s.conversationId);
    return {
      tool_calls_to_proposal: calls.findIndex((c) => c.startsWith("propose_remediation")) + 1,
      tool_calls_total: calls.length,
      tokens: usage.prompt + usage.completion,
      cost_usd: Number(
        ((usage.prompt * USD_PER_MTOK.prompt + usage.completion * USD_PER_MTOK.completion) / 1e6).toFixed(4),
      ),
      time_to_root_cause_s: Math.round((s.proposedAt - s.openedAt) / 1000),
    };
  };
  const badRelease = scenario(run.badRelease);
  const docsHang = scenario(run.docsHang);
  const report = {
    model,
    generated_at: new Date().toISOString(),
    total_cost_usd: Number((badRelease.cost_usd + docsHang.cost_usd).toFixed(4)),
    bad_release: badRelease,
    docs_hang: docsHang,
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
