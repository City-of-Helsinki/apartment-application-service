import { test, expect } from '@playwright/test';

test.describe('7.1 Apply button visible on a project detail page', () => {
  test.skip('requires a project with an open application period in fixture data', async ({ page }) => {
    // Navigate to a Haso detail page
    await page.goto('/fi');
    const hasoLink = page.locator('a[href*="asumisoikeus"], a[href*="haso"]').first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    const firstCard = page.locator('[class*="card"], article').first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });
    await firstCard.locator('a').first().click();
    await page.waitForLoadState('domcontentloaded');

    // Apply CTA
    const applyButton = page.locator(
      'a:has-text("Hae"), a:has-text("Jätä hakemus"), a:has-text("Apply"), button:has-text("Hae asuntoa")'
    ).first();
    await expect(applyButton).toBeVisible();
    await expect(applyButton).toBeEnabled();
  });
});
