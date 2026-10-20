import { test as base, expect } from '@playwright/test';

// Drupal's file_public_base_url is fixed to http://localhost:18080 so a
// human can browse the stack from the host machine with working images/CSS.
// That hostname is unreachable from inside this container, so every page's
// asset requests to it would otherwise fail here. Rewriting them to the
// container-reachable E2E_BASE_URL (drupal-app:8080) keeps both working:
// humans browse via localhost, tests run via drupal-app, same Drupal image.
export const test = base.extend({
  page: async ({ page }, use) => {
    const internalBase = process.env.E2E_BASE_URL;
    if (internalBase) {
      const internalOrigin = internalBase.replace(/\/$/, '');
      await page.route('http://localhost:18080/**', async (route) => {
        const reqUrl = new URL(route.request().url());
        await route.continue({ url: internalOrigin + reqUrl.pathname + reqUrl.search });
      });
    }
    await use(page);
  },
});

export { expect };

// Drupal sometimes renders absolute URLs using the host-facing hostname
// (localhost:18080 here), which is unreachable from inside the test-runner
// container. Extracting just the path keeps navigation going through baseURL.
export function pathOf(href: string): string {
  const url = new URL(href, 'http://placeholder');
  return url.pathname + url.search;
}
