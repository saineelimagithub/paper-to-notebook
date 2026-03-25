import { test, expect } from "@playwright/test";
import path from "path";

const screenshotsDir = path.join(process.cwd(), "tests/screenshots");

test("UI shell has correct theme colors and layout", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Verify the page loads with correct title
  await expect(page.locator('[data-testid="app-root"]')).toBeVisible();

  // Check dark background on body
  const bgColor = await page.evaluate(() => {
    return window.getComputedStyle(document.body).backgroundColor;
  });
  // #0d0d0d = rgb(13, 13, 13)
  expect(bgColor).toBe("rgb(13, 13, 13)");

  // Check "RESEARCH TOOL" label is visible and has green accent color
  const researchToolLabel = page.locator("text=Research Tool");
  await expect(researchToolLabel).toBeVisible();

  const labelColor = await researchToolLabel.evaluate((el) => {
    return window.getComputedStyle(el).color;
  });
  // accent #4ade80 = rgb(74, 222, 128)
  expect(labelColor).toBe("rgb(74, 222, 128)");

  // Check Inter font is used
  const headingFont = await page.locator("h1").evaluate((el) => {
    return window.getComputedStyle(el).fontFamily;
  });
  expect(headingFont).toContain("Inter");

  // Check heading text
  await expect(page.locator("h1")).toContainText("Notebook");

  // Take screenshot
  await page.screenshot({
    path: path.join(screenshotsDir, "task6-01-ui-shell.png"),
    fullPage: true,
  });
});
