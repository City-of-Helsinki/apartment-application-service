import { test, expect } from '@playwright/test';

test.describe('3.3 Haso apartment detail page', () => {
  test('clicking first Haso card opens project detail page', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    // Record first card name
    const firstCard = page.locator('[class*="card"], [class*="project"], article').first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });
    const cardTitle = firstCard.locator('h2, h3, h4, [class*="title"]').first();
    const projectName = (await cardTitle.innerText()).trim();

    // Click the card link
    const cardLink = firstCard.locator('a').first();
    await cardLink.click();

    await expect(page).not.toHaveURL(/\/fi\/?$/);
    const response = await page.waitForResponse(resp => resp.url().includes(page.url()) || true, { timeout: 5000 }).catch(() => null);

    const h1 = page.locator('h1').first();
    await expect(h1).toBeVisible();
    const h1Text = (await h1.innerText()).trim();
    expect(h1Text.length).toBeGreaterThan(0);

    // Navigation still intact
    await expect(page.locator('nav, [role="navigation"]').first()).toBeVisible();
  });

  test('detail page shows at least one apartment data field', async ({ page }) => {
    await page.goto('/fi');
    const hasoLink = page.locator(
      'a:has-text("asumisoikeus"), a:has-text("Haso"), a[href*="asumisoikeus"], a[href*="haso"]'
    ).first();
    await page.goto((await hasoLink.getAttribute('href'))!);

    const firstCard = page.locator('[class*="card"], [class*="project"], article').first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });
    await firstCard.locator('a').first().click();

    await page.waitForLoadState('domcontentloaded');

    // At least one of: address, size, price, application period
    const dataField = page.locator(
      '[class*="address"], [class*="price"], [class*="size"], [class*="rooms"], [class*="haku"], ' +
      'dt, dd, table td'
    ).first();
    await expect(dataField).toBeVisible({ timeout: 5_000 });
  });
});
