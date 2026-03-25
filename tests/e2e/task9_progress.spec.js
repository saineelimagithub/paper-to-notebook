import { test, expect } from "@playwright/test";
import path from "path";

const screenshotsDir = path.join(process.cwd(), "tests/screenshots");

test("Progress display is NOT shown in idle state", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Progress display should not be visible in idle state
  const progressDisplay = page.locator('[data-testid="progress-display"]');
  await expect(progressDisplay).not.toBeVisible();

  // API key input should be visible (idle state)
  await expect(page.locator('[data-testid="api-key-input-container"]')).toBeVisible();

  // PDF upload should be visible (idle state)
  await expect(page.locator('[data-testid="pdf-upload-container"]')).toBeVisible();

  // Screenshot of initial state
  await page.screenshot({
    path: path.join(screenshotsDir, "task9-01-idle-no-progress.png"),
    fullPage: true,
  });
});

test("Result card is NOT shown in idle state", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Result card should not be visible in idle state
  const resultCard = page.locator('[data-testid="result-card"]');
  await expect(resultCard).not.toBeVisible();
});

test("Error state is NOT shown initially", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Error state should not be visible initially
  const errorState = page.locator('[data-testid="error-state"]');
  await expect(errorState).not.toBeVisible();
});
