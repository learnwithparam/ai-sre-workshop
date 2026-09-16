/**
 * Two ClickStack views the workshop teaches from, driven while the bad release is live: the trace
 * waterfall of one slow signup, and the session replay of a real browser visit. Each writes the
 * screenshot teach.html shows for that module. Event deltas are taught from the same page by hand;
 * that view needs a drag across a canvas, which headless Chromium does not deliver.
 */
import { config } from "../lib/config";
import { expect, hyperdxSearch, openHyperdx, shot, test } from "../lib/ui";

// No model runs here, so the ten-minute budget the agent specs need would only slow a failure down.
test.describe.configure({ timeout: 180_000 });

test("a trace waterfall shows the spans of one slow signup", async ({ page }) => {
  await openHyperdx(page);
  await hyperdxSearch(page, "Traces", 'ServiceName:"subscription-backend" AND SpanName:"POST /api/subscribe"');

  // Click the span name itself: the first cell of the row toggles the raw event instead.
  const span = page.locator("table tbody tr").first().getByText("POST /api/subscribe").first();
  await expect(span).toBeVisible({ timeout: 60_000 });
  await span.click();
  await expect(page.getByTestId("row-side-panel")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("tab-trace").click();

  const panel = page.getByTestId("row-side-panel");
  await expect(panel).toContainText(/TraceId:\s*[0-9a-f]{32}/, { timeout: 30_000 });
  await expect(panel).toContainText(/\d+ spans/);
  // The span count renders before the bars do, so the waterfall itself is what to wait for.
  await expect(panel.getByText("Loading Traces...")).toBeHidden({ timeout: 60_000 });
  await expect(panel.getByText("subscription-backend", { exact: false }).first()).toBeVisible();
  await shot(page, "hyperdx-trace");
});

test("the session replay lists the browser visit that signed up", async ({ page }) => {
  // Sign in first, then go straight to the page: the sidebar reflows as saved searches load, so a
  // click on its Sessions link can land on the row above.
  await openHyperdx(page);
  await page.goto(`${config.hyperdxUrl}/sessions`);
  await expect(page.getByTestId("sessions-page")).toBeVisible({ timeout: 30_000 });

  // 03-app signed up through a real browser earlier in this run. The recorder batches, so give
  // the page a few reloads before calling the session missing.
  const cards = page.locator('[data-testid^="session-card-"]');
  for (let attempt = 0; attempt < 5 && (await cards.count()) === 0; attempt += 1) {
    await page.waitForTimeout(10_000);
    await page.reload();
  }
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });
  await shot(page, "hyperdx-sessions");
});
