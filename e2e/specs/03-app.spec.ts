import { config } from "../lib/config";
import { clickhouse, postgres, waitFor } from "../lib/stack";
import { expect, shot, test } from "../lib/ui";

test("a browser signup lands in Postgres and ClickHouse", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const started = new Date(Date.now() - 5_000).toISOString().replace("T", " ").slice(0, 19);

  await page.goto(config.appUrl);
  await page.locator("#subscribe").scrollIntoViewIfNeeded();
  await page.getByLabel("Full Name").fill("Workshop Attendee");
  await page.getByLabel("Company").fill("learnwithparam");
  await page.getByLabel("Email Address").fill(email);
  await page.locator("#source").selectOption("webinar");
  await page.getByRole("button", { name: "Subscribe to Updates" }).click();
  await expect(page.getByText("Successfully subscribed")).toBeVisible();
  await shot(page, "app-signup");

  expect(postgres(`SELECT source FROM users WHERE email = '${email}'`)).toBe("webinar");

  // The browser SDK reports the fetch; the backend reports the insert it caused.
  await waitFor(
    "frontend and backend spans for the signup",
    () => {
      const rows = clickhouse<{ ServiceName: string }>(
        `SELECT DISTINCT ServiceName FROM default.otel_traces
         WHERE Timestamp >= '${started}' AND SpanName ILIKE '%subscribe%'
           AND ServiceName IN ('subscription-frontend', 'subscription-backend') LIMIT 10`,
      );
      return rows.length === 2;
    },
    120_000,
  );
  await waitFor(
    "a recorded browser session",
    () => clickhouse(`SELECT 1 FROM default.hyperdx_sessions WHERE Timestamp >= '${started}' LIMIT 1`).length > 0,
    120_000,
  );
});
