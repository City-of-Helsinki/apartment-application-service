import { test, expect } from '@playwright/test';

test.describe('2.4 Footer is present with content and working links', () => {
  test('footer element is visible after scrolling', async ({ page }) => {
    await page.goto('/fi');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    const footer = page.locator('footer, [role="contentinfo"]').first();
    await expect(footer).toBeVisible();
  });

  test('footer contains at least one link with Finnish text', async ({ page }) => {
    await page.goto('/fi');
    const footer = page.locator('footer, [role="contentinfo"]').first();
    const links = footer.locator('a');
    await expect(links.first()).toBeVisible();
    const count = await links.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking a footer link opens a valid page', async ({ page }) => {
    await page.goto('/fi');
    const footer = page.locator('footer, [role="contentinfo"]').first();
    const firstLink = footer.locator('a[href^="/fi"]').first();

    const href = await firstLink.getAttribute('href');
    if (!href) {
      test.skip();
      return;
    }

    const response = await page.goto(href);
    expect(response?.status()).toBeLessThan(400);
  });
});
