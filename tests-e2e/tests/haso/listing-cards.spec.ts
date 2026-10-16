import { test, expect } from '@playwright/test';

test.describe('3.2 Haso listing displays apartment project cards', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    const href = await hasoLink.getAttribute('href');
    await page.goto(href!);
  });

  test('at least one project card is visible', async ({ page }) => {
    const cards = page.locator(
      '[class*="card"], [class*="project"], article, li[class*="apartment"]'
    );
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('each card contains a project name', async ({ page }) => {
    const cards = page.locator('[class*="card"], [class*="project"], article').filter({ hasText: /.+/ });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const heading = cards.nth(i).locator('h2, h3, h4, [class*="title"], [class*="name"]').first();
      await expect(heading).toBeVisible();
      const text = await heading.innerText();
      expect(text.trim().length).toBeGreaterThan(0);
    }
  });
});
