import { createHash } from 'crypto';
import { test as base, expect } from '@playwright/test';

// Base URL of the e2e seeder sidecar (e2e/seeder/server.py), which resets
// and seeds named scenarios in Django's database on request.
export const SEEDER_URL = (process.env.E2E_SEEDER_URL ?? 'http://localhost:18084').replace(
  /\/$/,
  '',
);

// Pattern the seeder enforces for scenario namespaces.
export const NAMESPACE_PATTERN = /^[a-z0-9-]{1,40}$/;

/**
 * Seed a named scenario through the seeder sidecar.
 *
 * @typeParam T - Shape of the scenario manifest returned by the seeder.
 * @param name - Registered scenario name, e.g. "haso_queue".
 * @param params - Scenario params; `namespace` defaults to one derived from
 *   the running test.
 * @returns The scenario manifest.
 * @throws Error including the HTTP status and response body on non-200.
 */
export type SeedScenario = <T = any>(
  name: string,
  params?: Record<string, unknown>,
) => Promise<T>;

/**
 * Derive a seeder namespace for a test.
 *
 * The namespace is stable for a test id within a worker and distinct between
 * tests, so parallel tests never share seeded customers.
 *
 * @param workerIndex - Playwright worker index.
 * @param testId - Playwright test id.
 * @returns A namespace matching NAMESPACE_PATTERN, e.g. "w0-1a2b3c4d5e".
 */
export function scenarioNamespace(workerIndex: number, testId: string): string {
  const hash = createHash('sha1').update(testId).digest('hex').slice(0, 10);
  const namespace = `w${workerIndex}-${hash}`.toLowerCase().replace(/[^a-z0-9-]/g, '-');
  return namespace.slice(0, 40);
}

interface Fixtures {
  seedScenario: SeedScenario;
}

// Drupal's file_public_base_url is fixed to http://localhost:18080 so a
// human can browse the stack from the host machine with working images/CSS.
// That hostname is unreachable from inside this container, so every page's
// asset requests to it would otherwise fail here. Rewriting them to the
// container-reachable E2E_BASE_URL (drupal-app:8080) keeps both working:
// humans browse via localhost, tests run via drupal-app, same Drupal image.
export const test = base.extend<Fixtures>({
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

  /**
   * Fixture seeding scenarios via POST {SEEDER_URL}/scenarios/{name}.
   *
   * Adds a `namespace` derived from the test (worker index plus a hash of
   * the test id) unless `params.namespace` is given.
   */
  seedScenario: async ({ request }, use, testInfo) => {
    const defaultNamespace = scenarioNamespace(testInfo.workerIndex, testInfo.testId);
    const seedScenario: SeedScenario = async <T = any>(
      name: string,
      params: Record<string, unknown> = {},
    ): Promise<T> => {
      const response = await request.post(
        `${SEEDER_URL}/scenarios/${encodeURIComponent(name)}`,
        { data: { namespace: defaultNamespace, ...params } },
      );
      const body = await response.text();
      if (response.status() !== 200) {
        throw new Error(
          `Seeding scenario "${name}" failed with HTTP ${response.status()}: ${body}`,
        );
      }
      return JSON.parse(body) as T;
    };
    await use(seedScenario);
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
