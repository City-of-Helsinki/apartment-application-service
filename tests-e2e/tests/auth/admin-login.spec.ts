import { test, expect } from '@playwright/test';

const ADMIN_USER = process.env.E2E_ADMIN_USER ?? 'admin';
const ADMIN_PASS = process.env.E2E_ADMIN_PASS ?? 'admin';

test.describe('6.1 Drupal admin login page', () => {
  test('login page renders with username, password, and submit fields', async ({ page }) => {
    const response = await page.goto('/fi/user/login');
    expect(response?.status()).toBe(200);

    await expect(page.locator('input[name="name"], input[id="edit-name"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('input[type="submit"], button[type="submit"]')).toBeVisible();
  });

  test('invalid credentials show error without 500', async ({ page }) => {
    await page.goto('/fi/user/login');

    await page.locator('input[name="name"], input[id="edit-name"]').fill('invalid');
    await page.locator('input[type="password"]').fill('invalid');
    await page.locator('input[type="submit"], button[type="submit"]').click();

    await page.waitForLoadState('domcontentloaded');

    // No server error
    const status = await page.evaluate(() => 0); // page loaded = no crash
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');

    // Error message present (Finnish)
    const errorMsg = page.locator('.messages--error, [class*="error"], [role="alert"]').first();
    await expect(errorMsg).toBeVisible();

    // Login form still displayed
    await expect(page.locator('input[name="name"], input[id="edit-name"]')).toBeVisible();
  });

  test('valid admin credentials log in successfully', async ({ page }) => {
    await page.goto('/fi/user/login');

    await page.locator('input[name="name"], input[id="edit-name"]').fill(ADMIN_USER);
    await page.locator('input[type="password"]').fill(ADMIN_PASS);
    await page.locator('input[type="submit"], button[type="submit"]').click();

    await page.waitForLoadState('domcontentloaded');

    // Successful login redirects away from /user/login
    await expect(page).not.toHaveURL(/\/user\/login$/);
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
  });
});
