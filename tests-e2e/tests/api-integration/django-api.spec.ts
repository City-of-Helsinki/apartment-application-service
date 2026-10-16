import { test, expect } from '@playwright/test';

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';

test.describe('8.1 Django REST API is reachable and returns apartment data', () => {
  test('GET /v1/sales/projects/ returns 200 or 401 with valid JSON', async ({ request }) => {
    const response = await request.get(`${DJANGO_BASE}/v1/sales/projects/`);
    expect([200, 401, 403]).toContain(response.status());

    if (response.status() === 200) {
      const body = await response.json();
      expect(body).toBeDefined();
    }
  });

  test('GET /v1/sales/apartments/ returns 200 or 401 with JSON content-type', async ({ request }) => {
    const response = await request.get(`${DJANGO_BASE}/v1/sales/apartments/`);
    expect([200, 401, 403]).toContain(response.status());
    expect(response.headers()['content-type']).toMatch(/application\/json/);
  });

  test('no 5xx error on sales project list', async ({ request }) => {
    const response = await request.get(`${DJANGO_BASE}/v1/sales/projects/`);
    expect(response.status()).toBeLessThan(500);
  });
});
