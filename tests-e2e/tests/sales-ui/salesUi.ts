import type { Page, Response } from '@playwright/test';

// Shared helpers for the sales UI specs. These run inside the compose network
// (test-runner container): the browser follows OIDC redirects to
// http://mock-oidc:8080/e2e and the sales UI calls the in-network Django
// service, so those hostnames must resolve from where Chromium runs.
//
// The configured baseURL points at Drupal, so every sales UI navigation uses
// an absolute URL built from E2E_SALES_UI_URL.

export const SALES_UI_BASE = (process.env.E2E_SALES_UI_URL ?? 'http://localhost:13000').replace(
  /\/$/,
  '',
);

// Seeded into Django's django_salesperson group by run-e2e.sh.
export const SALESPERSON_UUID = '8a5d3c1e-2f4b-4c6d-9e8f-0a1b2c3d4e5f';
// Default UI language is fi (att-sales-ui src/i18n/i18n.ts); text from
// pages.auth.Login.login in src/i18n/fi.json.
export const LOGIN_BUTTON_TEXT = 'Kirjaudu sisään';
export const PROJECTS_API_PATH = '/v1/sales/projects/';

// The CRA dev server compiles the bundle on its first request, which can take
// far longer than a normal page load; later navigations are fast.
export const FIRST_LOAD_TIMEOUT_MS = 60_000;
export const LOGIN_FLOW_TIMEOUT_MS = 30_000;

/**
 * Build an absolute sales UI URL for a path.
 *
 * @param path - Path beginning with "/".
 * @returns Absolute URL on the sales UI origin.
 */
export function salesUiUrl(path: string): string {
  return `${SALES_UI_BASE}${path}`;
}

/**
 * Locate the login page's login button.
 *
 * Scoped to <main> because the HDS header renders a second button with the
 * same accessible name while unauthenticated.
 *
 * @param page - Playwright page.
 * @returns Locator for the in-page login button.
 */
export function loginButton(page: Page) {
  return page.getByRole('main').getByRole('button', { name: LOGIN_BUTTON_TEXT });
}

/**
 * Log in to the sales UI through the mock OIDC interactive login page.
 *
 * Opens the UI, clicks the login button, submits the mock's form with the
 * given username (the token subject) and waits for the projects API call
 * that the UI makes after the callback.
 *
 * @param page - Playwright page.
 * @param username - Subject for the issued token (salesperson uuid).
 * @returns The first GET response from the Django projects endpoint.
 */
export async function loginToSalesUi(page: Page, username: string): Promise<Response> {
  await page.goto(salesUiUrl('/'), { timeout: FIRST_LOAD_TIMEOUT_MS });
  await loginButton(page).click({ timeout: FIRST_LOAD_TIMEOUT_MS });

  const usernameInput = page.locator('input[name="username"]');
  await usernameInput.waitFor({ state: 'visible', timeout: LOGIN_FLOW_TIMEOUT_MS });
  await usernameInput.fill(username);

  // Registered before submitting so the response cannot be missed. Any GET
  // is matched (not only 200) so a 401/403 fails fast with a clear status.
  const projectsResponse = page.waitForResponse(
    (response) =>
      response.url().includes(PROJECTS_API_PATH) && response.request().method() === 'GET',
    { timeout: LOGIN_FLOW_TIMEOUT_MS },
  );
  await usernameInput.press('Enter');
  return projectsResponse;
}
