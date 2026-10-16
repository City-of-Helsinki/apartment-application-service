import { test, expect } from '@playwright/test';

// There is no site-wide search box; apartment search is a set of filter
// dropdowns (district, room count, area, price) scoped to each listing page.
test.describe('5.1 Apartment filter controls are present and usable', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await page.goto((await hasoLink.getAttribute('href'))!);
  });

  test('district, room count, and submit controls are visible', async ({ page }) => {
    // exact: true matters — "Kaupunginosa" otherwise also matches the
    // "Tyhjennä valinnat, Kaupunginosa" clear button.
    await expect(page.getByRole('button', { name: 'Kaupunginosa', exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: 'Huoneiden lukumäärä', exact: true })).toBeVisible();
    // Several "Hae" buttons exist (one per filter group plus the main submit).
    await expect(page.getByRole('button', { name: 'Hae', exact: true }).first()).toBeVisible();
  });

  test('selecting a district filter and submitting does not error', async ({ page }) => {
    await page.getByRole('button', { name: 'Kaupunginosa', exact: true }).click();
    // .check() verifies the native checked state changed, but this widget's
    // custom styling intercepts that; a plain click toggles it visually/in-state.
    await page.getByLabel('Kallio', { exact: true }).click();
    await page.getByRole('button', { name: 'Hae', exact: true }).first().click();

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    await expect(page.locator('nav, [role="navigation"]').first()).toBeVisible();
  });
});
