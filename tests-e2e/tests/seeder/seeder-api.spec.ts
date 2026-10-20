import * as fs from 'fs';
import type { APIRequestContext } from '@playwright/test';
import { test, expect, NAMESPACE_PATTERN, SEEDER_URL } from '../utils';

// Exercises the seeder sidecar (e2e/seeder/server.py) over HTTP and checks
// the haso_queue scenario's effect through Django's sales API.
//
// The haso_queue tests here seed baseline apartment haso-a3 via the
// apartment_key param. haso-a1 and haso-a2 are the default apartments of
// the on_time/late variants used by sales-ui/haso-reservation-queue.spec.ts;
// seeding them here would reset that spec's data mid-test when the files run
// in parallel workers.
//
// Like django-oidc.spec.ts, this suite must run inside the compose network
// (test-runner container) so mock OIDC tokens carry the issuer Django trusts.

const DJANGO_BASE = process.env.E2E_DJANGO_URL ?? 'http://localhost:18081';
const OIDC_BASE = process.env.E2E_OIDC_URL ?? 'http://localhost:18083';
const BASELINE_FILE = process.env.E2E_BASELINE_FILE ?? '/e2e/fixtures/baseline.json';

const TRUSTED_ISSUER = 'e2e';
const SALESPERSON_SCOPE = 'e2e-salesperson';

const SCENARIO = 'haso_queue';
const SPARE_APARTMENT_KEY = 'haso-a3';

interface BaselineApartment {
  key: string;
  uuid: string;
  apartment_number: string;
}

interface BaselineProject {
  key: string;
  uuid: string;
  apartments: BaselineApartment[];
}

interface Baseline {
  projects: BaselineProject[];
}

interface SeededCustomer {
  id: number;
  first_name: string;
  last_name: string;
}

// Manifest returned by the seeder's haso_queue scenario.
interface HasoQueueManifest {
  scenario: string;
  variant: string;
  namespace: string;
  project_uuid: string;
  apartment_uuid: string;
  apartment_number: string;
  existing_customer: SeededCustomer;
  new_customer: SeededCustomer;
}

