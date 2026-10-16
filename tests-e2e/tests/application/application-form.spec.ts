import { test, expect } from '@playwright/test';

test.describe('7.3 Application form displayed to authenticated citizen', () => {
  test.skip('requires Helsinki profile SSO test account — not available in E2E stack', async ({ page }) => {
    // SSO login for citizens is not configured in the local E2E environment.
    // Enable this test once a test citizen account and SSO mock are set up.
  });
});
