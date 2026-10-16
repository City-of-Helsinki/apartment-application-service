import { test, expect } from '../utils';

test.describe('4.4 Cross-listing navigation between Haso and Hitas', () => {
  test('can navigate from Haso listing to Hitas listing without errors', async ({ page }) => {
    await page.goto('/fi');

    // Navigate to Haso
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    const hasoHref = await hasoLink.getAttribute('href');
    let response = await page.goto(hasoHref!);
    expect(response?.status()).toBe(200);

    // Go back to front page
    await page.goto('/fi');

    // Navigate to Hitas
    const hitasLink = page.locator(
      'a:has-text("omistus"), a:has-text("Hitas"), a[href*="omistus"], a[href*="hitas"]'
    ).first();
    const hitasHref = await hitasLink.getAttribute('href');
    response = await page.goto(hitasHref!);
    expect(response?.status()).toBe(200);

    // No stale session error
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    await expect(page.locator('body')).not.toContainText('Session expired');
  });
});
