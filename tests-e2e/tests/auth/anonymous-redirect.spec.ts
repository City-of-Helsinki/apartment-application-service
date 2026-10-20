import { test, expect } from '../utils';

test.describe('6.4 Restricted pages redirect anonymous users', () => {
  test('accessing /admin as anonymous user is blocked', async ({ page }) => {
    const response = await page.goto('/admin');

    // Should get 403 or be redirected to login
    const status = response?.status() ?? 200;
    const url = page.url();

    const isBlocked = status === 403 || url.includes('/user/login') || url.includes('/login');
    expect(isBlocked, `Expected 403 or redirect to login, got ${status} at ${url}`).toBe(true);

    // No admin dashboard content visible
    await expect(page.locator('#toolbar-bar, .toolbar-bar')).not.toBeVisible();
  });
});
