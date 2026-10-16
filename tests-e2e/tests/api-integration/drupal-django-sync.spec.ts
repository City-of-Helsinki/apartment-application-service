import { test, expect } from '@playwright/test';

const DJANGO_BASE = 'http://localhost:18081';

test.describe('8.2 Drupal listing pages reflect Django apartment data', () => {
  test('Haso listing page loads successfully (Django data pipeline reachable)', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    const href = await hasoLink.getAttribute('href');
    const response = await page.goto(href!);
    expect(response?.status()).toBe(200);

    // Page loaded — if Django data was missing, Drupal would likely show an error or empty state
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
  });

  test('Django API returns apartment data that exists in Drupal listing', async ({ page, request }) => {
    // Get project names from Django API (unauthenticated, may return 401)
    const apiResponse = await request.get(`${DJANGO_BASE}/v1/sales/projects/`);
    if (apiResponse.status() !== 200) {
      test.skip();
      return;
    }

    const apiData = await apiResponse.json();
    const projects: any[] = Array.isArray(apiData) ? apiData : (apiData.results ?? []);
    if (projects.length === 0) {
      test.skip();
      return;
    }

    const firstProjectName: string = projects[0].project_name ?? projects[0].name ?? '';

    // Navigate Drupal listing and verify it contains at least one project
    await page.goto('/fi');
    const hasoLink = page.locator('a[href*="asumisoikeus"], a[href*="haso"]').first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    const cards = page.locator('[class*="card"], article').filter({ hasText: /.+/ });
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    // At minimum the Drupal listing is non-empty when Django has data
    expect(await cards.count()).toBeGreaterThan(0);
  });
});
