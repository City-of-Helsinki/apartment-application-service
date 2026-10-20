<?php

/**
 * @file
 * Loads the committed e2e baseline content (baseline.json) into Drupal.
 *
 * Run with: drush php:script /e2e/fixtures/drupal/load_baseline.php
 *
 * Each project/apartment is matched by its node UUID, so re-running updates
 * the same nodes in place. Nodes are saved only when a value differs. Every
 * baseline node is then reindexed in the search_api indexes that contain it.
 * The baseline file path is read from E2E_BASELINE_FILE.
 *
 * Exits non-zero on invalid input or a failed save (all saves are rolled
 * back). Indexing errors only warn: search_api cron indexes tracked items.
 */

use Drupal\Core\Entity\ContentEntityInterface;
use Drupal\node\Entity\Node;
use Drupal\node\NodeInterface;
use Drupal\search_api\Entity\Index;
use Drupal\search_api\Utility\Utility;
use Drupal\taxonomy\Entity\Term;

const E2E_BASELINE_DEFAULT_FILE = '/e2e/fixtures/baseline.json';
const E2E_BASELINE_LANGCODE = 'fi';
const E2E_BASELINE_OWNER_UID = 1;
// Not in baseline.json; asu_rest project listings exclude projects without a
// state of sale (and "upcoming" ones), so a sellable state is set.
const E2E_BASELINE_PROJECT_STATE_OF_SALE = 'for_sale';
const E2E_BASELINE_UUID_PATTERN = '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/';

/**
 * Print an error to stderr and terminate with exit code 1.
 *
 * @param string $message
 *   Error description.
 */
function e2e_baseline_fail(string $message): never {
  fwrite(STDERR, "[e2e-baseline] ERROR: {$message}\n");
  exit(1);
}

/**
 * Read and decode the baseline file.
 *
 * @param string $path
 *   Filesystem path to baseline.json.
 *
 * @return array
 *   Decoded baseline content.
 */
function e2e_baseline_read(string $path): array {
  if (!is_file($path) || !is_readable($path)) {
    e2e_baseline_fail("Baseline file not readable: {$path}");
  }
  try {
    $data = json_decode(file_get_contents($path), TRUE, 512, JSON_THROW_ON_ERROR);
  }
  catch (\JsonException $e) {
    e2e_baseline_fail("Invalid JSON in {$path}: {$e->getMessage()}");
  }
  if (!is_array($data)) {
    e2e_baseline_fail("Baseline root must be an object: {$path}");
  }
  return $data;
}

/**
 * Return a required non-empty string value from an entry.
 *
 * @param array $entry
 *   Project or apartment entry.
 * @param string $key
 *   Key to read.
 * @param string $context
 *   Entry description used in error messages.
 *
 * @return string
 *   The string value.
 */
function e2e_baseline_require_string(array $entry, string $key, string $context): string {
  $value = $entry[$key] ?? NULL;
  if (!is_string($value) || trim($value) === '') {
    e2e_baseline_fail("{$context}: \"{$key}\" must be a non-empty string");
  }
  return $value;
}

/**
 * Return an optional string value from an entry.
 *
 * @param array $entry
 *   Project or apartment entry.
 * @param string $key
 *   Key to read.
 * @param string $context
 *   Entry description used in error messages.
 *
 * @return string|null
 *   The string value, or NULL when absent.
 */
function e2e_baseline_optional_string(array $entry, string $key, string $context): ?string {
  if (!array_key_exists($key, $entry)) {
    return NULL;
  }
  if (!is_string($entry[$key])) {
    e2e_baseline_fail("{$context}: \"{$key}\" must be a string");
  }
  return $entry[$key];
}

/**
 * Validate the baseline structure and collect UUIDs.
 *
 * @param array $data
 *   Decoded baseline content.
 */
