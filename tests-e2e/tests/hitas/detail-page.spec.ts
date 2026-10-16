import { test, expect } from '@playwright/test';

test.describe('4.3 Hitas apartment detail page', () => {
  test('clicking first Hitas card opens project detail page with matching heading', async ({ page }) => {
    await page.goto('/fi');
    const hitasLink = page.locator(
      'a:has-text("omistus"), a:has-text("Hitas"), a[href*="omistus"], a[href*="hitas"]'
    ).first();
    await page.goto((await hitasLink.getAttribute('href'))!);

    const firstCard = page.locator('[class*="card"], [class*="project"], article').first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });

    await firstCard.locator('a').first().click();
    await page.waitForLoadState('domcontentloaded');

    const h1 = page.locator('h1').first();
    await expect(h1).toBeVisible();
    expect((await h1.innerText()).trim().length).toBeGreaterThan(0);

    await expect(page.locator('nav, [role="navigation"]').first()).toBeVisible();
  });

  test('detail page contains at least one apartment data field', async ({ page }) => {
    await page.goto('/fi');
    const hitasLink = page.locator(
      'a:has-text("omistus"), a:has-text("Hitas"), a[href*="omistus"], a[href*="hitas"]'
    ).first();
    await page.goto((await hitasLink.getAttribute('href'))!);

    const firstCard = page.locator('[class*="card"], [class*="project"], article').first();
    await expect(firstCard).toBeVisible({ timeout: 10_000 });
    await firstCard.locator('a').first().click();
    await page.waitForLoadState('domcontentloaded');

    const dataField = page.locator(
      '[class*="address"], [class*="price"], [class*="size"], [class*="rooms"], dt, dd, table td'
    ).first();
    await expect(dataField).toBeVisible({ timeout: 5_000 });
  });
});
