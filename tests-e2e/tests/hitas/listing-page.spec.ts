import { test, expect } from '../utils';

test.describe('4.1 Hitas listing page accessible from main navigation', () => {
  test('nav contains Hitas/omistusasunnot link that loads with 200', async ({ page }) => {
    await page.goto('/fi');

    const hitasLink = page.locator(
      'a:has-text("omistus"), a:has-text("Hitas"), a[href*="omistus"], a[href*="hitas"]'
    ).first();
    await expect(hitasLink).toBeVisible();

    const href = await hitasLink.getAttribute('href');
    const response = await page.goto(href!);
    expect(response?.status()).toBe(200);

    await expect(page).toHaveURL(/omistus|hitas/i);

    // The real <h1> ("Etsi Hitas-omistusasuntoja") is rendered client-side by
    // the React search widget; `h1, h2` would otherwise match a visually-hidden
    // nav heading that appears earlier in the DOM.
    const heading = page.locator('h1').first();
    await expect(heading).toContainText(/omistus|Hitas/i);
  });
});
