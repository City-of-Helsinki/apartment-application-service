import type { Page } from '@playwright/test';
import { test, expect } from '../utils';
import {
  CUSTOMER_PASSWORD,
  apartmentNid,
  customerScenario,
  loginAsCustomer,
  projectNid,
} from './scenarios';

// ASU-1880 regressions found in acceptance testing of HITAS reservations made
// after the application period (project "hitas_late": period ended,
// can_apply_afterwards on; C1/C2 free for reservations, C3 reserved).
//
// Finnish UI texts:
// - "Tee varaus": reservation CTA, same as the search UI's
//   SEARCH:make-reservation in asuntomyynti-react.
// - "Luo jälkihakemus": "Create an after-application", HASO only.
// - "Jatka": "Continue" button of the replace-application dialog.
const MAKE_RESERVATION_TEXT = 'Tee varaus';
const AFTER_APPLICATION_TEXT = 'Luo jälkihakemus';
const CONTINUE_TEXT = 'Jatka';
const CONFIRM_ERROR_TEXT = 'Please confirm action';

const CONTACT_FORM_PATH = '/contact/apply_for_free_apartment';
const CONFIRM_DIALOG = '#asu-application-delete-confirm-dialog';

/**
 * Locate the CTA links in the apartment page header.
 *
 * @param page - Playwright page on an apartment page.
 * @returns Locator for the header action links.
 */
function apartmentHeaderActions(page: Page) {
  return page.locator('.apartment__header-section--actions a');
}

test.describe('ASU-1880: apartment page CTA after the HITAS application period', () => {
  test('a free apartment offers a reservation, not an after-application', async ({ page, request }) => {
    const project = await projectNid(request, 'hitas_late');
    const apartment = await apartmentNid(request, 'hitas-late-c1');

    await page.goto(`/fi/node/${apartment}`);

    const cta = apartmentHeaderActions(page);
    await expect(cta).toHaveCount(1);
    // Must open the reservation form with the apartment preselected, not the
    // contact form.
    const href = (await cta.getAttribute('href')) ?? '';
    expect(href).not.toContain(CONTACT_FORM_PATH);
    expect(href).toContain(`/application/add/hitas/${project}`);
    expect(href).toContain(`apartment=${apartment}`);
    // Same label as the search UI; "after-application" is HASO wording.
    await expect(cta).toHaveText(MAKE_RESERVATION_TEXT);
  });

  test('a reserved apartment offers no after-application leading to the contact form', async ({ page, request }) => {
    const apartment = await apartmentNid(request, 'hitas-late-c3');

    await page.goto(`/fi/node/${apartment}`);

    // The search UI shows no reservation CTA for a reserved apartment.
    await expect(apartmentHeaderActions(page).filter({ hasText: AFTER_APPLICATION_TEXT })).toHaveCount(0);
    await expect(apartmentHeaderActions(page).filter({ hasText: MAKE_RESERVATION_TEXT })).toHaveCount(0);
  });
});

test.describe('ASU-1880: a canceled reservation does not block a new one', () => {
  test.skip(!CUSTOMER_PASSWORD, 'E2E_CUSTOMER_PASSWORD not set — run via run-e2e.sh');

  // Customer whose only reservation in the project (C1, from an application
  // already sent to Django) is canceled: the offer was rejected.
  const customer = customerScenario('hitas_late_canceled');

  test('the search UI is not told that the customer has an application in the project', async ({ page, request }) => {
    const project = await projectNid(request, 'hitas_late');
    await loginAsCustomer(page, customer);

    // The search UI renders "Sinulla on hakemus tähän kohteeseen" for every
    // project listed in user.applications.
    const response = await page.request.get('/fi/initialize');
    expect(response.status()).toBe(200);
    const config = await response.json();
    expect(Object.keys(config.user.applications ?? {})).not.toContain(String(project));
  });

  test('the reservation CTA opens a new reservation, not the canceled application', async ({ page, request }) => {
    const project = await projectNid(request, 'hitas_late');
    const apartment = await apartmentNid(request, 'hitas-late-c2');
    await loginAsCustomer(page, customer);

    await page.goto(`/fi/application/add/hitas/${project}?apartment=${apartment}`);

    const submit = page.locator('[name="submit-application"]');
    await expect(submit).toBeVisible();
    // A form for an application already sent to Django carries this field and
    // forces the "replace your application" confirmation.
    await expect(page.locator('input[name="confirm_application_deletion"]')).toHaveCount(0);
    await expect(page.locator('select[name="apartment[0][id]"]')).toHaveValue(String(apartment));
  });

  test('the reservation form is in Finnish', async ({ page, request }) => {
    const project = await projectNid(request, 'hitas_late');
    const apartment = await apartmentNid(request, 'hitas-late-c2');
    await loginAsCustomer(page, customerScenario('hitas_late_fresh'));

    await page.goto(`/fi/application/add/hitas/${project}?apartment=${apartment}`);

    await expect(page.locator('[name="submit-application"]')).toHaveValue(MAKE_RESERVATION_TEXT);
  });
});

test.describe('ASU-1880: resubmitting an application already sent to Django', () => {
  test.skip(!CUSTOMER_PASSWORD, 'E2E_CUSTOMER_PASSWORD not set — run via run-e2e.sh');

  // Customer with a submitted application (D1) in a project whose
  // application period is ongoing; resending replaces that application.
  const customer = customerScenario('hitas_open_submitted');

  test('asks for confirmation instead of failing with "Please confirm action"', async ({ page, request }) => {
    const project = await projectNid(request, 'hitas_open');
    const apartment = await apartmentNid(request, 'hitas-open-d1');
    await loginAsCustomer(page, customer);

    // Redirects to the edit form of the existing application.
    await page.goto(`/fi/application/add/hitas/${project}`);
    await expect(page).toHaveURL(/\/application\/\d+\/edit/);
    await expect(page.locator('input[name="confirm_application_deletion"]')).toHaveCount(1);

    // The apartment list UI is built client side over a hidden select.
    await page
      .locator('select[name="apartment[0][id]"]')
      .selectOption(String(apartment), { force: true, timeout: 5_000 });
    await page.locator('input[name="main_applicant[0][personal_id]"]').fill(
      customer.national_identification_number.slice(-4),
    );
    await page.locator('input[name="main_applicant[0][address]"]').fill('E2E-katu 1');
    await page.locator('input[name="main_applicant[0][postal_code]"]').fill('00100');
    await page.locator('input[name="main_applicant[0][city]"]').fill('Helsinki');
    await page.locator('input[name="main_applicant[0][phone]"]').fill('0400000000');
    await page.locator('input[name="field_agreement_policy[value]"]').check({ force: true });
    await page.locator('input[name="field_data_agreement_policy[value]"]').check({ force: true });

    await page.locator('[name="submit-application"]').click();

    // The replace-application dialog must open before anything is posted.
    const dialog = page.locator(`.ui-dialog:has(${CONFIRM_DIALOG})`);
    await expect(dialog).toBeVisible();
    await expect(page.getByText(CONFIRM_ERROR_TEXT)).toHaveCount(0);

    await dialog.getByRole('button', { name: CONTINUE_TEXT }).click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText(CONFIRM_ERROR_TEXT)).toHaveCount(0);
    await expect(page).not.toHaveURL(/\/edit/);
  });
});