// Subset of SalesApartmentReservationSerializer used here.
interface SalesReservation {
  id: number;
  queue_position: number | null;
  submitted_late: boolean;
  customer: {
    id: number;
    primary_profile: { first_name: string; last_name: string } | null;
  };
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
 * Find a baseline apartment and its project by apartment key.
 *
 * @param baseline - Parsed baseline content.
 * @param key - Apartment key, e.g. "haso-a3".
 * @returns The apartment and the project it belongs to.
 * @throws Error when no apartment has the key.
 */
function findApartment(
  baseline: Baseline,
  key: string,
): { project: BaselineProject; apartment: BaselineApartment } {
  for (const project of baseline.projects) {
    const apartment = project.apartments.find((candidate) => candidate.key === key);
    if (apartment) {
      return { project, apartment };
    }
  }
  throw new Error(`Baseline has no apartment with key "${key}".`);
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

/**
 * List an apartment's reservations through Django's sales API.
 *
 * @param request - Playwright API request context.
 * @param apartmentUuid - Apartment whose reservations are listed.
 * @returns The reservations in list order.
 */
async function fetchReservations(
  request: APIRequestContext,
  apartmentUuid: string,
): Promise<SalesReservation[]> {
  const token = await fetchToken(request, TRUSTED_ISSUER, SALESPERSON_SCOPE);
  const response = await request.get(
    `${DJANGO_BASE}/v1/sales/apartments/${apartmentUuid}/reservations/`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(Array.isArray(body)).toBe(true);
  return body as SalesReservation[];
}

/**
 * Assert a seeder response is a JSON error with the given status.
 *
 * @param response - Seeder response.
 * @param status - Expected HTTP status.
 */
async function expectError(
  response: Awaited<ReturnType<APIRequestContext['post']>>,
  status: number,
): Promise<void> {
  expect(response.status()).toBe(status);
  const body = await response.json();
  expect(typeof body.error).toBe('string');
  expect(body.error.length).toBeGreaterThan(0);
}

const baseline = loadBaseline(BASELINE_FILE);

test.describe('Seeder sidecar HTTP API', () => {
  test('GET /health returns ok and lists haso_queue', async ({ request }) => {
    const response = await request.get(`${SEEDER_URL}/health`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body.status).toBe('ok');
    expect(Array.isArray(body.scenarios)).toBe(true);
    expect(body.scenarios).toContain(SCENARIO);
  });

  test('POST to an unknown scenario returns 404', async ({ request }) => {
    const response = await request.post(`${SEEDER_URL}/scenarios/does_not_exist`, {
      data: { namespace: 'seeder-unknown' },
    });
    await expectError(response, 404);
  });

  test('POST haso_queue with an unknown variant returns 400', async ({ request }) => {
    const response = await request.post(`${SEEDER_URL}/scenarios/${SCENARIO}`, {
      data: { variant: 'bogus', namespace: 'seeder-bad-variant' },
    });
    await expectError(response, 400);
  });

  test('POST haso_queue with an invalid namespace returns 400', async ({ request }) => {
    const response = await request.post(`${SEEDER_URL}/scenarios/${SCENARIO}`, {
      data: { variant: 'on_time', namespace: 'Not Valid!' },
    });
    await expectError(response, 400);
  });

  test('POST haso_queue with a non-HASO apartment_key returns 400', async ({ request }) => {
    const response = await request.post(`${SEEDER_URL}/scenarios/${SCENARIO}`, {
      data: { variant: 'on_time', namespace: 'seeder-bad-key', apartment_key: 'hitas-b1' },
    });
    await expectError(response, 400);
  });

  test('POST with a body that is not JSON returns 400', async ({ request }) => {
    const response = await request.post(`${SEEDER_URL}/scenarios/${SCENARIO}`, {
      headers: { 'Content-Type': 'application/json' },
      data: 'not json',
    });
    await expectError(response, 400);
  });

  test('GET on a scenario path returns 405', async ({ request }) => {
    const response = await request.get(`${SEEDER_URL}/scenarios/${SCENARIO}`);
    await expectError(response, 405);
  });

  test('unknown path returns 404', async ({ request }) => {
    const response = await request.get(`${SEEDER_URL}/does-not-exist`);
    await expectError(response, 404);
  });

  test('seedScenario fixture throws with status and body on failure', async ({
    seedScenario,
  }) => {
    await expect(seedScenario('does_not_exist')).rejects.toThrow(/404/);
    await expect(
      seedScenario(SCENARIO, { variant: 'bogus', apartment_key: SPARE_APARTMENT_KEY }),
    ).rejects.toThrow(/400[\s\S]*error/);
  });
});

test.describe('Seeder haso_queue scenario', () => {
  // Every test here resets the same spare apartment, so they must not
  // interleave with each other.
  test.describe.configure({ mode: 'serial' });

  const { project, apartment } = findApartment(baseline, SPARE_APARTMENT_KEY);

  test('manifest points at the requested baseline apartment', async ({ seedScenario }) => {
    const manifest = await seedScenario<HasoQueueManifest>(SCENARIO, {
      variant: 'on_time',
      apartment_key: SPARE_APARTMENT_KEY,
    });

    expect(manifest.scenario).toBe(SCENARIO);
    expect(manifest.variant).toBe('on_time');
    expect(manifest.namespace).toMatch(NAMESPACE_PATTERN);
    expect(manifest.apartment_uuid).toBe(apartment.uuid);
    expect(manifest.apartment_number).toBe(apartment.apartment_number);
    expect(manifest.project_uuid).toBe(project.uuid);
    expect(manifest.existing_customer.id).not.toBe(manifest.new_customer.id);
    expect(manifest.existing_customer.last_name).not.toBe(manifest.new_customer.last_name);
  });

  test('explicit namespace is used instead of the derived one', async ({ seedScenario }) => {
    const manifest = await seedScenario<HasoQueueManifest>(SCENARIO, {
      variant: 'on_time',
      apartment_key: SPARE_APARTMENT_KEY,
      namespace: 'seeder-explicit',
    });

    expect(manifest.namespace).toBe('seeder-explicit');
    expect(manifest.existing_customer.last_name.toLowerCase()).toContain('seeder-explicit');
  });

  test('re-seeding leaves exactly one reservation, owned by the newest existing customer', async ({
    request,
    seedScenario,
  }) => {
    const params = { variant: 'on_time', apartment_key: SPARE_APARTMENT_KEY };
    const first = await seedScenario<HasoQueueManifest>(SCENARIO, params);
    expect(first.apartment_uuid).toBe(apartment.uuid);

    const afterFirst = await fetchReservations(request, apartment.uuid);
    expect(afterFirst).toHaveLength(1);
    expect(afterFirst[0].customer.id).toBe(first.existing_customer.id);

    const second = await seedScenario<HasoQueueManifest>(SCENARIO, params);
    expect(second.apartment_uuid).toBe(apartment.uuid);

    const reservations = await fetchReservations(request, apartment.uuid);
    expect(reservations).toHaveLength(1);
    const [reservation] = reservations;
    expect(reservation.customer.id).toBe(second.existing_customer.id);
    expect(reservation.customer.primary_profile?.last_name).toBe(
      second.existing_customer.last_name,
    );
    expect(reservation.queue_position).toBe(1);
    expect(reservation.submitted_late).toBe(false);
  });
});
