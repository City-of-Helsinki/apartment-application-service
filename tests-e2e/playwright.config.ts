import { defineConfig, devices } from '@playwright/test';

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
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
