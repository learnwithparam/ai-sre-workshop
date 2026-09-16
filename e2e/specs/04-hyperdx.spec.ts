import { expect, hyperdxSearch, openHyperdx, shot, test } from "../lib/ui";

test("HyperDX search shows subscription-backend traces", async ({ page }) => {
  await openHyperdx(page);
  await hyperdxSearch(page, "Traces", 'ServiceName:"subscription-backend"');

  // A trace row carries a span status, which a log row never does, so this proves the Traces source.
  const first = page.locator("table tbody tr").first();
  await expect(first).toContainText(/subscription-backend\s*(Unset|Ok|Error)/, { timeout: 60_000 });
  await expect(page.getByText(/[\d,]+ Results/)).toBeVisible();
  await shot(page, "hyperdx-traces");
});
