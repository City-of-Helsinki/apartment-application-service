import { test, expect } from '../utils';

test.describe('5.3 Filtering to an unlikely combination handles emptiness gracefully', () => {
  test('narrow room-count filter does not crash and shows some outcome', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    await page.getByRole('button', { name: 'Huoneiden lukumäärä', exact: true }).click();
    // .check() verifies the native checked state changed, but this widget's
    // custom styling intercepts that; a plain click toggles it visually/in-state.
    await page.getByLabel('5+ Huonetta', { exact: true }).click();
    await page.getByRole('button', { name: 'Hae', exact: true }).first().click();

    await page.waitForLoadState('domcontentloaded');

    await expect(page.locator('body')).not.toContainText('500 Internal Server Error');
    await expect(page.locator('nav, [role="navigation"]').first()).toBeVisible();

    // Either filtered projects or a no-results message — both are acceptable,
    // the point is the page doesn't error or go blank.
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(0);
  });
});
