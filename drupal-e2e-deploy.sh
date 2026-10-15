#!/bin/bash
# E2E startup: run DB updates and config import, then load baseline content.
# Sourced by the helfi image entrypoint from /entrypoints/.

if [ "$SKIP_DEPLOY_SCRIPTS" = "true" ]; then
    echo "[e2e] SKIP_DEPLOY_SCRIPTS=true, skipping."
    return 0
fi

# Unlike Django's entrypoint, nothing here previously waited for the DB.
# drush would then fail with "Connection refused" if MariaDB (still
# importing the dump) wasn't ready yet — and since every drush call below
# is `|| true`, that failure was silently swallowed: the script still
# printed "Clearing caches", nginx still started, but config was never
# imported, leaving Drupal serving 500s while looking like it deployed fine.
echo "[e2e] Waiting for drupal-db to accept connections..."
for i in $(seq 1 60); do
    if drush sqlq "SELECT 1" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo "[e2e] Running drush updatedb..."
drush updatedb -y || true

echo "[e2e] Running drush cim..."
drush cim -y || true

# Django's sales project/apartment endpoints fetch data from Drupal with an
# OAuth client_credentials token. The consumer is a content entity, so it is
# not in config, and asu_rest only provisions it from install/update hooks
# that the dump has already run. Calling the (idempotent) provisioner here
# creates it from ASU_REST_OAUTH_CLIENT_ID/SECRET, which compose also hands
# to Django as DRUPAL_SEARCH_API_CLIENT_ID/SECRET.
echo "[e2e] Provisioning OAuth consumer for Django..."
drush php:eval "\Drupal::moduleHandler()->loadInclude('asu_rest', 'install'); asu_rest_provision_oauth_consumer();" || true

# Committed baseline content (e2e/fixtures/drupal/baseline.json): fixed-UUID
# projects and apartments that the tests rely on. The loader is idempotent
# and also reindexes the nodes in search_api. Unlike the steps above, a
# failure stops the container: this script is sourced by the image
# entrypoint, so `exit` ends it before nginx starts. Compose has no restart
# policy, so the container stays Exited(1) instead of crash-looping, and
# run-e2e.sh's readiness wait times out and prints these logs.
echo "[e2e] Loading baseline content..."
if ! drush php:script "${E2E_BASELINE_LOADER:-/e2e/fixtures/drupal/load_baseline.php}"; then
    echo "[e2e] ERROR: loading baseline content failed, stopping drupal-app." >&2
    exit 1
fi

echo "[e2e] Clearing caches..."
drush cr || true
