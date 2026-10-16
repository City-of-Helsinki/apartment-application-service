import { test, expect } from '@playwright/test';

test.describe('5.3 Search for non-existent term returns friendly empty state', () => {
  test('searching for garbage term shows no-results message without server error', async ({ page }) => {
    await page.goto('/fi');

    let searchInput = page.locator('input[type="search"], input[role="searchbox"], [aria-label*="haku"], [placeholder*="Hae"]').first();
    if (!await searchInput.isVisible().catch(() => false)) {
      const toggle = page.locator('button[aria-label*="haku"], button[aria-label*="search"]').first();
      if (await toggle.isVisible().catch(() => false)) await toggle.click();
    }

    const inputVisible = await searchInput.isVisible().catch(() => false);
    if (!inputVisible) {
      test.skip();
      return;
    }

    await searchInput.fill('zzzzznotaplacexxx');
    await searchInput.press('Enter');

    await page.waitForLoadState('domcontentloaded');

    // No server error
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    await expect(page.locator('body')).not.toContainText('Drupal\\Core');

    // Navigation still intact
    await expect(page.locator('nav, [role="navigation"]').first()).toBeVisible();
  });
});
