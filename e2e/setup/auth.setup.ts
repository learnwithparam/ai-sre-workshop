import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { test as setup } from "@playwright/test";
import { clearChatHistory } from "../lib/stack";
import { loginChat, loginSre, STORAGE_STATE } from "../lib/ui";

// Log in once to LibreChat and to the approval pages, then every spec starts signed in.
setup("sign in to LibreChat and sre-control", async ({ page }) => {
  // Start from an empty workspace, so the screenshots this run writes show only this run's work.
  clearChatHistory();
  await loginChat(page);
  await loginSre(page);
  mkdirSync(dirname(STORAGE_STATE), { recursive: true });
  await page.context().storageState({ path: STORAGE_STATE });
});
