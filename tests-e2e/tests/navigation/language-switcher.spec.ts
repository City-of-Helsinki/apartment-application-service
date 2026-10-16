import { test, expect } from '../utils';

test.describe('2.2 Language switcher', () => {
  test('language switcher toggle is visible on the front page', async ({ page }) => {
    await page.goto('/fi');
    // The dropdown only lists languages the current page is translated into;
    // this fixture's front page has no Swedish translation, so only the
    // toggle itself (showing the active language) is guaranteed to be present.
    const toggle = page.locator('#lang-switcher-dropdown-desktop, [class*="lang-switcher"]').first();
    await expect(toggle).toBeVisible();
  });

  test('/sv route itself renders in Swedish', async ({ page }) => {
    const response = await page.goto('/sv');
    expect(response?.status()).toBeLessThan(400);
    const lang = await page.locator('html').getAttribute('lang');
    expect(lang?.toLowerCase()).toMatch(/^sv/);
  });

  test('/fi route itself renders in Finnish', async ({ page }) => {
    const response = await page.goto('/fi');
    expect(response?.status()).toBe(200);
    const lang = await page.locator('html').getAttribute('lang');
    expect(lang?.toLowerCase()).toMatch(/^fi/);
  });
});
