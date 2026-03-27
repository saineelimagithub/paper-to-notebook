/**
 * Live Quality Test — generates a REAL notebook from "Attention Is All You Need"
 * using an actual Gemini API key.
 *
 * Tagged @live — excluded from CI. Run manually:
 *   GEMINI_API_KEY=AIza... npx playwright test tests/e2e/live-quality.spec.js --headed
 *
 * Requirements:
 *   - GEMINI_API_KEY env var set to a valid Gemini API key
 *   - Backend running on localhost:8000
 *   - Frontend running on localhost:5173
 *   - PDF at C:\Users\U6041256\Downloads\NIPS-2017-attention-is-all-you-need-Paper.pdf
 */
import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const SCREENSHOTS = path.resolve("tests/screenshots");
const PDF_PATH = path.resolve(
  "C:\\Users\\U6041256\\Downloads\\NIPS-2017-attention-is-all-you-need-Paper.pdf"
);
const DOWNLOAD_DIR = path.resolve("tests/tmp/downloads");

// Ensure directories exist
for (const dir of [SCREENSHOTS, DOWNLOAD_DIR]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

test.describe("Live Quality Test — Attention Is All You Need", () => {
  test.setTimeout(180_000); // 3 minutes max

  test("Generate real notebook and validate output structure", async ({
    page,
    context,
  }) => {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      test.skip(true, "GEMINI_API_KEY env var not set — skipping live test");
      return;
    }

    // Verify PDF exists
    expect(fs.existsSync(PDF_PATH)).toBe(true);

    // ── Step 1: Navigate ──────────────────────────────────────────────
    await page.goto("/");
    await page.screenshot({ path: `${SCREENSHOTS}/live-01-page-loaded.png` });
    await expect(page.locator("h1")).toContainText("Paper");

    // ── Step 2: Enter API key ─────────────────────────────────────────
    const apiKeyInput = page.locator('[data-testid="api-key-input"]');
    await apiKeyInput.fill(apiKey);
    await page.screenshot({ path: `${SCREENSHOTS}/live-02-api-key-entered.png` });

    // ── Step 3: Upload "Attention Is All You Need" PDF ────────────────
    const fileInput = page.locator('[data-testid="file-input"]');
    await fileInput.setInputFiles(PDF_PATH);
    await page.screenshot({ path: `${SCREENSHOTS}/live-03-pdf-uploaded.png` });

    const fileInfo = page.locator('[data-testid="file-info"]');
    await expect(fileInfo).toBeVisible();
    await expect(fileInfo).toContainText(".pdf");

    // ── Step 4: Click Generate ────────────────────────────────────────
    const generateBtn = page.locator('[data-testid="generate-btn"]');
    await expect(generateBtn).toBeEnabled();
    await generateBtn.click();
    await page.screenshot({ path: `${SCREENSHOTS}/live-04-generating.png` });

    // ── Step 5: Wait for result card (up to 120s) ─────────────────────
    const resultCard = page.locator('[data-testid="result-card"]');
    await expect(resultCard).toBeVisible({ timeout: 120_000 });
    await page.screenshot({ path: `${SCREENSHOTS}/live-05-result-card.png` });

    // ── Step 6: Click Download and capture the file ───────────────────
    // Set up download listener before clicking
    const downloadPromise = page.waitForEvent("download", { timeout: 15_000 });

    // If there are security warnings, acknowledge them first
    const acknowledgeBtn = page.locator(
      '[data-testid="acknowledge-warnings-btn"]'
    );
    if (await acknowledgeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await acknowledgeBtn.click();
      await page.screenshot({
        path: `${SCREENSHOTS}/live-06-warnings-acknowledged.png`,
      });
    }

    const downloadBtn = page.locator('[data-testid="download-btn"]');
    await expect(downloadBtn).toBeVisible();
    await downloadBtn.click();

    const download = await downloadPromise;
    const downloadPath = path.join(DOWNLOAD_DIR, download.suggestedFilename());
    await download.saveAs(downloadPath);
    await page.screenshot({ path: `${SCREENSHOTS}/live-07-downloaded.png` });

    // ── Step 7: Validate the downloaded notebook ──────────────────────
    expect(fs.existsSync(downloadPath)).toBe(true);

    const notebookContent = fs.readFileSync(downloadPath, "utf-8");

    // 7a: Valid JSON
    let notebook;
    try {
      notebook = JSON.parse(notebookContent);
    } catch (e) {
      throw new Error(`Downloaded notebook is not valid JSON: ${e.message}`);
    }

    // 7b: Has cells array
    expect(notebook).toHaveProperty("cells");
    expect(Array.isArray(notebook.cells)).toBe(true);

    // 7c: At least 8 cells
    expect(notebook.cells.length).toBeGreaterThanOrEqual(8);

    // 7d: At least one code cell contains 'import'
    const codeCells = notebook.cells.filter((c) => c.cell_type === "code");
    const hasImport = codeCells.some((c) =>
      (Array.isArray(c.source) ? c.source.join("") : c.source).includes(
        "import"
      )
    );
    expect(hasImport).toBe(true);

    // 7e: At least one markdown cell contains '#'
    const mdCells = notebook.cells.filter((c) => c.cell_type === "markdown");
    const hasHeading = mdCells.some((c) =>
      (Array.isArray(c.source) ? c.source.join("") : c.source).includes("#")
    );
    expect(hasHeading).toBe(true);

    // Log summary
    console.log(`\n✅ Notebook validated successfully:`);
    console.log(`   Cells: ${notebook.cells.length}`);
    console.log(`   Code cells: ${codeCells.length}`);
    console.log(`   Markdown cells: ${mdCells.length}`);
    console.log(`   File: ${downloadPath}`);

    // Cleanup download
    fs.unlinkSync(downloadPath);
  });
});
