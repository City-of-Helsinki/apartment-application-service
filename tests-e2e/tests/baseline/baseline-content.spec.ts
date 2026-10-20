import * as fs from 'fs';
import type { APIRequestContext } from '@playwright/test';
import { test, expect } from '../utils';

// Verifies that the committed baseline content (e2e/fixtures/baseline.json),
// loaded into Drupal by the drush loader, is served by Django's sales API with
// the fixed node UUIDs. The loader runs on every drupal-app start, so this
// also guards idempotency: a non-idempotent loader would create duplicate
// apartments and the exact-set/length assertions below would fail.
//
// Like django-oidc.spec.ts, this suite must run inside the compose network
// (test-runner container) so mock OIDC tokens carry the issuer Django trusts.

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';
const OIDC_BASE = process.env.E2E_OIDC_URL ?? 'http://localhost:18083';
const BASELINE_FILE = process.env.E2E_BASELINE_FILE ?? '/e2e/fixtures/baseline.json';

const TRUSTED_ISSUER = 'e2e';
const SALESPERSON_SCOPE = 'e2e-salesperson';

interface BaselineApartment {
  key: string;
  uuid: string;
  apartment_number: string;
}

interface BaselineProject {
  key: string;
  uuid: string;
  ownership_type: string;
  housing_company: string;
  apartments: BaselineApartment[];
}

interface Baseline {
  projects: BaselineProject[];
}

/**
 * Read and parse the baseline fixture file.
 *
 * @param path - Filesystem path to baseline.json.
 * @returns The parsed baseline content.
 * @throws Error with a descriptive message when the file is missing or invalid.
 */
function loadBaseline(path: string): Baseline {
  if (!fs.existsSync(path)) {
    throw new Error(
      `Baseline fixture not found at ${path}. Mount e2e/fixtures into the ` +
        'test-runner or set E2E_BASELINE_FILE to the baseline.json path.',
    );
  }
  const data = JSON.parse(fs.readFileSync(path, 'utf-8')) as Baseline;
  if (!Array.isArray(data.projects) || data.projects.length === 0) {
    throw new Error(`Baseline fixture at ${path} has no projects.`);
  }
  return data;
}

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

const baseline = loadBaseline(BASELINE_FILE);

for (const project of baseline.projects) {
  test.describe(`Baseline project "${project.key}" is served by the sales API`, () => {
    test('project detail matches uuid, housing company and ownership type', async ({
      request,
    }) => {
      const token = await fetchToken(request, TRUSTED_ISSUER, SALESPERSON_SCOPE);

      const response = await request.get(`${DJANGO_BASE}/v1/sales/projects/${project.uuid}/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(response.status()).toBe(200);

      const body = await response.json();
      expect(body.uuid).toBe(project.uuid);
      expect(body.housing_company).toBe(project.housing_company);
      expect(String(body.ownership_type).toLowerCase()).toBe(
        project.ownership_type.toLowerCase(),
      );
    });

    test('apartment list contains exactly the baseline apartments', async ({ request }) => {
      const token = await fetchToken(request, TRUSTED_ISSUER, SALESPERSON_SCOPE);

      const response = await request.get(`${DJANGO_BASE}/v1/sales/apartments/`, {
        params: { project_uuid: project.uuid },
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(response.status()).toBe(200);

      const body: Array<{ uuid: string; apartment_number: string }> = await response.json();
      expect(Array.isArray(body)).toBe(true);
      expect(body).toHaveLength(project.apartments.length);

      const actualUuids = new Set(body.map((apartment) => apartment.uuid));
      const expectedUuids = new Set(project.apartments.map((apartment) => apartment.uuid));
      expect(actualUuids).toEqual(expectedUuids);

      const actualNumbers = Object.fromEntries(
        body.map((apartment) => [apartment.uuid, apartment.apartment_number]),
      );
      const expectedNumbers = Object.fromEntries(
        project.apartments.map((apartment) => [apartment.uuid, apartment.apartment_number]),
      );
      expect(actualNumbers).toEqual(expectedNumbers);
    });
  });
}
