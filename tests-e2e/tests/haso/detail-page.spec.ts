import { test, expect } from '@playwright/test';
import { pathOf } from '../utils';

test.describe('3.3 Haso apartment detail page', () => {
  test('clicking first project link opens its detail page', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    const projectName = (await page.locator('h3').first().innerText()).trim();

    // The detail link is rendered as an absolute URL using the host-facing
    // hostname (localhost:18080), which is unreachable from this container —
    // extract the path and navigate through baseURL instead of clicking it.
    const detailLink = page.getByRole('link', { name: /Tutustu kohteeseen/i }).first();
    const href = await detailLink.getAttribute('href');
    await page.goto(pathOf(href!));

    const h1 = page.locator('h1').first();
    await expect(h1).toBeVisible();
    await expect(h1).toContainText(projectName.split(' / ')[0]);

    await expect(page.locator('nav, [role="navigation"]').first()).toBeVisible();
  });

  test('detail page shows apartment data fields', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    const detailLink = page.getByRole('link', { name: /Tutustu kohteeseen/i }).first();
    const href = await detailLink.getAttribute('href');
    await page.goto(pathOf(href!));

    await expect(page.getByText('Yksityiskohdat', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/Kaupunginosa|Pinta-ala|Huoneita/).first()).toBeVisible();
  });
});
