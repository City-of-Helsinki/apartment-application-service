<?php

/**
 * @file
 * Creates the e2e customer scenarios (customers.json) in Drupal.
 *
 * Run with: drush php:script /e2e/fixtures/drupal/load_customers.php
 *
 * For each customer this script:
 * - creates or updates the Drupal customer user (login name and email are
 *   the scenario email, password is E2E_CUSTOMER_PASSWORD);
 * - makes sure the user has a Django profile, creating one through the
 *   backend API when the stored profile id is missing or unknown to Django;
 * - deletes the user's Drupal applications and recreates the scenario
 *   application, if any, as an already sent (locked) application whose
 *   field_backend_id is the scenario backend_uuid.
 *
 * Must run after load_baseline.php (projects/apartments are looked up by
 * their baseline UUIDs) and while django-app is reachable. The matching
 * Django application and reservation are created afterwards by
 * e2e/seed_customer_scenarios.py, which finds the profile by email.
 *
 * Any failure throws, which makes drush exit non-zero.
 */

use Drupal\asu_api\Api\BackendApi\Request\CreateUserRequest;
use Drupal\asu_api\Api\BackendApi\Request\UserRequest;
use Drupal\node\NodeInterface;
use Drupal\user\Entity\User;
use Drupal\user\UserInterface;

const E2E_CUSTOMERS_DEFAULT_FILE = '/e2e/fixtures/drupal/customers.json';
const E2E_CUSTOMERS_BASELINE_DEFAULT_FILE = '/e2e/fixtures/drupal/baseline.json';

/**
 * Read and decode a JSON fixture file.
 *
 * @param string $path
 *   Filesystem path.
 *
 * @return array
 *   Decoded content.
 */
function e2e_customers_read_json(string $path): array {
  if (!is_file($path) || !is_readable($path)) {
    throw new \RuntimeException("Fixture file not readable: {$path}");
  }
  return json_decode(file_get_contents($path), TRUE, 512, JSON_THROW_ON_ERROR);
}

/**
 * Map baseline project and apartment keys to their UUIDs.
 *
 * @param array $baseline
 *   Decoded baseline.json.
 *
 * @return array
 *   ['projects' => [key => uuid], 'apartments' => [key => uuid]].
 */
function e2e_customers_baseline_uuids(array $baseline): array {
  $uuids = ['projects' => [], 'apartments' => []];
  foreach ($baseline['projects'] as $project) {
    $uuids['projects'][$project['key']] = $project['uuid'];
    foreach ($project['apartments'] as $apartment) {
      $uuids['apartments'][$apartment['key']] = $apartment['uuid'];
    }
  }
  return $uuids;
}

/**
 * Load a node by UUID or fail.
 *
 * @param string $uuid
 *   Node UUID.
 *
 * @return \Drupal\node\NodeInterface
 *   The node.
 */
function e2e_customers_node(string $uuid): NodeInterface {
  $node = \Drupal::service('entity.repository')->loadEntityByUuid('node', $uuid);
  if (!$node instanceof NodeInterface) {
    throw new \RuntimeException("Baseline node {$uuid} not found; run load_baseline.php first");
  }
  return $node;
}

/**
 * Create or update the Drupal customer user.
 *
 * @param array $customer
 *   Customer scenario entry.
 * @param string $password
 *   Login password.
 *
 * @return \Drupal\user\UserInterface
 *   The saved user.
 */
function e2e_customers_upsert_user(array $customer, string $password): UserInterface {
  $users = \Drupal::entityTypeManager()->getStorage('user')
    ->loadByProperties(['mail' => $customer['email']]);
  $user = $users ? reset($users) : User::create([
    'type' => 'customer',
    'name' => $customer['email'],
    'mail' => $customer['email'],
    'langcode' => 'fi',
    'preferred_langcode' => 'fi',
  ]);
  $user->activate();
  $user->addRole('customer');
  $user->setPassword($password);
  $user->save();
  return $user;
}

/**
 * Make sure the user has a Django profile that Django knows about.
 *
 * @param \Drupal\user\UserInterface $user
 *   Customer user.
 * @param array $customer
 *   Customer scenario entry.
 *
 * @return string
 *   Django profile id.
 */
