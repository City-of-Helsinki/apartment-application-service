import type { APIRequestContext } from '@playwright/test';
import { test, expect } from '../utils';

// The mock OIDC provider sets each token's `iss` from the host used to reach
// it. Django only trusts the issuer configured in the compose network
// (http://mock-oidc:8080/e2e), so this suite is meant to run inside the
// compose network (test-runner container) with E2E_OIDC_URL pointing there.
// Run from the host, every token would carry a localhost issuer and be
// rejected with 401.

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';
const OIDC_BASE = process.env.E2E_OIDC_URL ?? 'http://localhost:18083';

const TRUSTED_ISSUER = 'e2e';
const UNTRUSTED_ISSUER = 'untrusted';
const PROTECTED_URL = `${DJANGO_BASE}/v1/sales/projects/`;

/**
 * Fetch an access token from the mock OIDC provider via client_credentials.
 *
 * @param request - Playwright API request context.
 * @param issuerId - Issuer id path segment on the mock provider (e.g. "e2e").
 * @param scope - Scope selecting the mock request mapping (token claims).
 * @returns The raw access token (JWT) string.
 */
async function fetchToken(
  request: APIRequestContext,
  issuerId: string,
  scope: string,
): Promise<string> {
  const response = await request.post(`${OIDC_BASE}/${issuerId}/token`, {
    form: {
      grant_type: 'client_credentials',
      client_id: 'e2e-client',
      client_secret: 'e2e-secret',
      scope,
    },
  });
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(typeof body.access_token).toBe('string');
  return body.access_token;
}

test.describe('Django sales API authenticates OIDC Bearer tokens', () => {
  test('mock OIDC discovery document is served for the trusted issuer', async ({ request }) => {
    const response = await request.get(
      `${OIDC_BASE}/${TRUSTED_ISSUER}/.well-known/openid-configuration`,
    );
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body.issuer).toMatch(new RegExp(`/${TRUSTED_ISSUER}$`));
    expect(typeof body.jwks_uri).toBe('string');
    expect(body.jwks_uri.length).toBeGreaterThan(0);
  });

  test('salesperson token is accepted with 200 and JSON body', async ({ request }) => {
    const token = await fetchToken(request, TRUSTED_ISSUER, 'e2e-salesperson');

    const response = await request.get(PROTECTED_URL, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toMatch(/application\/json/);
    const body = await response.json();
    expect(body).toBeDefined();
  });

  test('request without Authorization header is rejected with 401', async ({ request }) => {
    const response = await request.get(PROTECTED_URL);
    expect(response.status()).toBe(401);
  });

  test('malformed bearer token is rejected with 401', async ({ request }) => {
    const response = await request.get(PROTECTED_URL, {
      headers: { Authorization: 'Bearer not-a-jwt' },
    });
    expect(response.status()).toBe(401);
  });

  test('token with wrong audience is rejected with 401', async ({ request }) => {
    const token = await fetchToken(request, TRUSTED_ISSUER, 'e2e-wrong-audience');

    const response = await request.get(PROTECTED_URL, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(401);
  });

  test('token from untrusted issuer is rejected with 401', async ({ request }) => {
    const token = await fetchToken(request, UNTRUSTED_ISSUER, 'e2e-salesperson');

    const response = await request.get(PROTECTED_URL, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(401);
  });

  test('authenticated non-salesperson is forbidden with 403', async ({ request }) => {
    const token = await fetchToken(request, TRUSTED_ISSUER, 'e2e-customer');

    const response = await request.get(PROTECTED_URL, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(403);
  });
});
