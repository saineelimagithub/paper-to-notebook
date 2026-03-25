import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const screenshotsDir = path.join(process.cwd(), "tests/screenshots");

test("PDFUpload renders drop zone and disabled button", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Verify drop zone is visible
  const dropZone = page.locator('[data-testid="drop-zone"]');
  await expect(dropZone).toBeVisible();
  await expect(dropZone).toContainText("Drop a research paper PDF here");

  // Screenshot 1: initial state with no file and no API key
  await page.screenshot({
    path: path.join(screenshotsDir, "task8-01-upload-initial.png"),
  });

  // Generate button should be disabled (no API key, no file)
  const generateBtn = page.locator('[data-testid="generate-btn"]');
  await expect(generateBtn).toBeVisible();
  await expect(generateBtn).toBeDisabled();
});

test("Generate button stays disabled with API key but no file", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Type API key
  const apiKeyInput = page.locator('[data-testid="api-key-input"]');
  await apiKeyInput.fill("sk-test123");

  // Button still disabled (no file)
  const generateBtn = page.locator('[data-testid="generate-btn"]');
  await expect(generateBtn).toBeDisabled();

  // Screenshot
  await page.screenshot({
    path: path.join(screenshotsDir, "task8-02-api-key-no-file.png"),
  });
});

test("File selection enables generate button and shows file info", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // First enter API key
  const apiKeyInput = page.locator('[data-testid="api-key-input"]');
  await apiKeyInput.fill("sk-test123");

  // Create a minimal PDF-like file for testing
  // We use a real minimal PDF bytes
  const minimalPdfContent = Buffer.from(
    "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n" +
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n" +
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n" +
    "xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n" +
    "0000000058 00000 n\n0000000115 00000 n\n" +
    "trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
  );

  // Upload the file via the file input
  const fileInput = page.locator('[data-testid="file-input"]');
  await fileInput.setInputFiles({
    name: "test-paper.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdfContent,
  });

  // File info should appear
  const fileInfo = page.locator('[data-testid="file-info"]');
  await expect(fileInfo).toBeVisible();
  await expect(fileInfo).toContainText("test-paper.pdf");

  // Generate button should now be enabled
  const generateBtn = page.locator('[data-testid="generate-btn"]');
  await expect(generateBtn).toBeEnabled();

  // Screenshot with file selected and button enabled
  await page.screenshot({
    path: path.join(screenshotsDir, "task8-03-file-selected-enabled.png"),
  });
});
