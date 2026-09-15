import { config } from "../lib/config";
import { auditEvents, chaos, inspect, state, waitFor } from "../lib/stack";
import { expect, sendPrompt, shot, test, waitForAnswer } from "../lib/ui";

test("hung requests open an incident", async () => {
  const startedAt = Date.now();
  chaos("docs-hang");
  const opened = await waitFor(
    "a stuck_requests incident for docs-loader",
    () =>
      auditEvents(startedAt, "kind = 'incident_opened'").find(
        (e) => e.payload.rule === "stuck_requests" && e.payload.service === "docs-loader",
      ),
    90_000,
  );
  state.merge({ docsHang: { incidentId: opened.incident_id, openedAt: opened.ms } });
});

test("reject, edit and approve a restart", async ({ page }) => {
  const { incidentId, openedAt } = state.read().docsHang;
  const startedBefore = inspect("docs-loader", "{{.State.StartedAt}}");

  await page.goto(`${config.sreUrl}/incidents/${incidentId}`);
  await page.getByRole("link", { name: "Investigate with AI SRE" }).click();
  await page.waitForURL(/\/c\/[0-9a-f-]{36}/, { timeout: 60_000 });
  const conversationId = page.url().match(/\/c\/([0-9a-f-]{36})/)![1];
  const proposal = await waitFor(
    "the agent to propose a remediation",
    () => auditEvents(openedAt, `kind = 'remediation_proposed' AND incident_id = '${incidentId}'`)[0],
    300_000,
  );
  await waitForAnswer(page);

  await page.goto(`${config.sreUrl}/actions/${proposal.action_id}`);
  await page.getByLabel("Reason").fill("Only docs-loader holds the hung handlers; restart it and track the timeout fix.");
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByTestId("action-state")).toHaveText("rejected");

  await page.getByLabel("Action").selectOption("restart_service");
  await page.getByLabel("Target").selectOption("docs-loader");
  await page.getByRole("button", { name: "Save edit" }).click();
  await expect(page.getByTestId("action-state")).toHaveText("pending");
  await shot(page, "approval-edited");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("action-state")).toHaveText("approved");

  await page.goto(`${config.chatUrl}/c/${conversationId}`);
  await sendPrompt(page, "I rejected your proposal and approved an edited one. Execute it and confirm recovery.");
  await waitForAnswer(page);

  await waitFor(
    "the approved restart to resolve the incident",
    () => auditEvents(openedAt, `kind = 'incident_resolved' AND incident_id = '${incidentId}'`)[0],
    300_000,
  );
  expect(inspect("docs-loader", "{{.State.StartedAt}}")).not.toBe(startedBefore);

  const kinds = auditEvents(openedAt, `action_id = '${proposal.action_id}'`).map((e) => e.kind);
  expect(kinds.slice(0, 5)).toEqual([
    "remediation_proposed", "remediation_rejected", "remediation_edited", "remediation_approved",
    "remediation_executed",
  ]); // prettier-ignore
  const executed = auditEvents(openedAt, `kind = 'remediation_executed' AND action_id = '${proposal.action_id}'`)[0];
  expect([executed.payload.action, executed.payload.target]).toEqual(["restart_service", "docs-loader"]);
  state.merge({ docsHang: { ...state.read().docsHang, conversationId, proposedAt: proposal.ms } });
});
