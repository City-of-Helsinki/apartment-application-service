import { test, expect } from '@playwright/test';

// The listing is a client-side React widget with CSS-module (hashed) class
// names, so "cards" can't be targeted by class. Each project renders as an
// <h3> heading plus a "Tutustu kohteeseen, <project name>" link — those are
// stable across builds and used here instead.

test.describe('3.2 Haso listing displays apartment project cards', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    const href = await hasoLink.getAttribute('href');
    await page.goto(href!);
  });

  test('at least one project heading is visible', async ({ page }) => {
    const headings = page.locator('h3');
    await expect(headings.first()).toBeVisible({ timeout: 10_000 });
    expect(await headings.count()).toBeGreaterThan(0);
  });

  test('each project has a non-empty name and a detail link', async ({ page }) => {
    const headings = page.locator('h3');
    // .count() doesn't auto-retry like toBeVisible() does — wait for the
    // React widget to render before counting, or this races the fetch.
    await expect(headings.first()).toBeVisible({ timeout: 10_000 });
    const count = await headings.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const text = (await headings.nth(i).innerText()).trim();
      expect(text.length).toBeGreaterThan(0);
    }

    const detailLinks = page.getByRole('link', { name: /Tutustu kohteeseen/i });
    await expect(detailLinks.first()).toBeVisible();
  });
});
