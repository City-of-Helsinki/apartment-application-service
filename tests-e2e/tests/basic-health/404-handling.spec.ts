import { test, expect } from '../utils';

test.describe('1.3 404 page is rendered with site chrome', () => {
  test('non-existent page returns 404 with navigation intact', async ({ page }) => {
    const response = await page.goto('/fi/this-page-does-not-exist-abc123xyz');
    expect(response?.status()).toBe(404);

    // Styled page, not blank
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(50);

    // No PHP/Drupal exception text
    await expect(page.locator('body')).not.toContainText('Drupal\\Core');
    await expect(page.locator('body')).not.toContainText('Fatal error');

    // Site navigation still present
    const nav = page.locator('nav, [role="navigation"]').first();
    await expect(nav).toBeVisible();

    // Link back to front page
    const homeLink = page.locator('a[href="/fi"], a[href="/"], a:has-text("Etusivu"), a:has-text("Helsinki")').first();
    await expect(homeLink).toBeVisible();
  });
});
