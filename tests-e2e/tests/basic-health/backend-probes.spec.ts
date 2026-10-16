import { test, expect } from '@playwright/test';

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';

test.describe('1.4 Django backend health probes', () => {
  test('GET /healthz returns 200', async ({ request }) => {
    const response = await request.get(`${DJANGO_BASE}/healthz`);
    expect(response.status()).toBe(200);
  });

  test('GET /readiness returns 200', async ({ request }) => {
    const response = await request.get(`${DJANGO_BASE}/readiness`);
    expect(response.status()).toBe(200);
  });
});
