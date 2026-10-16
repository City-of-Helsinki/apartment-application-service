import { test, expect } from '@playwright/test';

test.describe('2.2 Language switcher', () => {
  test('language switcher is visible on the front page', async ({ page }) => {
    await page.goto('/fi');
    const switcher = page.locator('a:has-text("SV"), a:has-text("Svenska"), a[hreflang="sv"], a[href*="/sv"]').first();
    await expect(switcher).toBeVisible();
  });

  test('clicking SV switches site to Swedish', async ({ page }) => {
    await page.goto('/fi');
    const svLink = page.locator('a:has-text("SV"), a:has-text("Svenska"), a[hreflang="sv"], a[href*="/sv/"]').first();
    await svLink.click();

    await expect(page).toHaveURL(/\/sv\//);
    const lang = await page.locator('html').getAttribute('lang');
    expect(lang?.toLowerCase()).toMatch(/^sv/);
  });

  test('clicking FI from Swedish returns to Finnish', async ({ page }) => {
    await page.goto('/sv');
    const fiLink = page.locator('a:has-text("FI"), a:has-text("Suomi"), a[hreflang="fi"], a[href*="/fi/"]').first();
    await fiLink.click();

    await expect(page).toHaveURL(/\/fi\//);
    const lang = await page.locator('html').getAttribute('lang');
    expect(lang?.toLowerCase()).toMatch(/^fi/);
  });
});
