import { defineConfig, devices } from '@playwright/test';

/**
 * Return the origin (scheme://host:port) of a URL.
 *
 * @param url - Absolute URL.
 * @returns The URL's origin.
 */
function originOf(url: string): string {
  return new URL(url).origin;
}

// The sales UI's OIDC client (oidc-client-ts) needs crypto.subtle for PKCE,
// which browsers expose only in secure contexts. In the compose network the
// UI and the mock OIDC provider are plain http on non-localhost hostnames,
// so Chromium is told to treat exactly those origins as secure.
const insecureOriginsTreatedAsSecure = [
  originOf(process.env.E2E_SALES_UI_URL ?? 'http://localhost:13000'),
  originOf(process.env.E2E_OIDC_URL ?? 'http://localhost:18083'),
].join(',');

export default defineConfig({
  testDir: '.',
  fullyParallel: true,
  // Each worker is a full Chromium instance recording video continuously
  // (for video/screenshot retain-on-failure); Docker Desktop's VM memory is
  // shared with whatever else is running on the host, so too many parallel
  // workers causes real, flaky "Page crashed" / timeout failures rather than
  // revealing actual bugs. Override with PLAYWRIGHT_WORKERS if your machine
  // has headroom to spare.
  workers: process.env.PLAYWRIGHT_WORKERS ? Number(process.env.PLAYWRIGHT_WORKERS) : 2,
  reporter: 'html',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:18080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [`--unsafely-treat-insecure-origin-as-secure=${insecureOriginsTreatedAsSecure}`],
        },
      },
    },
  ],
});
