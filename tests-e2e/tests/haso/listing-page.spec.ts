import { test, expect } from '../utils';

test.describe('3.1 Haso listing page accessible from main navigation', () => {
  test('nav contains Haso/asumisoikeus link that loads with 200', async ({ page }) => {
    await page.goto('/fi');

    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await expect(hasoLink).toBeVisible();

    const href = await hasoLink.getAttribute('href');
    const response = await page.goto(href!);
    expect(response?.status()).toBe(200);

    await expect(page).toHaveURL(/asumisoikeus|haso/i);

    // The real <h1> ("Etsi HASO-asumisoikeusasuntoja") is rendered client-side by
    // the React search widget; `h1, h2` would otherwise match a visually-hidden
    // nav heading that appears earlier in the DOM.
    const heading = page.locator('h1').first();
    await expect(heading).toContainText(/asumisoikeus|Haso/i);
  });
});
