import { test, expect } from '@playwright/test';

test.describe('1.1 Front page loads in Finnish without errors', () => {
  test('renders with correct language and no server errors', async ({ page }) => {
    // Drupal's file_public_base_url intentionally points at localhost:18080 so
    // images work when a human browses the stack from the host. That host is
    // unreachable from inside this container, so those specific requests are a
    // known gap here, not a real bug — only fail on requests to our own origin.
    const unexpectedFailures: string[] = [];
    page.on('requestfailed', req => {
      if (!req.url().includes('localhost:18080')) {
        unexpectedFailures.push(`${req.url()} — ${req.failure()?.errorText}`);
      }
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

    await page.waitForLoadState('networkidle').catch(() => {});
    expect(unexpectedFailures, `Unexpected request failures: ${unexpectedFailures.join(', ')}`).toHaveLength(0);
  });
});
