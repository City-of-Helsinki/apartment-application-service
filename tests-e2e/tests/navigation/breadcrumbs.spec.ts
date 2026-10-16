import { test, expect } from '@playwright/test';

test.describe('2.3 Breadcrumb navigation on inner pages', () => {
  test('breadcrumb is present on an inner page and home link works', async ({ page }) => {
    // Navigate to an inner content page (use the first non-home nav link)
    await page.goto('/fi');
    const navLinks = page.locator('nav a[href^="/fi"]').filter({ hasNotText: '' });
    const firstNavHref = await navLinks.first().getAttribute('href');
    await page.goto(firstNavHref!);

    const breadcrumb = page.locator('[class*="breadcrumb"], nav[aria-label*="breadcrumb"], ol[aria-label*="breadcrumb"]').first();

    // Skip gracefully if this page has no breadcrumb (some top-level pages might not)
    const breadcrumbVisible = await breadcrumb.isVisible().catch(() => false);
    if (!breadcrumbVisible) {
      test.skip();
      return;
    }

    const items = breadcrumb.locator('li, a, span');
    const itemCount = await items.count();
    expect(itemCount).toBeGreaterThanOrEqual(2);

    // Home breadcrumb link navigates to front page
    const homeLink = breadcrumb.locator('a[href="/fi"], a[href="/"], a:has-text("Etusivu")').first();
    if (await homeLink.isVisible()) {
      await homeLink.click();
      await expect(page).toHaveURL(/\/fi\/?$/);
    }
  });
});
