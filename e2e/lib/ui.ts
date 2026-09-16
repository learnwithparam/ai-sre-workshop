import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { test as base, expect, type Page } from "@playwright/test";
import { config } from "./config";

export const STORAGE_STATE = resolve(__dirname, "../playwright/.auth/state.json");

/**
 * LibreChat rotates its refresh cookie on every page mount, so a snapshot taken once goes stale
 * after the first spec. Re-saving storage state after each test carries the rotated cookie
 * forward (the same fix agentic-data-stack's e2e uses).
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await use(page);
    writeFileSync(STORAGE_STATE, JSON.stringify(await page.context().storageState()));
  },
});
export { expect };

export const loginChat = async (page: Page): Promise<void> => {
  await page.goto(`${config.chatUrl}/login`);
  await page.getByRole("textbox", { name: "Email", exact: true }).fill(config.chatUser.email);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(config.chatUser.password);
  await page.getByRole("button", { name: /continue|log ?in|sign ?in/i }).click();
  await expect(page.getByTestId("new-chat-button")).toBeVisible({ timeout: 30_000 });
};

/**
 * Opens HyperDX's search page, logging in only when the stored session has lapsed. The redirect to
 * the login form happens after hydration, so the URL right after `goto` cannot be trusted; wait for
 * whichever of the two screens renders.
 */
export const openHyperdx = async (page: Page): Promise<void> => {
  await page.goto(`${config.hyperdxUrl}/login`);
  const email = page.getByPlaceholder("you@company.com");
  const searchPage = page.getByTestId("search-page");
  await expect(email.or(searchPage).first()).toBeVisible({ timeout: 60_000 });
  if (await email.isVisible()) {
    await email.fill(config.hyperdxUser.email);
    await page.getByPlaceholder("Password").fill(config.hyperdxUser.password);
    await page.getByRole("button", { name: "Login" }).click();
  }
  await expect(searchPage).toBeVisible({ timeout: 30_000 });
};

/** Runs a Lucene search against one HyperDX source and waits for the result table. */
export const hyperdxSearch = async (page: Page, source: string, query: string): Promise<void> => {
  // The selector is a combobox that keeps its choice per profile, and picking the source it
  // already holds clears it instead, which then runs the query against no source at all.
  // It also renders empty for about a second on load, and a choice made in that window is undone
  // when the page restores its own source.
  const selector = page.getByTestId("source-selector");
  await expect(selector).not.toHaveValue("", { timeout: 60_000 });
  if ((await selector.inputValue()) !== source) {
    await selector.click();
    const option = page.getByRole("option", { name: source, exact: true });
    await expect(option).toBeVisible({ timeout: 30_000 });
    await option.click();
  }
  await expect(selector).toHaveValue(source);

  // The time range persists per profile, so an earlier spec can leave a window that has since
  // scrolled into the past and returns nothing.
  const picker = page.getByTestId("time-picker-input");
  await picker.fill("Last 30 minutes");
  await picker.press("Enter");

  await page.getByTestId("search-input").fill(query);
  await page.getByTestId("search-submit-button").click();
  await expect(page.getByText(/Loading results/)).toBeHidden({ timeout: 60_000 });
};

export const loginSre = async (page: Page): Promise<void> => {
  await page.goto(`${config.sreUrl}/login`);
  await page.getByLabel("Email").fill(config.approver.email);
  await page.getByLabel("Password").fill(config.approver.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Incidents", exact: true })).toBeVisible();
};

/**
 * Reopens a conversation and waits until its history is on screen. Typing before the thread loads
 * sends the message as a new root with no context, and the model starts the investigation over.
 */
export const openChat = async (page: Page, conversationId: string, lastSeen: string): Promise<void> => {
  await page.goto(`${config.chatUrl}/c/${conversationId}`);
  await expect(page.getByTestId("messages-view")).toContainText(lastSeen, { timeout: 60_000 });
  await expect(page.getByTestId("text-input")).toBeEnabled({ timeout: 60_000 });
};

/** Types into the LibreChat composer of the conversation already open in `page`. */
export const sendPrompt = async (page: Page, prompt: string): Promise<void> => {
  const input = page.getByTestId("text-input");
  await expect(input).toBeEnabled({ timeout: 60_000 });
  await input.fill(prompt);
  await page.getByTestId("send-button").click();
};

/** Waits until LibreChat has finished streaming the current answer. */
export const waitForAnswer = async (page: Page, timeoutMs = 300_000): Promise<void> => {
  await expect(page.getByTestId("stop-generation-button")).toBeHidden({ timeout: timeoutMs });
  await expect(page.getByTestId("send-button")).toBeVisible({ timeout: timeoutMs });
};

export const shot = async (page: Page, name: string): Promise<void> => {
  await page.screenshot({ path: resolve(__dirname, `../../evidence/screens/${name}.png`), fullPage: false });
};
