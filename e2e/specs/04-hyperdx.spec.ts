import { config } from "../lib/config";
import { expect, shot, test } from "../lib/ui";

test("HyperDX search shows subscription-backend traces", async ({ page }) => {
  await page.goto(`${config.hyperdxUrl}/login`);
  await page.getByPlaceholder(/email/i).fill(config.hyperdxUser.email);
  await page.getByPlaceholder(/password/i).fill(config.hyperdxUser.password);
  await page.getByRole("button", { name: /login|sign in/i }).click();
  await page.waitForURL(/\/search/);

  await page.goto(`${config.hyperdxUrl}/search?where=${encodeURIComponent('ServiceName:"subscription-backend"')}&whereLanguage=lucene`);
  await page.getByText("Traces", { exact: true }).first().click().catch(() => undefined);
  await expect(page.getByText("subscription-backend").first()).toBeVisible({ timeout: 60_000 });
  await shot(page, "hyperdx-search");
});
