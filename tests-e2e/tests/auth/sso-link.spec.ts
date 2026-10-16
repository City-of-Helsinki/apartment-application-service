import { test, expect } from '@playwright/test';

test.describe('6.2 Helsinki profile SSO login entry point', () => {
  test('login button or link is visible to anonymous users', async ({ page }) => {
    await page.goto('/fi');

    const loginLink = page.locator(
      'a:has-text("Kirjaudu"), a:has-text("Kirjaudu sisään"), a[href*="/user/login"], a[href*="login"], ' +
      'button:has-text("Kirjaudu")'
    ).first();
    await expect(loginLink).toBeVisible();
  });

  test('clicking login entry point leads to a login page without server error', async ({ page }) => {
    await page.goto('/fi');

    const loginLink = page.locator(
      'a:has-text("Kirjaudu"), a:has-text("Kirjaudu sisään"), a[href*="/user/login"], a[href*="login"]'
    ).first();

    const href = await loginLink.getAttribute('href');
    if (!href) {
      test.skip();
      return;
    }

    const response = await page.goto(href.startsWith('http') ? href : `http://localhost:18080${href}`);
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
  });
});
