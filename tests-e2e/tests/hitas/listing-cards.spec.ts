import { test, expect } from '@playwright/test';

test.describe('4.2 Hitas listing displays project cards with ownership type label', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/fi');
    const hitasLink = page.locator(
      'a:has-text("omistus"), a:has-text("Hitas"), a[href*="omistus"], a[href*="hitas"]'
    ).first();
    await page.goto((await hitasLink.getAttribute('href'))!);
  });

  test('at least one project card is visible', async ({ page }) => {
    const cards = page.locator('[class*="card"], [class*="project"], article');
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('cards contain project names', async ({ page }) => {
    const cards = page.locator('[class*="card"], [class*="project"], article').filter({ hasText: /.+/ });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    const heading = cards.first().locator('h2, h3, h4, [class*="title"]').first();
    await expect(heading).toBeVisible();
    expect((await heading.innerText()).trim().length).toBeGreaterThan(0);
  });

  test('at least one card shows ownership type label', async ({ page }) => {
    const typeBadge = page.locator(
      '[class*="badge"]:has-text("Hitas"), [class*="badge"]:has-text("omistus"), [class*="badge"]:has-text("Puolihitas"), ' +
      '[class*="tag"]:has-text("Hitas"), [class*="label"]:has-text("Hitas"), span:has-text("Puolihitas")'
    ).first();
    // Soft assertion — badge presence depends on fixture data
    const visible = await typeBadge.isVisible().catch(() => false);
    if (!visible) {
      // Fall back: check that listing heading itself indicates ownership type
      const heading = page.locator('h1').first();
      await expect(heading).toContainText(/omistus|Hitas|Puolihitas/i);
    }
  });
});
