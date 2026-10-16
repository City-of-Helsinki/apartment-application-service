import { test, expect } from '../utils';

// The listing is a client-side React widget with CSS-module (hashed) class
// names, so "cards" can't be targeted by class. Each project renders as an
// <h3> heading plus a "Tutustu kohteeseen, <project name>" link — those are
// stable across builds and used here instead.

test.describe('4.2 Hitas listing displays project cards with ownership type label', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/fi');
    const hitasLink = page.locator(
      'a:has-text("omistus"), a:has-text("Hitas"), a[href*="omistus"], a[href*="hitas"]'
    ).first();
    await page.goto((await hitasLink.getAttribute('href'))!);
  });

  test('at least one project heading is visible', async ({ page }) => {
    const headings = page.locator('h3');
    await expect(headings.first()).toBeVisible({ timeout: 10_000 });
    expect(await headings.count()).toBeGreaterThan(0);
  });

  test('projects have non-empty names and a detail link', async ({ page }) => {
    const headings = page.locator('h3');
    // .count() doesn't auto-retry like toBeVisible() does — wait for the
    // React widget to render before counting, or this races the fetch.
    await expect(headings.first()).toBeVisible({ timeout: 10_000 });
    const count = await headings.count();
    expect(count).toBeGreaterThan(0);

    const text = (await headings.first().innerText()).trim();
    expect(text.length).toBeGreaterThan(0);

    const detailLinks = page.getByRole('link', { name: /Tutustu kohteeseen/i });
    await expect(detailLinks.first()).toBeVisible();
  });

  test('page heading indicates ownership (omistus/Hitas) context', async ({ page }) => {
    const heading = page.locator('h1').first();
    await expect(heading).toContainText(/omistus|Hitas/i);
  });
});
