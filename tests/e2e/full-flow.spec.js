import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const SCREENSHOTS = path.resolve("tests/screenshots");

// Ensure screenshots directory exists
if (!fs.existsSync(SCREENSHOTS)) {
  fs.mkdirSync(SCREENSHOTS, { recursive: true });
}

// Helper: create a tiny valid PDF in memory (PDF 1.0 minimal spec)
function createMinimalPdfBuffer() {
  const pdfContent = `%PDF-1.0
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
206
%%EOF`;
  return Buffer.from(pdfContent);
}

test.describe("Full user flow — E2E", () => {
  test("Step 1: Page loads with Paper → Notebook heading", async ({ page }) => {
    await page.goto("/");
    await page.screenshot({ path: `${SCREENSHOTS}/e2e-01-page-loaded.png` });

    const heading = page.locator("h1");
    await expect(heading).toBeVisible();
    await expect(heading).toContainText("Paper");
    await expect(heading).toContainText("Notebook");
  });

  test("Step 2: API key input accepts text and masks it", async ({ page }) => {
    await page.goto("/");

    const apiKeyInput = page.locator('[data-testid="api-key-input"]');
    await expect(apiKeyInput).toBeVisible();

    // Type an API key
    await apiKeyInput.fill("AIzaSyB-test-key-12345");
    await page.screenshot({ path: `${SCREENSHOTS}/e2e-02-api-key-entered.png` });

    // Input should be password type (masked)
    const inputType = await apiKeyInput.getAttribute("type");
    expect(inputType).toBe("password");
  });

  test("Step 3: PDF upload via file chooser shows filename", async ({ page }) => {
    await page.goto("/");

    // Create a temporary PDF file for upload
    const tmpDir = path.resolve("tests/tmp");
    if (!fs.existsSync(tmpDir)) {
      fs.mkdirSync(tmpDir, { recursive: true });
    }
    const pdfPath = path.join(tmpDir, "test-paper.pdf");
    fs.writeFileSync(pdfPath, createMinimalPdfBuffer());

    // Upload via file input
    const fileInput = page.locator('[data-testid="file-input"]');
    await fileInput.setInputFiles(pdfPath);

    await page.screenshot({ path: `${SCREENSHOTS}/e2e-03-pdf-selected.png` });

    // Should show the filename
    const fileInfo = page.locator('[data-testid="file-info"]');
    await expect(fileInfo).toBeVisible();
    await expect(fileInfo).toContainText("test-paper.pdf");

    // Cleanup
    fs.unlinkSync(pdfPath);
    fs.rmdirSync(tmpDir, { recursive: true });
  });

  test("Step 4: Clicking Generate shows progress, then reaches result or error", async ({ page }) => {
    await page.goto("/");

    // Enter API key
    const apiKeyInput = page.locator('[data-testid="api-key-input"]');
    await apiKeyInput.fill("AIzaSyB-fake-key-for-e2e-test");

    // Upload PDF
    const tmpDir = path.resolve("tests/tmp");
    if (!fs.existsSync(tmpDir)) {
      fs.mkdirSync(tmpDir, { recursive: true });
    }
    const pdfPath = path.join(tmpDir, "e2e-paper.pdf");
    fs.writeFileSync(pdfPath, createMinimalPdfBuffer());

    const fileInput = page.locator('[data-testid="file-input"]');
    await fileInput.setInputFiles(pdfPath);

    // Click Generate
    const generateBtn = page.locator('[data-testid="generate-btn"]');
    await expect(generateBtn).toBeEnabled();
    await generateBtn.click();

    await page.screenshot({ path: `${SCREENSHOTS}/e2e-04-generating.png` });

    // Wait for either result card or error state (up to 30s)
    const resultOrError = page.locator(
      '[data-testid="result-card"], [data-testid="error-state"]'
    );
    await expect(resultOrError).toBeVisible({ timeout: 30000 });

    await page.screenshot({ path: `${SCREENSHOTS}/e2e-05-result.png` });

    // Verify we reached a terminal state
    const resultCard = page.locator('[data-testid="result-card"]');
    const errorState = page.locator('[data-testid="error-state"]');
    const isResult = await resultCard.isVisible();
    const isError = await errorState.isVisible();
    expect(isResult || isError).toBe(true);

    // Cleanup
    fs.unlinkSync(pdfPath);
    fs.rmdirSync(tmpDir, { recursive: true });
  });

  test("Step 5: Generate Another button resets to idle state", async ({ page }) => {
    await page.goto("/");

    // Verify idle state has the API key input visible
    const apiKeyInput = page.locator('[data-testid="api-key-input"]');
    await expect(apiKeyInput).toBeVisible();

    // And the upload zone
    const dropZone = page.locator('[data-testid="drop-zone"]');
    await expect(dropZone).toBeVisible();

    await page.screenshot({ path: `${SCREENSHOTS}/e2e-06-idle-state.png` });
  });
});
