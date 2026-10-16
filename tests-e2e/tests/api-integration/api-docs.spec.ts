import { test, expect } from '@playwright/test';

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';

test.describe('8.3 API documentation endpoints are accessible', () => {
  test('GET /api_docs/ returns 200 and renders Redoc', async ({ page }) => {
    const response = await page.goto(`${DJANGO_BASE}/api_docs/`);
    expect(response?.status()).toBe(200);

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    // Redoc hydrates via a third-party CDN script into a shadow root; just confirm
    // the Django view served the right template rather than depending on that render.
    await expect(page.locator('redoc')).toHaveCount(1);
  });

  test('GET /api_docs/swagger/ returns 200 and renders Swagger UI', async ({ page }) => {
    const response = await page.goto(`${DJANGO_BASE}/api_docs/swagger/`);
    expect(response?.status()).toBe(200);

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    const hasContent = await page.locator('.swagger-ui, h2, h1').first().isVisible().catch(() => false);
    expect(hasContent).toBe(true);
  });
});
