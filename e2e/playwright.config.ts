import { defineConfig, devices } from "@playwright/test";
import { STORAGE_STATE } from "./lib/ui";

/**
 * Host-driven, one worker, specs in file order: later specs build on the incident an earlier
 * one opened. The stack is started by `make up` before this runs, so there is no webServer.
 */
export default defineConfig({
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "../artifacts/playwright.json" }], ["html", { open: "never" }]],
  timeout: 600_000,
  expect: { timeout: 20_000 },
  // No video: the host also runs Docker at 8 GB, and a recorder per spec is memory the stack needs.
  use: { trace: "retain-on-failure", screenshot: "only-on-failure", video: "off" },
  projects: [
    { name: "setup", testDir: "./setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "stack",
      testDir: "./specs",
      testMatch: /.*\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], storageState: STORAGE_STATE, viewport: { width: 1440, height: 900 } },
      dependencies: ["setup"],
    },
  ],
});
