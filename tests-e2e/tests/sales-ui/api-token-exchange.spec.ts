import type { APIRequestContext, APIResponse } from '@playwright/test';
import { test, expect } from '../utils';

// This suite runs inside the compose network (test-runner container). The
// mock OIDC provider derives each token's `iss` from the host used to reach
// it, and Django only trusts http://mock-oidc:8080/e2e, so E2E_OIDC_URL must
// point at the in-network mock-oidc service for tokens to be accepted.
//
// The requests here mirror what hds-react's LoginProvider sends from the
// sales UI when it exchanges the user's access token for an API token.

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';
const OIDC_BASE = process.env.E2E_OIDC_URL ?? 'http://localhost:18083';
const GRANT_TYPE =
  process.env.E2E_API_GRANT_TYPE ?? 'urn:ietf:params:oauth:grant-type:uma-ticket';

const AUDIENCE = 'apartment-application-service';
const OTHER_AUDIENCE = 'some-other-api';
const TOKEN_EXCHANGE_URL = `${OIDC_BASE}/e2e/token`;
const PROTECTED_URL = `${DJANGO_BASE}/v1/sales/projects/`;

/**
 * Fetch a salesperson "user access token" from the mock OIDC provider.
 *
 * Uses client_credentials with scope `e2e-salesperson`, identical to the
 * phase 1 fetchToken request, as a stand-in for the token the browser gets
 * from the authorization_code flow.
 *
 * @param request - Playwright API request context.
 * @returns The raw access token (JWT) string.
 */
async function fetchUserToken(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${OIDC_BASE}/e2e/token`, {
    form: {
      grant_type: 'client_credentials',
      client_id: 'e2e-client',
      client_secret: 'e2e-secret',
      scope: 'e2e-salesperson',
    },
  });
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(typeof body.access_token).toBe('string');
  return body.access_token;
}

/**
 * Exchange a user access token for an API token the way hds-react does.
 *
 * Sends POST to the token exchange URL with the user token as Bearer and a
 * form body of audience, grant_type and permission=#access.
 *
 * @param request - Playwright API request context.
 * @param userToken - User access token sent in the Authorization header.
 * @param audience - Audience (API) the token is requested for.
 * @returns The unasserted token exchange response.
 */
async function exchangeApiToken(
  request: APIRequestContext,
  userToken: string,
  audience: string,
): Promise<APIResponse> {
  return request.post(TOKEN_EXCHANGE_URL, {
    headers: { Authorization: `Bearer ${userToken}` },
    form: {
      audience,
      grant_type: GRANT_TYPE,
      permission: '#access',
    },
  });
}

test.describe('Sales UI API token exchange against the mock OIDC provider', () => {
  test('exchanged API token is accepted by the Django sales API', async ({ request }) => {
    const userToken = await fetchUserToken(request);

    const exchange = await exchangeApiToken(request, userToken, AUDIENCE);
    expect(exchange.status()).toBe(200);
    const body = await exchange.json();
    expect(typeof body.access_token).toBe('string');
    expect(body.access_token.length).toBeGreaterThan(0);

    const response = await request.get(PROTECTED_URL, {
      headers: { Authorization: `Bearer ${body.access_token}` },
    });
    expect(response.status()).toBe(200);
  });

  test('API token exchanged for another audience is not usable', async ({ request }) => {
    // Whether the mock refuses an unknown audience or issues a token for it
    // depends on its request mappings, which this test does not pin down.
    // Either outcome is acceptable as long as the result cannot reach the
    // sales API: the exchange fails, or Django rejects the token with 401.
    const userToken = await fetchUserToken(request);

    const exchange = await exchangeApiToken(request, userToken, OTHER_AUDIENCE);
    const rejectedAtExchange = exchange.status() !== 200;

    let djangoStatus: number | null = null;
    if (!rejectedAtExchange) {
      const body = await exchange.json();
      const response = await request.get(PROTECTED_URL, {
        headers: { Authorization: `Bearer ${body.access_token}` },
      });
      djangoStatus = response.status();
    }

    expect(
      rejectedAtExchange || djangoStatus === 401,
      `exchange status ${exchange.status()}, Django status ${djangoStatus}`,
    ).toBe(true);
  });
});
