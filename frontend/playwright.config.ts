import { defineConfig, devices } from "@playwright/test";

// The browser test plays CASE #001 end to end against the real backend with the mock AI,
// so it needs no model and no key. Both servers run on their own ports, so a dev server
// you already have open (on 8000 and 5173) is left alone.
const API_PORT = 8765;
const WEB_PORT = 5199;
// E2E_BASE_URL plays against a server that is already running instead, such as the
// Docker image in CI.
const external = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: external ?? `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: devices["Desktop Chrome"] }],
  webServer: external
    ? []
    : [
        {
          command: `uv run --directory ../backend casefile-api --ai mock --port ${API_PORT}`,
          url: `http://127.0.0.1:${API_PORT}/api/case`,
          // Games live in memory only, so a test run never touches backend/games.sqlite3.
          env: { CASEFILE_SAVE_FILE: "" },
          reuseExistingServer: false,
          timeout: 120_000,
        },
        {
          command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
          url: `http://127.0.0.1:${WEB_PORT}`,
          env: { CASEFILE_API: `http://127.0.0.1:${API_PORT}` },
          reuseExistingServer: false,
        },
      ],
});
