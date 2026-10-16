#!/bin/bash
# E2E startup: run DB updates and config import.
# Sourced by the helfi image entrypoint from /entrypoints/.

if [ "$SKIP_DEPLOY_SCRIPTS" = "true" ]; then
    echo "[e2e] SKIP_DEPLOY_SCRIPTS=true, skipping."
    return 0
fi

echo "[e2e] Running drush updatedb..."
drush updatedb -y || true

echo "[e2e] Running drush cim..."
drush cim -y || true

echo "[e2e] Clearing caches..."
drush cr || true
