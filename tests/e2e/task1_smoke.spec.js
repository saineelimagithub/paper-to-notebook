import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOTS = path.resolve("tests/screenshots");

test.describe("Task 1 — Scaffold smoke tests", () => {
  test("page loads with correct heading", async ({ page }) => {
    await page.goto("http://localhost:5173");
    await page.screenshot({ path: `${SCREENSHOTS}/task1-01-initial-load.png` });

    // Must contain the app title
    await expect(page.locator("h1")).toContainText("Paper");
    await page.screenshot({ path: `${SCREENSHOTS}/task1-02-heading-visible.png` });
  });

  test("page has correct background color (dark theme)", async ({ page }) => {
    await page.goto("http://localhost:5173");
    const bgColor = await page.evaluate(() =>
      window.getComputedStyle(document.body).backgroundColor
    );
    // #0d0d0d = rgb(13, 13, 13)
    expect(bgColor).toBe("rgb(13, 13, 13)");
  });

  test("page renders API key input placeholder", async ({ page }) => {
    await page.goto("http://localhost:5173");
    // The APIKeyInput component will be added later, but the placeholder div must exist
    await expect(page.locator('[data-testid="app-root"]')).toBeVisible();
    await page.screenshot({ path: `${SCREENSHOTS}/task1-03-app-root.png` });
  });
});
