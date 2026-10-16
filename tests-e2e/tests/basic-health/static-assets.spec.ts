import { test, expect } from '@playwright/test';

test.describe('1.2 Static assets are served from the correct host', () => {
  test('no assets use the internal drupal-app hostname', async ({ page }) => {
    const internalHostRequests: string[] = [];
    const failedAssets: string[] = [];

    page.on('response', response => {
      const url = response.url();
      if (url.includes('drupal-app')) {
        internalHostRequests.push(url);
      }
      if (/\.(css|js|png|jpe?g|gif|svg|webp|woff2?)(\?|$)/i.test(url) && response.status() >= 400) {
        failedAssets.push(`HTTP ${response.status()} – ${url}`);
      }
    });

    await page.goto('/fi');
    await page.waitForLoadState('networkidle');

    expect(internalHostRequests, 'Requests to internal drupal-app hostname').toHaveLength(0);
    expect(failedAssets, 'Static assets with 4xx/5xx response').toHaveLength(0);
  });

  test('CSS and JS files return 200', async ({ page }) => {
    const cssErrors: string[] = [];
    const jsErrors: string[] = [];

    page.on('response', response => {
      const url = response.url();
      const status = response.status();
      if (url.includes('.css') && status >= 400) cssErrors.push(`${status} ${url}`);
      if (url.includes('.js') && status >= 400) jsErrors.push(`${status} ${url}`);
    });

    await page.goto('/fi');
    await page.waitForLoadState('networkidle');

    expect(cssErrors, 'CSS files with errors').toHaveLength(0);
    expect(jsErrors, 'JS files with errors').toHaveLength(0);
  });
});
