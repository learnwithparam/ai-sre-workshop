import { config } from "../lib/config";
import { clickhouse, postgres, waitFor } from "../lib/stack";
import { expect, shot, test } from "../lib/ui";

test("a browser signup lands in Postgres and ClickHouse", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const started = new Date(Date.now() - 5_000).toISOString().replace("T", " ").slice(0, 19);

  await page.goto(config.appUrl);
  await shot(page, "app-home");
  await page.locator("#subscribe").scrollIntoViewIfNeeded();
  await page.getByLabel("Full Name").fill("Workshop Attendee");
  await page.getByLabel("Company").fill("learnwithparam");
  await page.getByLabel("Email Address").fill(email);
  await page.locator("#source").selectOption("webinar");
  await page.getByRole("button", { name: "Subscribe to Updates" }).click();
  await expect(page.locator("#successMessage")).toContainText("Thank you for subscribing");
  await shot(page, "app-signup");

  expect(postgres(`SELECT source FROM users WHERE email = '${email}'`)).toBe("webinar");

  // The browser SDK records the fetch with its request body; the backend span shares its trace.
  const [frontend] = await waitFor(
    "the browser's POST /api/subscribe span carrying this email",
    () => {
      const rows = clickhouse<{ TraceId: string }>(
        `SELECT TraceId FROM default.otel_traces
         WHERE Timestamp >= '${started}' AND ServiceName = 'subscription-frontend'
           AND SpanAttributes['http.url'] LIKE '%/api/subscribe'
           AND position(SpanAttributes['http.request.body'], '${email}') > 0 LIMIT 1`,
      );
      return rows.length > 0 && rows;
    },
    120_000,
  );
  // Each service exports on its own batch timer, so the backend span can land after the browser's.
  await waitFor(
    "the backend POST /api/subscribe span in the same trace",
    () =>
      Number(
        clickhouse<{ backend: string }>(
          `SELECT count() AS backend FROM default.otel_traces
           WHERE TraceId = '${frontend.TraceId}' AND ServiceName = 'subscription-backend'
             AND SpanName = 'POST /api/subscribe'`,
        )[0].backend,
      ) === 1,
    60_000,
  );
  await waitFor(
    "a recorded browser session",
    () => clickhouse(`SELECT 1 FROM default.hyperdx_sessions WHERE Timestamp >= '${started}' LIMIT 1`).length > 0,
    120_000,
  );
});

test("the signup page holds together at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(config.appUrl);

  // Nothing may push the body sideways, and every driver's target stays reachable.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  for (const link of ["Features", "Performance", "Subscribe", "Docs"]) {
    await expect(page.locator(".nav-links").getByRole("link", { name: link, exact: true })).toBeVisible();
  }
  await page.locator("#subscribe").scrollIntoViewIfNeeded();
  await expect(page.getByLabel("Full Name")).toBeVisible();
  await expect(page.getByRole("button", { name: "Subscribe to Updates" })).toBeVisible();
  await shot(page, "app-mobile");
});