function e2e_baseline_validate(array $data): void {
  if (empty($data['projects']) || !is_array($data['projects']) || !array_is_list($data['projects'])) {
    e2e_baseline_fail('"projects" must be a non-empty list');
  }
  $seen = [];
  foreach ($data['projects'] as $index => $project) {
    $context = "projects[{$index}]";
    if (!is_array($project)) {
      e2e_baseline_fail("{$context} must be an object");
    }
    foreach (['key', 'uuid', 'ownership_type', 'housing_company', 'street_address'] as $key) {
      e2e_baseline_require_string($project, $key, $context);
    }
    foreach (['postal_code', 'city'] as $key) {
      e2e_baseline_optional_string($project, $key, $context);
    }
    $entries = [[$project, $context]];
    if (empty($project['apartments']) || !is_array($project['apartments']) || !array_is_list($project['apartments'])) {
      e2e_baseline_fail("{$context}: \"apartments\" must be a non-empty list");
    }
    foreach ($project['apartments'] as $apartmentIndex => $apartment) {
      $apartmentContext = "{$context}.apartments[{$apartmentIndex}]";
      if (!is_array($apartment)) {
        e2e_baseline_fail("{$apartmentContext} must be an object");
      }
      foreach (['key', 'uuid', 'apartment_number'] as $key) {
        e2e_baseline_require_string($apartment, $key, $apartmentContext);
      }
      e2e_baseline_optional_string($apartment, 'apartment_structure', $apartmentContext);
      if (array_key_exists('living_area', $apartment)
        && (!is_int($apartment['living_area']) && !is_float($apartment['living_area']))) {
        e2e_baseline_fail("{$apartmentContext}: \"living_area\" must be a number");
      }
      if (array_key_exists('floor', $apartment) && !is_int($apartment['floor'])) {
        e2e_baseline_fail("{$apartmentContext}: \"floor\" must be an integer");
      }
      $entries[] = [$apartment, $apartmentContext];
    }
    foreach ($entries as [$entry, $entryContext]) {
      if (!preg_match(E2E_BASELINE_UUID_PATTERN, $entry['uuid'])) {
        e2e_baseline_fail("{$entryContext}: \"uuid\" must be a lowercase canonical UUID");
      }
      if (isset($seen[$entry['uuid']])) {
        e2e_baseline_fail("{$entryContext}: duplicate uuid {$entry['uuid']}");
      }
      $seen[$entry['uuid']] = TRUE;
    }
  }
}

/**
 * Load a node of the given bundle by UUID, or create an unsaved one.
 *
 * @param string $uuid
 *   Node UUID.
 * @param string $bundle
 *   Expected node bundle.
 *
 * @return \Drupal\node\NodeInterface
 *   Existing or new (unsaved) node.
 *
 * @throws \RuntimeException
 *   When the UUID belongs to an entity of another type or bundle.
 */
function e2e_baseline_load_or_create_node(string $uuid, string $bundle): NodeInterface {
  $node = \Drupal::service('entity.repository')->loadEntityByUuid('node', $uuid);
  if ($node === NULL) {
    return Node::create([
      'type' => $bundle,
      'uuid' => $uuid,
      'langcode' => E2E_BASELINE_LANGCODE,
      'uid' => E2E_BASELINE_OWNER_UID,
    ]);
  }
  if (!$node instanceof NodeInterface || $node->bundle() !== $bundle) {
    throw new \RuntimeException("UUID {$uuid} belongs to an existing non-{$bundle} entity");
  }
  return $node;
}

/**
 * Set a single-value field when its value differs.
 *
 * @param \Drupal\Core\Entity\ContentEntityInterface $entity
 *   Entity to modify.
 * @param string $field
 *   Field name.
 * @param string|int|float|null $value
 *   New value; NULL empties the field.
 *
 * @return bool
 *   TRUE if the field was changed.
 */
function e2e_baseline_set_value(ContentEntityInterface $entity, string $field, string|int|float|null $value): bool {
  $current = $entity->get($field)->isEmpty() ? NULL : $entity->get($field)->first()->getValue();
  $current = $current === NULL ? NULL : reset($current);
  $same = is_float($value) || is_int($value)
    ? $current !== NULL && is_numeric($current) && (float) $current === (float) $value
    : $current === $value;
  if ($same) {
    return FALSE;
  }
  $entity->set($field, $value);
  return TRUE;
}

/**
 * Set an entity reference field to the given target IDs when they differ.
 *
 * @param \Drupal\Core\Entity\ContentEntityInterface $entity
 *   Entity to modify.
 * @param string $field
 *   Reference field name.
 * @param array $targetIds
 *   Ordered target IDs.
 *
 * @return bool
 *   TRUE if the field was changed.
 */
