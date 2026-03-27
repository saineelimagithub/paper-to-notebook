import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev",
    cwd: "./frontend",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
