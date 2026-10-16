import { test, expect } from '@playwright/test';

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

    const heading = page.locator('h1, h2').first();
    await expect(heading).toContainText(/omistus|Hitas/i);
  });
});
