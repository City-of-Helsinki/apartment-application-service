import { test, expect } from '@playwright/test';

const DJANGO_BASE = 'http://localhost:18081';

test.describe('8.3 API documentation endpoints are accessible', () => {
  test('GET /api_docs/ returns 200 and renders Redoc', async ({ page }) => {
    const response = await page.goto(`${DJANGO_BASE}/api_docs/`);
    expect(response?.status()).toBe(200);

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    // Redoc renders a heading or its custom elements
    const hasContent = await page.locator('redoc, h1, h2').first().isVisible().catch(() => false);
    expect(hasContent).toBe(true);
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
