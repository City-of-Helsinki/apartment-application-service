import * as fs from 'fs';
import * as path from 'path';
import type { Locator, Page } from '@playwright/test';
import { test, expect } from '../utils';
import {
  FIRST_LOAD_TIMEOUT_MS,
  LOGIN_FLOW_TIMEOUT_MS,
  SALESPERSON_UUID,
  loginToSalesUi,
  salesUiUrl,
} from './salesUi';

// Reproduces the bug fixed in d53002c: after the lottery, adding a non-late
// (submitted_late unchecked) HASO reservation without a queue position put
// the customer at the end of the queue instead of ranking them by right of
// residence among the non-late reservations. The on_time scenario fails
// before that fix; the late scenario guards the late pool still ranking
// after every non-late reservation.
//
// Each scenario runs on its own apartment seeded by
// django_e2e_seed_haso_queue.py (run-e2e.sh runs it and writes its JSON
// output to the seed file), so the tests are independent of each other:
// - existing customer: right of residence 500, non-late, queue position 1
// - new customer: right of residence 100, no reservation yet

// Finnish UI texts from att-sales-ui src/i18n/fi.json.
const ADD_APPLICANT_BUTTON_TEXT = 'Lisää hakija'; // ApartmentRow.btnAddApplicant
const ADD_BUTTON_TEXT = 'Lisää'; // ReservationAddModal.addBtn
const CONFIRM_BUTTON_TEXT = 'Vahvista muutokset'; // ReservationAddModal.confirm
const PREVIEW_TITLE_TEXT = 'Jonon esikatselu'; // ReservationAddModal.previewTitle

const CREATE_RESERVATION_API_PATH = '/v1/sales/apartment_reservations/';

const SEED_FILE =
  process.env.E2E_HASO_SEED_FILE ??
  path.join(__dirname, '..', '..', '.e2e-seed', 'haso-queue.json');

type ScenarioName = 'on_time' | 'late';

interface SeededCustomer {
  id: number;
  first_name: string;
  last_name: string;
}

interface ScenarioSeed {
  scenario: ScenarioName;
  project_uuid: string;
  apartment_uuid: string;
  apartment_number: string;
  existing_customer: SeededCustomer;
  new_customer: SeededCustomer;
}

type HasoQueueSeed = Record<ScenarioName, ScenarioSeed>;

interface ScenarioExpectation {
  name: ScenarioName;
  submittedLate: boolean;
  // Queue position the new customer is expected to receive.
  newQueuePosition: number;
}

const SCENARIOS: ScenarioExpectation[] = [
  // Better right of residence ranks ahead of the existing non-late customer.
  { name: 'on_time', submittedLate: false, newQueuePosition: 1 },
  // The late pool ranks after every non-late reservation regardless of RoR.
  { name: 'late', submittedLate: true, newQueuePosition: 2 },
];

/**
 * Read the HASO queue seed written by django_e2e_seed_haso_queue.py.
 *
 * @param scenario - Scenario whose seed data is returned.
 * @returns The seeded project, apartment and customers of the scenario.
 * @throws Error with instructions to run the seed when the file is missing
 *   or does not contain the scenario.
 */
function loadScenarioSeed(scenario: ScenarioName): ScenarioSeed {
  if (!fs.existsSync(SEED_FILE)) {
    throw new Error(
      `HASO queue seed file not found at ${SEED_FILE}. Run the seed first ` +
        '(run-e2e.sh runs django_e2e_seed_haso_queue.py and writes its JSON ' +
        'output there), or point E2E_HASO_SEED_FILE at the seed output.',
    );
  }
  const seed = JSON.parse(fs.readFileSync(SEED_FILE, 'utf-8')) as Partial<HasoQueueSeed>;
  const scenarioSeed = seed[scenario];
  if (!scenarioSeed) {
    throw new Error(
      `HASO queue seed file ${SEED_FILE} has no "${scenario}" scenario. ` +
        'Re-run django_e2e_seed_haso_queue.py (run-e2e.sh does it).',
    );
  }
  return scenarioSeed;
}

