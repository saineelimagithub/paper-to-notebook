import { test, expect } from "@playwright/test";
import path from "path";

const screenshotsDir = path.join(process.cwd(), "tests/screenshots");

test("Idle state shows APIKeyInput and PDFUpload", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Both idle components should be visible
  await expect(page.locator('[data-testid="api-key-input-container"]')).toBeVisible();
  await expect(page.locator('[data-testid="pdf-upload-container"]')).toBeVisible();

  // Result card should NOT be visible in idle state
  await expect(page.locator('[data-testid="result-card"]')).not.toBeVisible();

  // Progress display should NOT be visible in idle state
  await expect(page.locator('[data-testid="progress-display"]')).not.toBeVisible();

  // Screenshot of idle state
  await page.screenshot({
    path: path.join(screenshotsDir, "task10-01-idle-state.png"),
    fullPage: true,
  });
});

test("Error state appears when fetch fails and can be reset", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Mock the fetch to return an error
  await page.route("/generate", async (route) => {
    await route.fulfill({
      status: 500,
      body: "Internal Server Error",
    });
  });

  // Fill in API key
  await page.locator('[data-testid="api-key-input"]').fill("sk-test123");

  // Upload a file
  const minimalPdf = Buffer.from(
    "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n" +
    "trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n90\n%%EOF"
  );
  await page.locator('[data-testid="file-input"]').setInputFiles({
    name: "test.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf,
  });

  // Click generate button
  await page.locator('[data-testid="generate-btn"]').click();

  // Error state should appear
  const errorState = page.locator('[data-testid="error-state"]');
  await expect(errorState).toBeVisible({ timeout: 5000 });

  // Screenshot of error state
  await page.screenshot({
    path: path.join(screenshotsDir, "task10-02-error-state.png"),
    fullPage: true,
  });

  // Click "Try Again" to reset
  await page.locator("text=Try Again").click();

  // Should return to idle state
  await expect(page.locator('[data-testid="api-key-input-container"]')).toBeVisible();
  await expect(errorState).not.toBeVisible();

  // Screenshot after reset
  await page.screenshot({
    path: path.join(screenshotsDir, "task10-03-after-reset.png"),
    fullPage: true,
  });
});

test("App layout screenshot — full component view", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Wait for full render
  await page.waitForLoadState("networkidle");

  await page.screenshot({
    path: path.join(screenshotsDir, "task10-04-full-layout.png"),
    fullPage: true,
  });

  // Verify all key UI elements
  await expect(page.locator("h1")).toContainText("Notebook");
  await expect(page.locator("text=Research Tool")).toBeVisible();
  await expect(
    page.locator('[data-testid="api-key-input-container"] span').filter({ hasText: "never stored" })
  ).toBeVisible();
});
