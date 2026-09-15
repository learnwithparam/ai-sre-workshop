import { auditEvents, chaos, containerEnv, state, waitFor } from "../lib/stack";
import { expect, test } from "../lib/ui";

test("a bad release opens an incident within 90 seconds", async () => {
  expect(containerEnv("subscription-app", "APP_RELEASE")).toBe("v1");
  const deployedAt = Date.now();
  chaos("bad-release");
  expect(containerEnv("subscription-app", "APP_RELEASE")).toBe("v2");

  const opened = await waitFor(
    "an error_rate incident for subscription-backend",
    () =>
      auditEvents(deployedAt, "kind = 'incident_opened'").find(
        (e) => e.payload.rule === "error_rate" && e.payload.service === "subscription-backend",
      ),
    90_000,
  );
  expect((opened.ms - deployedAt) / 1000).toBeLessThanOrEqual(90);
  state.merge({ badRelease: { incidentId: opened.incident_id, deployedAt, openedAt: opened.ms } });
});