/**
 * Escape a string for literal use inside a RegExp.
 *
 * @param value - Raw text.
 * @returns The text with RegExp metacharacters escaped.
 */
function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Locate the toggle button of an apartment row.
 *
 * @param page - Playwright page.
 * @param apartmentUuid - Apartment whose row is targeted.
 * @returns Locator for the row's expand/collapse button.
 */
function apartmentRowToggle(page: Page, apartmentUuid: string): Locator {
  return page.locator(`button[aria-controls="apartment-row-${apartmentUuid}"]`);
}

/**
 * Locate the expandable content of an apartment row.
 *
 * @param page - Playwright page.
 * @param apartmentUuid - Apartment whose row is targeted.
 * @returns Locator for the row's reservation list container.
 */
function apartmentRowContent(page: Page, apartmentUuid: string): Locator {
  return page.locator(`[id="apartment-row-${apartmentUuid}"]`);
}

/**
 * Expand an apartment row unless it is already expanded.
 *
 * The reservations are fetched only when the row is opened, so this waits
 * until the toggle reports the row as expanded (fetch finished).
 *
 * @param page - Playwright page.
 * @param apartmentUuid - Apartment whose row is expanded.
 * @returns The row's content locator.
 */
async function openApartmentRow(page: Page, apartmentUuid: string): Promise<Locator> {
  const toggle = apartmentRowToggle(page, apartmentUuid);
  await expect(toggle).toBeEnabled({ timeout: FIRST_LOAD_TIMEOUT_MS });
  if ((await toggle.getAttribute('aria-expanded')) !== 'true') {
    await toggle.click();
  }
  await expect(toggle).toHaveAttribute('aria-expanded', 'true', {
    timeout: LOGIN_FLOW_TIMEOUT_MS,
  });
  return apartmentRowContent(page, apartmentUuid);
}

/**
 * Locate the reservation add dialog of an apartment.
 *
 * @param page - Playwright page.
 * @param apartmentUuid - Apartment the dialog adds a reservation to.
 * @returns Locator for the dialog.
 */
function reservationAddDialog(page: Page, apartmentUuid: string): Locator {
  return page.locator(`[id="reservation-add-dialog-${apartmentUuid}"]`);
}

/**
 * Search for a customer by last name and pick them in the dialog.
 *
 * The option is matched by its trailing "ID: <id>" so a namesake from other
 * data cannot be picked instead.
 *
 * @param dialog - Reservation add dialog.
 * @param customer - Seeded customer to pick.
 */
async function selectCustomer(dialog: Locator, customer: SeededCustomer): Promise<void> {
  await dialog.locator('#searchCustomer').fill(customer.last_name);
  const option = dialog.getByRole('option', {
    name: new RegExp(`${escapeRegExp(customer.last_name)}.*ID: ${customer.id}$`),
  });
  await expect(option).toBeVisible({ timeout: LOGIN_FLOW_TIMEOUT_MS });
  await option.click();
}

/**
 * Locate the queue preview rows shown after pressing "add".
 *
 * Rows are the sibling divs rendered after the preview title, each as
 * "<queue_position>. <last_name> <first_name>".
 *
 * @param dialog - Reservation add dialog.
 * @returns Locator matching every preview row in queue order.
 */
function previewRows(dialog: Locator): Locator {
  return dialog
    .getByText(PREVIEW_TITLE_TEXT, { exact: true })
    .locator('xpath=..')
    .locator(':scope > div');
}

/**
 * Build a RegExp matching a preview row for a queue position and customer.
 *
 * @param position - Expected queue position.
 * @param customer - Expected customer.
 * @returns RegExp matching "<position>. <last_name> <first_name>".
 */
function previewRowPattern(position: number, customer: SeededCustomer): RegExp {
  return new RegExp(
    `^\\s*${position}\\.\\s+${escapeRegExp(customer.last_name)}\\s+` +
      `${escapeRegExp(customer.first_name)}\\s*$`,
  );
}

