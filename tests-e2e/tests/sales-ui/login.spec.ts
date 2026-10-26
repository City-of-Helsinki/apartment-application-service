import { test, expect } from '../utils';
import {
  FIRST_LOAD_TIMEOUT_MS,
  LOGIN_FLOW_TIMEOUT_MS,
  SALESPERSON_UUID,
  loginButton,
  loginToSalesUi,
  salesUiUrl,
} from './salesUi';

// This suite runs inside the compose network (test-runner container). The
// browser follows OIDC redirects to http://mock-oidc:8080/e2e and the sales
// UI calls the in-network Django service, so those hostnames must resolve
// from where Chromium runs. Shared login helpers live in ./salesUi.

const SALES_API_PATH = '/v1/sales/';
const API_TOKEN_STORAGE_KEY = 'hds_login_api_token_storage_key';
const API_AUDIENCE = 'apartment-application-service';

test.describe('Sales UI login via mock OIDC provider', () => {
  test.beforeEach(async ({}, testInfo) => {
    testInfo.setTimeout(FIRST_LOAD_TIMEOUT_MS + 2 * LOGIN_FLOW_TIMEOUT_MS);
  });

  test('unauthenticated visit redirects to login without sales API data', async ({ page }) => {
    const salesApiOkUrls: string[] = [];
    page.on('response', (response) => {
      if (response.url().includes(SALES_API_PATH) && response.status() === 200) {
        salesApiOkUrls.push(response.url());
      }
    });

    await page.goto(salesUiUrl('/'), { timeout: FIRST_LOAD_TIMEOUT_MS });

    await expect(page).toHaveURL(/\/login$/, { timeout: FIRST_LOAD_TIMEOUT_MS });
    await expect(loginButton(page)).toBeVisible();
    // Websockets (CRA hot reload) do not count towards network idle, so this
    // settles once any API calls the page would make have finished.
    await page.waitForLoadState('networkidle');
    expect(salesApiOkUrls).toEqual([]);
  });

  test('salesperson logs in and the project list is loaded', async ({ page }) => {
    const projectsResponse = await loginToSalesUi(page, SALESPERSON_UUID);

    expect(projectsResponse.status()).toBe(200);
    await expect(page).toHaveURL(/\/projects/);
    await expect(loginButton(page)).toBeHidden();
  });

  test('API token for the sales API is stored in sessionStorage', async ({ page }) => {
    const projectsResponse = await loginToSalesUi(page, SALESPERSON_UUID);
    expect(projectsResponse.status()).toBe(200);

    const raw = await page.evaluate(
      (key) => window.sessionStorage.getItem(key),
      API_TOKEN_STORAGE_KEY,
    );
    expect(raw).not.toBeNull();

    const tokens = JSON.parse(raw as string);
    expect(typeof tokens).toBe('object');
    expect(typeof tokens[API_AUDIENCE]).toBe('string');
    expect(tokens[API_AUDIENCE].length).toBeGreaterThan(0);
  });
});
