import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { test as setup } from "@playwright/test";
import { loginChat, loginSre, STORAGE_STATE } from "../lib/ui";

// Log in once to LibreChat and to the approval pages, then every spec starts signed in.
setup("sign in to LibreChat and sre-control", async ({ page }) => {
  await loginChat(page);
  await loginSre(page);
  mkdirSync(dirname(STORAGE_STATE), { recursive: true });
  await page.context().storageState({ path: STORAGE_STATE });
});
