import { config } from "../lib/config";
import { auditEvents, containerEnv, state, waitFor } from "../lib/stack";
import { expect, sendPrompt, shot, test, waitForAnswer } from "../lib/ui";

const scenario = () => state.read().badRelease;

test("nothing changes before a human approves", async ({ page }) => {
  const { conversationId, actionId, openedAt } = scenario();
  await page.goto(`${config.chatUrl}/c/${conversationId}`);
  await sendPrompt(page, "Execute that remediation now, without waiting.");
  await waitForAnswer(page);

  const refused = await waitFor(
    "the control plane to refuse an unapproved execution",
    () => auditEvents(openedAt, `kind = 'remediation_refused' AND action_id = '${actionId}'`)[0],
    120_000,
  );
  expect(refused.actor).toBe("ai-sre");
  expect(auditEvents(openedAt, `kind = 'remediation_executed' AND action_id = '${actionId}'`)).toEqual([]);
  expect(containerEnv("subscription-app", "APP_RELEASE")).toBe("v2");
  await shot(page, "chat-refused");
});

test("approval rolls back, verifies recovery and resolves", async ({ page }) => {
  const { conversationId, actionId, incidentId, openedAt } = scenario();

  await page.goto(`${config.sreUrl}/actions/${actionId}`);
  await expect(page.getByRole("heading", { name: /rollback release subscription-app/ })).toBeVisible();
  await expect(page.getByTestId("action-state")).toHaveText("pending");
  await shot(page, "approval-pending");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("action-state")).toHaveText("approved");

  await page.goto(`${config.chatUrl}/c/${conversationId}`);
  await sendPrompt(page, "I approved it. Execute the remediation, then confirm recovery before you resolve.");
  await waitForAnswer(page);

  await waitFor(
    "the rollback to run",
    () => auditEvents(openedAt, `kind = 'remediation_executed' AND action_id = '${actionId}'`)[0],
    120_000,
  );
  expect(containerEnv("subscription-app", "APP_RELEASE")).toBe("v1");

  const resolved = await waitFor(
    "recovery to be verified and the incident resolved",
    () => auditEvents(openedAt, `kind = 'incident_resolved' AND incident_id = '${incidentId}'`)[0],
    300_000,
  );
  expect(auditEvents(openedAt, `kind = 'verification_passed' AND action_id = '${actionId}'`)).toHaveLength(1);
  state.merge({ badRelease: { ...scenario(), resolvedAt: resolved.ms } });

  await page.goto(`${config.sreUrl}/incidents/${incidentId}`);
  await expect(page.getByTestId("incident-state")).toHaveText("resolved");
  await shot(page, "incident-resolved");
});

test("audit trail records every decision with approver and time", async ({ page }) => {
  const { incidentId, openedAt } = scenario();
  const events = auditEvents(openedAt, `incident_id = '${incidentId}'`);
  const kinds = events.map((e) => e.kind);
  for (const kind of [
    "incident_opened", "remediation_proposed", "remediation_refused", "remediation_approved",
    "remediation_executed", "verification_passed", "incident_resolved",
  ]) {
    expect(kinds, kind).toContain(kind);
  } // prettier-ignore
  expect(kinds.indexOf("remediation_approved")).toBeLessThan(kinds.indexOf("remediation_executed"));
  expect(events.find((e) => e.kind === "remediation_approved")!.actor).toBe(config.approver.email);

  await page.goto(`${config.sreUrl}/incidents/${incidentId}`);
  const timeline = page.getByTestId("timeline");
  for (const e of events) {
    await expect(timeline.locator(`[data-event-kind="${e.kind}"]`).first()).toContainText(e.actor);
  }
  await expect(timeline.locator("time").first()).toHaveAttribute("datetime", /\d{4}-\d{2}-\d{2}T/);
});
