import { test, expect } from '@playwright/test';

test.describe('7.2 Unauthenticated user attempting to apply is prompted to log in', () => {
  test.skip('requires a project with an open application period in fixture data', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator('a[href*="asumisoikeus"], a[href*="haso"]').first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    const firstCard = page.locator('[class*="card"], article').first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });
    await firstCard.locator('a').first().click();
    await page.waitForLoadState('domcontentloaded');

    const applyButton = page.locator(
      'a:has-text("Hae"), a:has-text("Jätä hakemus"), button:has-text("Hae asuntoa")'
    ).first();

    if (!await applyButton.isVisible().catch(() => false)) {
      test.skip();
      return;
    }

    await applyButton.click();
    await page.waitForLoadState('domcontentloaded');

    // Should be redirected to login or shown login prompt
    const isLoginPage = page.url().includes('/user/login') || page.url().includes('/login');
    const loginPrompt = await page.locator('[class*="login"], a:has-text("Kirjaudu")').isVisible().catch(() => false);
    expect(isLoginPage || loginPrompt, 'Unauthenticated apply should redirect to login').toBe(true);

    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
  });
});
