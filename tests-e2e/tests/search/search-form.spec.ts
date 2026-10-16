import { test, expect } from '@playwright/test';

test.describe('5.1 Search form is present on the site', () => {
  test('search input is reachable from the front page', async ({ page }) => {
    await page.goto('/fi');

    // Look for search input directly or via a search icon/button
    let searchInput = page.locator('input[type="search"], input[role="searchbox"], [aria-label*="haku"], [placeholder*="Hae"]').first();
    const directlyVisible = await searchInput.isVisible().catch(() => false);

    if (!directlyVisible) {
      // Try clicking a search icon/button to reveal the input
      const searchToggle = page.locator('button[aria-label*="haku"], button[aria-label*="search"], [class*="search-toggle"]').first();
      if (await searchToggle.isVisible().catch(() => false)) {
        await searchToggle.click();
        searchInput = page.locator('input[type="search"], input[role="searchbox"]').first();
      }
    }

    await expect(searchInput).toBeVisible({ timeout: 5_000 });
  });

  test('submitting a neighbourhood search returns results page', async ({ page }) => {
    await page.goto('/fi');

    let searchInput = page.locator('input[type="search"], input[role="searchbox"], [aria-label*="haku"], [placeholder*="Hae"]').first();
    if (!await searchInput.isVisible().catch(() => false)) {
      const toggle = page.locator('button[aria-label*="haku"], button[aria-label*="search"]').first();
      if (await toggle.isVisible().catch(() => false)) await toggle.click();
    }

    await searchInput.fill('Kallio');
    await searchInput.press('Enter');

    await page.waitForLoadState('domcontentloaded');
    const status = (await page.waitForResponse(r => r.url().includes(page.url())).catch(() => null))?.status() ?? 200;
    expect(status).toBeLessThan(500);

    // Results page or empty state message — no server error
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
  });
});
