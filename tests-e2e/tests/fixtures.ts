// Django rows loaded from e2e/fixtures/django/*.json by
// e2e/load_django_fixtures.py, which run-e2e.sh runs before every test run.
// Keep these constants in sync with the JSON files.

export interface FixtureCustomer {
  id: number;
  first_name: string;
  last_name: string;
}

export interface HasoQueueFixture {
  project_uuid: string;
  apartment_uuid: string;
  // Right of residence 500, non-late reservation at queue position 1.
  existing_customer: FixtureCustomer;
  // Right of residence 100, no reservation.
  new_customer: FixtureCustomer;
}

// Baseline project "haso" in e2e/fixtures/drupal/baseline.json.
const HASO_PROJECT_UUID = 'e2e00001-0000-4000-8000-000000000001';

// e2e/fixtures/django/haso_queue.json: one apartment per variant, so the
// variants can run in parallel.
export const HASO_QUEUE: Record<'on_time' | 'late', HasoQueueFixture> = {
  on_time: {
    project_uuid: HASO_PROJECT_UUID,
    apartment_uuid: 'e2e00001-0000-4000-8000-000000000101', // haso-a1
    existing_customer: { id: 900001, first_name: 'Existing', last_name: 'E2eHasoOntimeExisting' },
    new_customer: { id: 900002, first_name: 'Newcomer', last_name: 'E2eHasoOntimeNewcomer' },
  },
  late: {
    project_uuid: HASO_PROJECT_UUID,
    apartment_uuid: 'e2e00001-0000-4000-8000-000000000102', // haso-a2
    existing_customer: { id: 900003, first_name: 'Existing', last_name: 'E2eHasoLateExisting' },
    new_customer: { id: 900004, first_name: 'Newcomer', last_name: 'E2eHasoLateNewcomer' },
  },
};
