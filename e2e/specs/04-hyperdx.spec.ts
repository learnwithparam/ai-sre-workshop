import { config } from "../lib/config";
import { expect, shot, test } from "../lib/ui";

test("HyperDX search shows subscription-backend traces", async ({ page }) => {
  await page.goto(`${config.hyperdxUrl}/login`);
  await page.getByPlaceholder("you@company.com").fill(config.hyperdxUser.email);
  await page.getByPlaceholder("Password").fill(config.hyperdxUser.password);
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByTestId("search-page")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("source-selector").click();
  await page.getByRole("option", { name: "Traces" }).click();
  await page.getByTestId("search-input").fill('ServiceName:"subscription-backend"');
  await page.getByTestId("search-submit-button").click();

  // A trace row carries a span status, which a log row never does, so this proves the Traces source.
  await expect(page.getByText(/Loading results/)).toBeHidden({ timeout: 60_000 });
  const first = page.locator("table tbody tr").first();
  await expect(first).toContainText(/subscription-backend\s*(Unset|Ok|Error)/, { timeout: 60_000 });
  await expect(page.getByText(/[\d,]+ Results/)).toBeVisible();
  await shot(page, "hyperdx-traces");
});
