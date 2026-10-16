#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP=0

for arg in "$@"; do
  case "$arg" in
    --keep|-k) KEEP=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# Load env vars so COMPOSE_PROJECT_NAME etc. are set for docker compose
set -a
# shellcheck source=.env.e2e
source "$SCRIPT_DIR/.env.e2e"
set +a

COMPOSE="docker compose -f $SCRIPT_DIR/compose.e2e.yaml --env-file $SCRIPT_DIR/.env.e2e"

# Note whether the stack was already up, so we know whether to tear it down later.
STACK_WAS_RUNNING=0
if $COMPOSE ps --status running --services 2>/dev/null | grep -q "drupal-app"; then
  STACK_WAS_RUNNING=1
fi

# Always reconcile: if compose.e2e.yaml changed since the containers were
# created, `docker compose run test-runner` below would otherwise silently
# recreate stale dependencies with no readiness wait, racing the test run
# against a half-booted Drupal. Running this explicitly first means any
# recreate happens here, where we wait for it.
echo "[e2e] Ensuring stack is up to date..."
$COMPOSE up --build -d drupal-db drupal-elastic drupal-redis drupal-app django-db django-elastic django-app

echo "[e2e] Waiting for Drupal deploy script to finish..."
for i in $(seq 1 60); do
  if $COMPOSE logs drupal-app 2>&1 | grep -q "\[e2e\] Clearing caches"; then
    break
  fi
  sleep 3
done

echo "[e2e] Waiting for Django (incl. fixture load) to finish..."
for i in $(seq 1 60); do
  if $COMPOSE logs django-app 2>&1 | grep -q "Starting development server"; then
    break
  fi
  sleep 3
done

echo "[e2e] Generating one-time admin login link..."
LOGIN_URL=$($COMPOSE exec -T drupal-app drush uli --uid=1 --uri="http://drupal-app:8080" 2>/dev/null | tr -d '\r')
echo "[e2e] Login URL: $LOGIN_URL"

echo "[e2e] Running tests..."
set +e
$COMPOSE run --rm -e E2E_LOGIN_URL="$LOGIN_URL" test-runner
EXIT_CODE=$?
set -e

# Only tear down if we started the stack and --keep was not given
if [ "$KEEP" -eq 0 ] && [ "$STACK_WAS_RUNNING" -eq 0 ]; then
  $COMPOSE down -v
fi

exit $EXIT_CODE
