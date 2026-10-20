#!/bin/bash
# E2E startup: run DB updates and config import.
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

echo "[e2e] Clearing caches..."
drush cr || true
