import { test, expect } from '@playwright/test';

// run-e2e.sh generates a fresh `drush uli --uid=1` one-time login link per run
// and passes it here, since the login form's email-type field makes scripted
// form-fill login brittle and the dump's admin password is unknown.
const LOGIN_URL = process.env.E2E_LOGIN_URL;

test.describe('6.3 Authenticated session persists across navigations', () => {
  test('one-time login link authenticates, session persists, logout clears it', async ({ page }) => {
    test.skip(!LOGIN_URL, 'E2E_LOGIN_URL not set — run via run-e2e.sh to generate a one-time drush uli link');

    await page.goto(LOGIN_URL!);
    await page.waitForLoadState('domcontentloaded');

    // Logged in — admin toolbar visible
    await expect(page.locator('#toolbar-bar, .toolbar-bar').first()).toBeVisible();

    // Session persists across navigation
    await page.goto('/fi');
    await expect(page.locator('#toolbar-bar, .toolbar-bar').first()).toBeVisible();

    // Log out
    const logoutLink = page.locator('a[href*="/user/logout"]').first();
    await logoutLink.click();
    await page.waitForLoadState('domcontentloaded');

    await expect(page.locator('#toolbar-bar, .toolbar-bar').first()).not.toBeVisible();
    await expect(page.locator('a:has-text("Kirjaudu")').first()).toBeVisible();
  });
});