function e2e_baseline_set_references(ContentEntityInterface $entity, string $field, array $targetIds): bool {
  $current = array_map('strval', array_column($entity->get($field)->getValue(), 'target_id'));
  $targetIds = array_map('strval', $targetIds);
  if ($current === $targetIds) {
    return FALSE;
  }
  $entity->set($field, array_map(static fn ($id) => ['target_id' => $id], $targetIds));
  return TRUE;
}

/**
 * Return the ID of the ownership_type term with the given name.
 *
 * The term is created when missing.
 *
 * @param string $name
 *   Term name (e.g. "HASO").
 *
 * @return int|string
 *   Term ID.
 */
function e2e_baseline_ownership_term_id(string $name): int|string {
  $terms = \Drupal::entityTypeManager()->getStorage('taxonomy_term')->loadByProperties([
    'vid' => 'ownership_type',
    'name' => $name,
  ]);
  if ($terms) {
    return reset($terms)->id();
  }
  $term = Term::create(['vid' => 'ownership_type', 'name' => $name]);
  $term->save();
  echo "[e2e-baseline] Created ownership_type term \"{$name}\"\n";
  return $term->id();
}

/**
 * Save a node if it is new or changed and record the outcome.
 *
 * @param \Drupal\node\NodeInterface $node
 *   Node to save.
 * @param bool $changed
 *   Whether any value was changed.
 * @param array $counts
 *   Outcome counters keyed by created/updated/unchanged.
 */
function e2e_baseline_save(NodeInterface $node, bool $changed, array &$counts): void {
  if ($node->isNew()) {
    $node->save();
    $counts['created']++;
  }
  elseif ($changed) {
    $node->save();
    $counts['updated']++;
  }
  else {
    $counts['unchanged']++;
  }
}

/**
 * Create or update one apartment node.
 *
 * @param array $apartment
 *   Apartment entry.
 * @param string $streetAddress
 *   Street address of the parent project, used in the title.
 * @param array $counts
 *   Outcome counters.
 *
 * @return \Drupal\node\NodeInterface
 *   The saved apartment node.
 */
function e2e_baseline_upsert_apartment(array $apartment, string $streetAddress, array &$counts): NodeInterface {
  $node = e2e_baseline_load_or_create_node($apartment['uuid'], 'apartment');
  // Same format asu_content uses when it retitles a project's apartments.
  $changed = e2e_baseline_set_value($node, 'title', "{$streetAddress} {$apartment['apartment_number']}");
  $changed = e2e_baseline_set_value($node, 'field_apartment_number', $apartment['apartment_number']) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_apartment_structure', $apartment['apartment_structure'] ?? NULL) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_living_area', $apartment['living_area'] ?? NULL) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_floor', $apartment['floor'] ?? NULL) || $changed;
  if (!$node->isPublished()) {
    $node->setPublished();
    $changed = TRUE;
  }
  e2e_baseline_save($node, $changed, $counts);
  return $node;
}

/**
 * Create or update one project node and its apartments.
 *
 * Apartments are saved first so a new project is created with
 * field_apartments already set; asu_content otherwise adds a placeholder
 * apartment to projects inserted without apartments.
 *
 * @param array $project
 *   Project entry.
 * @param array $counts
 *   Outcome counters.
 *
 * @return \Drupal\node\NodeInterface[]
 *   The saved project node followed by its apartment nodes.
 */