function e2e_customers_ensure_profile(UserInterface $user, array $customer): string {
  /** @var \Drupal\asu_api\Api\BackendApi\BackendApi $backendApi */
  $backendApi = \Drupal::service('asu_api.backendapi');

  if ($user->get('field_backend_profile')->value) {
    try {
      $request = new UserRequest($user);
      $request->setSender($user);
      $backendApi->send($request);
      return $user->get('field_backend_profile')->value;
    }
    catch (\Throwable $e) {
      // The Django database was reset; create a new profile below.
    }
  }

  // Same date format as the SAML login flow (AuthService).
  $dateOfBirth = \DateTime::createFromFormat('Y-m-d', $customer['date_of_birth'])->format('d.m.Y');
  $request = new CreateUserRequest($user, [
    'first_name' => $customer['first_name'],
    'last_name' => $customer['last_name'],
    'date_of_birth' => $dateOfBirth,
    'national_identification_number' => $customer['national_identification_number'],
  ], 'customer');
  $request->setSender($user);
  /** @var \Drupal\asu_api\Api\BackendApi\Response\CreateUserResponse $response */
  $response = $backendApi->send($request);
  $user->set('field_backend_profile', $response->getProfileId());
  $user->set('field_backend_password', $response->getPassword());
  $user->save();

  return $response->getProfileId();
}

/**
 * Delete the user's applications and recreate the scenario application.
 *
 * @param \Drupal\user\UserInterface $user
 *   Customer user.
 * @param array|null $application
 *   Scenario application entry, or NULL for none.
 * @param array $uuids
 *   Baseline key to UUID maps.
 *
 * @return int|null
 *   Drupal application id, or NULL.
 */
function e2e_customers_reset_application(UserInterface $user, ?array $application, array $uuids): ?int {
  $storage = \Drupal::entityTypeManager()->getStorage('asu_application');
  $existing = $storage->loadByProperties(['uid' => $user->id()]);
  if ($existing) {
    $storage->delete($existing);
  }
  if ($application === NULL) {
    return NULL;
  }

  $project = e2e_customers_node($uuids['projects'][$application['project']]);
  $apartment = e2e_customers_node($uuids['apartments'][$application['apartment']]);
  $ownershipType = strtolower($project->get('field_ownership_type')->entity->label());

  // Application::preCreate() assigns the owner from the current user, the
  // same way as when a customer opens the application form.
  $accountSwitcher = \Drupal::service('account_switcher');
  $accountSwitcher->switchTo($user);
  try {
    $entity = $storage->create([
      'bundle' => $ownershipType,
      'project_id' => (int) $project->id(),
      'project' => (int) $project->id(),
      'apartment' => [
        [
          'id' => (int) $apartment->id(),
          'information' => $apartment->get('field_apartment_number')->value,
        ],
      ],
      'field_backend_id' => $application['backend_uuid'],
      'field_locked' => 1,
      'status' => 1,
    ]);
    $entity->save();
  }
  finally {
    $accountSwitcher->switchBack();
  }
  return (int) $entity->id();
}

/**
 * Load customers.json into Drupal and print one summary line per customer.
 */
function e2e_customers_main(): void {
  $password = getenv('E2E_CUSTOMER_PASSWORD');
  if (!$password) {
    throw new \RuntimeException('E2E_CUSTOMER_PASSWORD is not set');
  }
  $customers = e2e_customers_read_json(getenv('E2E_CUSTOMERS_FILE') ?: E2E_CUSTOMERS_DEFAULT_FILE);
  $baseline = e2e_customers_read_json(getenv('E2E_BASELINE_FILE') ?: E2E_CUSTOMERS_BASELINE_DEFAULT_FILE);
  $uuids = e2e_customers_baseline_uuids($baseline);

  foreach ($customers['customers'] as $customer) {
    $user = e2e_customers_upsert_user($customer, $password);
    $profileId = e2e_customers_ensure_profile($user, $customer);
    $applicationId = e2e_customers_reset_application($user, $customer['application'], $uuids);
    printf(
      "[e2e-customers] %s: uid=%d profile=%s application=%s\n",
      $customer['key'],
      $user->id(),
      $profileId,
      $applicationId ?? 'none'
    );
  }
}

e2e_customers_main();
