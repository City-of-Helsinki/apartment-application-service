import { test, expect } from '@playwright/test';

test.describe('6.1 Drupal admin login page', () => {
  test('login page renders with username, password, and submit fields', async ({ page }) => {
    const response = await page.goto('/fi/user/login');
    expect(response?.status()).toBe(200);

    await expect(page.locator('input[name="name"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('input[type="submit"], button[type="submit"]')).toBeVisible();
  });

  test('invalid credentials show error without 500', async ({ page }) => {
    await page.goto('/fi/user/login');

    // The "name" field is type="email"; it must be syntactically valid or the
    // browser blocks submission before Drupal ever sees the request.
    await page.locator('input[name="name"]').fill('invalid@example.com');
    await page.locator('input[type="password"]').fill('invalid');
    await page.locator('input[type="submit"], button[type="submit"]').click();

    await page.waitForLoadState('domcontentloaded');

    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');

    const errorMsg = page.locator('.hds-notification--error, [role="alert"]').first();
    await expect(errorMsg).toBeVisible();

    // Login form still displayed
    await expect(page.locator('input[name="name"]')).toBeVisible();
  });
});
