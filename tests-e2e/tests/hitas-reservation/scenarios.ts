import * as fs from 'fs';
import type { APIRequestContext, Page } from '@playwright/test';
import { expect } from '../utils';

// Shared data for the HITAS reservation (ASU-1880) specs. Projects and
// apartments come from e2e/fixtures/drupal/baseline.json; customers, their
// Drupal applications and their Django reservations from
// e2e/fixtures/drupal/customers.json (loaded by run-e2e.sh).

const FIXTURES_DIR = process.env.E2E_FIXTURES_DIR ?? '/e2e/fixtures/drupal';
// The Drupal search index, used only to map baseline UUIDs to node ids.
const ELASTIC_URL = process.env.E2E_ELASTIC_URL ?? 'http://drupal-elastic:9200';

export const CUSTOMER_PASSWORD = process.env.E2E_CUSTOMER_PASSWORD;

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

export interface CustomerScenario {
  key: string;
  email: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  national_identification_number: string;
  application: {
    backend_uuid: string;
    project: string;
    apartment: string;
    reservation_state: string;
  } | null;
}

/**
 * Read a JSON fixture file from the mounted fixtures directory.
 *
 * @param name - File name inside FIXTURES_DIR.
 * @returns The parsed content.
 */
function readFixture<T>(name: string): T {
  return JSON.parse(fs.readFileSync(`${FIXTURES_DIR}/${name}`, 'utf-8')) as T;
}

const baseline = readFixture<{ projects: BaselineProject[] }>('baseline.json');
const customers = readFixture<{ customers: CustomerScenario[] }>('customers.json');

/**
 * Return a baseline project by key.
 *
 * @param key - Project key in baseline.json.
 * @returns The project entry.
 */
export function baselineProject(key: string): BaselineProject {
  const project = baseline.projects.find((p) => p.key === key);
  if (!project) {
    throw new Error(`Baseline project "${key}" not found`);
  }
  return project;
}

/**
 * Return a baseline apartment by key.
 *
 * @param key - Apartment key in baseline.json.
 * @returns The apartment entry.
 */
export function baselineApartment(key: string): BaselineApartment {
  for (const project of baseline.projects) {
    const apartment = project.apartments.find((a) => a.key === key);
    if (apartment) {
      return apartment;
    }
  }
  throw new Error(`Baseline apartment "${key}" not found`);
}

/**
 * Return a customer scenario by key.
 *
 * @param key - Customer key in customers.json.
 * @returns The scenario entry.
 */
export function customerScenario(key: string): CustomerScenario {
  const customer = customers.customers.find((c) => c.key === key);
  if (!customer) {
    throw new Error(`Customer scenario "${key}" not found`);
  }
  return customer;
}

/**
 * Read an indexed apartment document whose field matches a UUID.
 *
 * Baseline UUIDs are node UUIDs, but tests navigate by node id; the
 * apartment index holds both the apartment's and its project's ids.
 *
 * @param request - Playwright API request context.
 * @param field - "uuid" (apartment) or "project_uuid".
 * @param uuid - Node UUID.
 * @returns The indexed document source.
 */
async function indexedApartment(
  request: APIRequestContext,
  field: 'uuid' | 'project_uuid',
  uuid: string,
): Promise<{ nid: number; project_id: number }> {
  const response = await request.post(`${ELASTIC_URL}/asuntotuotanto_apartment/_search`, {
    // UUID fields are analysed text in this index, so a term query misses.
    data: { size: 1, query: { match_phrase: { [field]: uuid } } },
  });
  expect(response.ok()).toBeTruthy();
  const source = (await response.json()).hits.hits[0]?._source;
  if (!source) {
    throw new Error(`No indexed apartment with ${field}=${uuid}`);
  }
  return source;
}

/**
 * Resolve the Drupal node id of a baseline apartment.
 *
 * @param request - Playwright API request context.
 * @param key - Apartment key in baseline.json.
 * @returns Apartment node id.
 */
export async function apartmentNid(request: APIRequestContext, key: string): Promise<number> {
  return Number((await indexedApartment(request, 'uuid', baselineApartment(key).uuid)).nid);
}

/**
 * Resolve the Drupal node id of a baseline project.
 *
 * @param request - Playwright API request context.
 * @param key - Project key in baseline.json.
 * @returns Project node id.
 */
export async function projectNid(request: APIRequestContext, key: string): Promise<number> {
  return Number((await indexedApartment(request, 'project_uuid', baselineProject(key).uuid)).project_id);
}

/**
 * Log a seeded customer in through the Drupal login form.
 *
 * @param page - Playwright page.
 * @param customer - Customer scenario to log in as.
 */
export async function loginAsCustomer(page: Page, customer: CustomerScenario): Promise<void> {
  if (!CUSTOMER_PASSWORD) {
    throw new Error('E2E_CUSTOMER_PASSWORD not set; run via run-e2e.sh');
  }
  await page.goto('/fi/user/login');
  await page.locator('input[name="name"]').fill(customer.email);
  await page.locator('input[type="password"]').fill(CUSTOMER_PASSWORD);
  await page.locator('input[type="submit"], button[type="submit"]').first().click();
  await page.waitForLoadState('domcontentloaded');
  await expect(page).not.toHaveURL(/\/user\/login/);
}
