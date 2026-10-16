import { test, expect } from '@playwright/test';

test.describe('2.1 Main navigation is present and links are reachable', () => {
  test('primary nav element is visible', async ({ page }) => {
    await page.goto('/fi');
    const nav = page.locator('nav, [role="navigation"]').first();
    await expect(nav).toBeVisible();
  });

  test('top-level nav links are present and have non-empty hrefs', async ({ page }) => {
    await page.goto('/fi');
    const links = page.locator('nav a, [role="navigation"] a').filter({ hasNotText: '' });
    const count = await links.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(count, 5); i++) {
      const href = await links.nth(i).getAttribute('href');
      expect(href?.trim().length).toBeGreaterThan(0);
    }
  });

  test('clicking first top-level nav link opens a valid page', async ({ page }) => {
    await page.goto('/fi');
    const links = page.locator('nav a[href^="/fi"], [role="navigation"] a[href^="/fi"]').filter({ hasNotText: '' });
    const count = await links.count();
    expect(count).toBeGreaterThan(0);

    const href = await links.first().getAttribute('href');
    const response = await page.goto(href!);
    expect(response?.status()).toBeLessThan(400);
  });
});
