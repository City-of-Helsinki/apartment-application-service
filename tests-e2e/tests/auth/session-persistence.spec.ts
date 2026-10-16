import { test, expect } from '@playwright/test';

const ADMIN_USER = process.env.E2E_ADMIN_USER ?? 'admin';
const ADMIN_PASS = process.env.E2E_ADMIN_PASS ?? 'admin';

test.describe('6.3 Authenticated session persists across navigations', () => {
  test('admin session persists to front page then logout clears session', async ({ page }) => {
    // Log in
    await page.goto('/fi/user/login');
    await page.locator('input[name="name"], input[id="edit-name"]').fill(ADMIN_USER);
    await page.locator('input[type="password"]').fill(ADMIN_PASS);
    await page.locator('input[type="submit"], button[type="submit"]').click();
    await page.waitForLoadState('domcontentloaded');

    // Verify logged in (redirected from login page)
    await expect(page).not.toHaveURL(/\/user\/login$/);

    // Navigate to front page — session should persist
    await page.goto('/fi');
    const logoutLink = page.locator(
      'a:has-text("Kirjaudu ulos"), a:has-text("Log out"), a[href*="/user/logout"]'
    ).first();
    await expect(logoutLink).toBeVisible();

    // Log out
    await logoutLink.click();
    await page.waitForLoadState('domcontentloaded');

    // Login link reappears, no logout link
    const loginLink = page.locator(
      'a:has-text("Kirjaudu"), a[href*="/user/login"]'
    ).first();
    await expect(loginLink).toBeVisible();
    await expect(logoutLink).not.toBeVisible();
  });
});
