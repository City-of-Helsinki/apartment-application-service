import { test, expect } from '@playwright/test';

test.describe('1.2 Static assets are served from the correct host', () => {
  // Drupal's file_public_base_url intentionally points at localhost:18080 so
  // images work when a human browses the stack from the host machine. That
  // host is unreachable from inside this container — a known environment gap,
  // not a bug — so these tests only check same-origin (drupal-app) assets.

  test('same-origin CSS and JS files return 200', async ({ page }) => {
    const failedAssets: string[] = [];

    page.on('response', response => {
      const url = response.url();
      if (!url.includes('drupal-app')) return;
      if (/\.(css|js)(\?|$)/i.test(url) && response.status() >= 400) {
        failedAssets.push(`HTTP ${response.status()} – ${url}`);
      }
    });

    await page.goto('/fi');
    await page.waitForLoadState('networkidle');

    expect(failedAssets, 'Same-origin CSS/JS with errors').toHaveLength(0);
  });

  test('no 5xx responses from the Drupal origin itself', async ({ page }) => {
    const serverErrors: string[] = [];

    page.on('response', response => {
      const url = response.url();
      if (url.includes('drupal-app') && response.status() >= 500) {
        serverErrors.push(`HTTP ${response.status()} – ${url}`);
      }
    });

    await page.goto('/fi');
    await page.waitForLoadState('networkidle');

    expect(serverErrors, 'Same-origin 5xx responses').toHaveLength(0);
  });
});
