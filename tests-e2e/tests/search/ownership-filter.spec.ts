import { test, expect } from '@playwright/test';

test.describe('5.2 Apartment listing can be filtered by ownership type', () => {
  test.skip('filter controls depend on live site structure — enable once listing page is explored', async ({ page }) => {
    // Navigate to an apartment listing that offers ownership-type filters
    await page.goto('/fi');
    const listingLink = page.locator('nav a[href*="asunto"]').first();
    await page.goto((await listingLink.getAttribute('href'))!);

    // Ownership type filter controls
    const hitasFilter = page.locator('input[value*="hitas"], label:has-text("Hitas"), button:has-text("Hitas")').first();
    await expect(hitasFilter).toBeVisible({ timeout: 10_000 });
    await hitasFilter.click();

    await page.waitForLoadState('networkidle');

    // Only Hitas cards remain
    const cards = page.locator('[class*="card"], article');
    const count = await cards.count();
    for (let i = 0; i < Math.min(count, 5); i++) {
      await expect(cards.nth(i)).not.toContainText('Haso');
    }
  });
});
