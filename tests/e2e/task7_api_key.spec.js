import { test, expect } from "@playwright/test";
import path from "path";

const screenshotsDir = path.join(process.cwd(), "tests/screenshots");

test("APIKeyInput component renders and toggles visibility", async ({ page }) => {
  await page.goto("http://localhost:5173");

  // Verify container is visible
  const container = page.locator('[data-testid="api-key-input-container"]');
  await expect(container).toBeVisible();

  // Screenshot 1: initial state
  await page.screenshot({
    path: path.join(screenshotsDir, "task7-01-api-key-initial.png"),
  });

  // Input should be of type password by default
  const input = page.locator('[data-testid="api-key-input"]');
  await expect(input).toBeVisible();
  const inputType = await input.getAttribute("type");
  expect(inputType).toBe("password");

  // Type a test key
  await input.fill("sk-test123");
  await expect(input).toHaveValue("sk-test123");

  // Screenshot 2: after typing (masked)
  await page.screenshot({
    path: path.join(screenshotsDir, "task7-02-api-key-typed-masked.png"),
  });

  // Click "show" button to reveal the key
  const toggleBtn = page.locator('[data-testid="toggle-key-visibility"]');
  await expect(toggleBtn).toBeVisible();
  await expect(toggleBtn).toHaveText("show");
  await toggleBtn.click();

  // Now input should be type="text"
  const inputTypeAfterToggle = await input.getAttribute("type");
  expect(inputTypeAfterToggle).toBe("text");
  await expect(toggleBtn).toHaveText("hide");

  // Screenshot 3: after toggle (visible)
  await page.screenshot({
    path: path.join(screenshotsDir, "task7-03-api-key-visible.png"),
  });

  // Click "hide" to mask again
  await toggleBtn.click();
  const inputTypeAfterHide = await input.getAttribute("type");
  expect(inputTypeAfterHide).toBe("password");
  await expect(toggleBtn).toHaveText("show");
});

test("APIKeyInput shows security note", async ({ page }) => {
  await page.goto("http://localhost:5173");
  // Use the specific span inside the api-key-input-container
  await expect(
    page.locator('[data-testid="api-key-input-container"] span').filter({ hasText: "never stored" })
  ).toBeVisible();
});
