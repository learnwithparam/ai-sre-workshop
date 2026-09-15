import { config } from "../lib/config";
import { auditEvents, chatToolCalls, clickhouse, state, waitFor } from "../lib/stack";
import { expect, shot, test } from "../lib/ui";

test("the AI SRE investigates with tools and proposes a grounded rollback", async ({ page, request }) => {
  const { incidentId, openedAt } = state.read().badRelease;
  const key = await request.get("https://openrouter.ai/api/v1/key", {
    headers: { Authorization: `Bearer ${config.openrouterKey}` },
  });
  const usageBefore = (await key.json()).data.usage as number;

  await page.goto(`${config.sreUrl}/incidents/${incidentId}`);
  await expect(page.getByRole("heading", { name: /subscription-backend/ })).toBeVisible();
  await shot(page, "incident-open");
  await page.getByRole("link", { name: "Investigate with AI SRE" }).click();
  await page.waitForURL(/\/c\/[0-9a-f-]{36}/, { timeout: 60_000 });
  const conversationId = page.url().match(/\/c\/([0-9a-f-]{36})/)![1];

  const proposal = await waitFor(
    "the agent to propose a remediation",
    () => auditEvents(openedAt, `kind = 'remediation_proposed' AND incident_id = '${incidentId}'`)[0],
    300_000,
  );
  await expect(page.getByTestId("messages-view")).toContainText(`/actions/${proposal.action_id}`, {
    timeout: 300_000,
  });
  await shot(page, "chat-proposal");

  const p = proposal.payload;
  expect([p.action, p.target, p.params.release]).toEqual(["rollback_release", "subscription-app", "v1"]);
  expect([p.service, p.release]).toEqual(["subscription-backend", "v2"]);
  expect(p.trace_ids.length).toBeGreaterThan(0);
  const ids = p.trace_ids.map((t: string) => `'${t.replace(/[^0-9a-f]/g, "")}'`).join(",");
  const [{ found }] = clickhouse<{ found: string }>(
    `SELECT uniqExact(TraceId) AS found FROM default.otel_traces WHERE TraceId IN (${ids})`,
  );
  expect(Number(found)).toBe(p.trace_ids.length);

  const tools = chatToolCalls(conversationId);
  expect(tools.length).toBeGreaterThanOrEqual(3);
  expect(tools.some((t) => t.startsWith("propose_remediation"))).toBe(true);

  state.merge({
    badRelease: {
      ...state.read().badRelease,
      conversationId,
      actionId: proposal.action_id,
      proposedAt: proposal.ms,
      usageBefore,
    },
  });
});