test.describe('Sales UI HASO reservation queue ordering', () => {
  test.beforeEach(async ({}, testInfo) => {
    testInfo.setTimeout(2 * FIRST_LOAD_TIMEOUT_MS + 6 * LOGIN_FLOW_TIMEOUT_MS);
  });

  for (const expectation of SCENARIOS) {
    test(`${expectation.name}: new customer with better RoR gets queue position ${expectation.newQueuePosition}`, async ({
      page,
    }) => {
      const seed = loadScenarioSeed(expectation.name);
      const newCustomer = seed.new_customer;
      const existingCustomer = seed.existing_customer;
      const [firstInQueue, secondInQueue] =
        expectation.newQueuePosition === 1
          ? [newCustomer, existingCustomer]
          : [existingCustomer, newCustomer];

      const projectsResponse = await loginToSalesUi(page, SALESPERSON_UUID);
      expect(projectsResponse.status()).toBe(200);

      await page.goto(salesUiUrl(`/projects/${seed.project_uuid}`), {
        timeout: FIRST_LOAD_TIMEOUT_MS,
      });

      const rowContent = await openApartmentRow(page, seed.apartment_uuid);
      await expect(rowContent).toContainText(existingCustomer.last_name, {
        timeout: LOGIN_FLOW_TIMEOUT_MS,
      });
      await rowContent.getByRole('button', { name: ADD_APPLICANT_BUTTON_TEXT }).click();

      const dialog = reservationAddDialog(page, seed.apartment_uuid);
      await expect(dialog).toBeVisible({ timeout: LOGIN_FLOW_TIMEOUT_MS });

      await selectCustomer(dialog, newCustomer);

      const queuePositionInput = dialog.locator('#queuePosition');
      if (expectation.submittedLate) {
        await dialog.locator('#submittedLate').check();
        await expect(dialog.locator('#submittedLate')).toBeChecked();
        // The queue position field is hidden for late reservations.
        await expect(queuePositionInput).toBeHidden();
      } else {
        await expect(dialog.locator('#submittedLate')).not.toBeChecked();
        // HASO leaves the queue position empty so RoR decides the order.
        await expect(queuePositionInput).toHaveValue('');
      }

      await dialog.getByRole('button', { name: ADD_BUTTON_TEXT, exact: true }).click();

      // The preview endpoint returns reservations in list order, not queue
      // order, so rows are matched by their rendered queue number.
      const rows = previewRows(dialog);
      await expect(rows).toHaveCount(2, { timeout: LOGIN_FLOW_TIMEOUT_MS });
      await expect(rows.filter({ hasText: previewRowPattern(1, firstInQueue) })).toHaveCount(1);
      await expect(rows.filter({ hasText: previewRowPattern(2, secondInQueue) })).toHaveCount(1);

      const createResponsePromise = page.waitForResponse(
        (response) =>
          response.url().includes(CREATE_RESERVATION_API_PATH) &&
          response.request().method() === 'POST',
        { timeout: LOGIN_FLOW_TIMEOUT_MS },
      );
      await dialog.getByRole('button', { name: CONFIRM_BUTTON_TEXT }).click();
      const createResponse = await createResponsePromise;

      expect(createResponse.status()).toBe(201);
      const created = await createResponse.json();
      expect(created.queue_position).toBe(expectation.newQueuePosition);
      expect(created.submitted_late).toBe(expectation.submittedLate);

      await expect(dialog).toBeHidden({ timeout: LOGIN_FLOW_TIMEOUT_MS });

      // The create mutation invalidates the row's reservations, so the list
      // is refetched; poll until both customers are listed in queue order.
      const content = await openApartmentRow(page, seed.apartment_uuid);
      await expect
        .poll(
          async () => {
            const text = await content.innerText();
            const newIndex = text.indexOf(newCustomer.last_name);
            const existingIndex = text.indexOf(existingCustomer.last_name);
            if (newIndex < 0 || existingIndex < 0) {
              return null;
            }
            return newIndex < existingIndex
              ? [newCustomer.last_name, existingCustomer.last_name]
              : [existingCustomer.last_name, newCustomer.last_name];
          },
          { timeout: LOGIN_FLOW_TIMEOUT_MS },
        )
        .toEqual([firstInQueue.last_name, secondInQueue.last_name]);
    });
  }
});