function e2e_baseline_upsert_project(array $project, array &$counts): array {
  $apartments = [];
  foreach ($project['apartments'] as $apartment) {
    $apartments[] = e2e_baseline_upsert_apartment($apartment, $project['street_address'], $counts);
  }

  $node = e2e_baseline_load_or_create_node($project['uuid'], 'project');
  // Same "<housing company> / <street address>" format as real projects.
  $changed = e2e_baseline_set_value($node, 'title', "{$project['housing_company']} / {$project['street_address']}");
  $changed = e2e_baseline_set_value($node, 'field_housing_company', $project['housing_company']) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_street_address', $project['street_address']) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_postal_code', $project['postal_code'] ?? NULL) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_city', $project['city'] ?? NULL) || $changed;
  $changed = e2e_baseline_set_value($node, 'field_archived', 0) || $changed;
  $changed = e2e_baseline_set_references($node, 'field_state_of_sale', [E2E_BASELINE_PROJECT_STATE_OF_SALE]) || $changed;
  $ownershipTermId = e2e_baseline_ownership_term_id($project['ownership_type']);
  $changed = e2e_baseline_set_references($node, 'field_ownership_type', [$ownershipTermId]) || $changed;
  $apartmentIds = array_map(static fn (NodeInterface $apartment) => $apartment->id(), $apartments);
  $changed = e2e_baseline_set_references($node, 'field_apartments', $apartmentIds) || $changed;
  if (!$node->isPublished()) {
    $node->setPublished();
    $changed = TRUE;
  }
  e2e_baseline_save($node, $changed, $counts);

  return [$node, ...$apartments];
}

/**
 * Reindex the given nodes in every enabled index that contains them.
 *
 * Items are marked as updated in the tracker first (also unchanged ones), so
 * when the server is unavailable or indexing fails they stay queued for
 * search_api cron.
 *
 * @param \Drupal\node\NodeInterface[] $nodes
 *   Nodes to reindex.
 *
 * @return string[]
 *   Per-index summaries, e.g. "apartment=6".
 */
function e2e_baseline_reindex(array $nodes): array {
  $datasourceId = 'entity:node';
  $summaries = [];
  foreach (Index::loadMultiple() as $index) {
    if (!$index->status() || $index->isReadOnly() || !$index->isValidDatasource($datasourceId)) {
      continue;
    }
    // Only bundles the index contains; loading other items would make
    // search_api log them as missing and queue server-side deletions.
    $bundles = $index->getDatasource($datasourceId)->getBundles();
    $rawIds = [];
    foreach ($nodes as $node) {
      if (isset($bundles[$node->bundle()])) {
        foreach (array_keys($node->getTranslationLanguages()) as $langcode) {
          $rawIds[] = "{$node->id()}:{$langcode}";
        }
      }
    }
    if (!$rawIds) {
      continue;
    }
    $index->trackItemsUpdated($datasourceId, $rawIds);
    if (!$index->isServerEnabled() || !$index->getServerInstance()->isAvailable()) {
      $summaries[] = "{$index->id()}=queued (server unavailable)";
      continue;
    }
    try {
      $itemIds = array_map(static fn ($rawId) => Utility::createCombinedId($datasourceId, $rawId), $rawIds);
      $indexed = $index->indexSpecificItems($index->loadItemsMultiple($itemIds));
      $summaries[] = "{$index->id()}=" . count($indexed);
    }
    catch (\Exception $e) {
      fwrite(STDERR, "[e2e-baseline] WARNING: indexing {$index->id()} failed, left to cron: {$e->getMessage()}\n");
      $summaries[] = "{$index->id()}=queued (indexing failed)";
    }
  }
  return $summaries;
}

/**
 * Load the baseline file into Drupal and print a summary line.
 */
function e2e_baseline_main(): void {
  $path = getenv('E2E_BASELINE_FILE') ?: E2E_BASELINE_DEFAULT_FILE;
  $data = e2e_baseline_read($path);
  e2e_baseline_validate($data);

  $counts = ['created' => 0, 'updated' => 0, 'unchanged' => 0];
  $nodes = [];
  $transaction = \Drupal::database()->startTransaction();
  try {
    foreach ($data['projects'] as $project) {
      array_push($nodes, ...e2e_baseline_upsert_project($project, $counts));
    }
  }
  catch (\Throwable $e) {
    $transaction->rollBack();
    e2e_baseline_fail("Saving baseline content failed: {$e->getMessage()}");
  }
  // Commit before indexing so a failed index run cannot undo the content.
  $transaction->commitOrRelease();

  $indexSummary = implode(', ', e2e_baseline_reindex($nodes)) ?: 'none';
  printf(
    "[e2e-baseline] Loaded %s: %d projects, %d nodes (created=%d, updated=%d, unchanged=%d); indexed: %s\n",
    $path,
    count($data['projects']),
    count($nodes),
    $counts['created'],
    $counts['updated'],
    $counts['unchanged'],
    $indexSummary
  );
}

e2e_baseline_main();
