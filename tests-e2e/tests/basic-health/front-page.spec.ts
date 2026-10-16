import { test, expect } from '@playwright/test';

test.describe('1.1 Front page loads in Finnish without errors', () => {
  test('renders with correct language and no server errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    const response = await page.goto('/fi');
    expect(response?.status()).toBe(200);

    const lang = await page.locator('html').getAttribute('lang');
    expect(lang?.toLowerCase()).toMatch(/^fi/);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(0);

    await expect(page.locator('body')).not.toContainText('403 Forbidden');
    await expect(page.locator('body')).not.toContainText('404 Not Found');
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    // No raw PHP/Drupal exception visible
    await expect(page.locator('body')).not.toContainText('Drupal\\Core');

    expect(consoleErrors, `Console errors: ${consoleErrors.join(', ')}`).toHaveLength(0);
  });
});
