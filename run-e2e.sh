#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP=0
PLAYWRIGHT_ARGS=""

for arg in "$@"; do
  case "$arg" in
    --keep|-k) KEEP=1 ;;
    --headed) PLAYWRIGHT_ARGS="$PLAYWRIGHT_ARGS --headed" ;;
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
#
# django-app is brought up separately (and last): it's the only service with
# a `build:` step, and `docker compose up --build` builds every listed
# service before starting ANY of them — so a transient failure building
# django-app (e.g. a registry hiccup pulling its base image) would otherwise
# prevent drupal-app etc. from starting at all, even though they don't need
# a build and have nothing to do with the failure.
echo "[e2e] Ensuring Drupal stack is up to date..."
$COMPOSE up -d drupal-db drupal-elastic drupal-redis drupal-app django-db django-elastic

echo "[e2e] Ensuring Django stack is up to date..."
$COMPOSE up --build -d django-app

# Polls the service's own HTTP port rather than grepping logs for text: nginx
# (Drupal) and `runserver` (Django) both start only after the deploy
# script / fixture load finishes, so "responds to HTTP" is a direct,
# unambiguous readiness signal — and it isn't at the mercy of log-buffering
# delays between a command finishing and its output actually showing up in
# `docker compose logs`.
wait_for_http() {
  local name="$1" url="$2" max_seconds="$3"
  local waited=0
  echo -n "[e2e] Waiting for $name to respond at $url "
  while ! curl -sf -o /dev/null "$url" 2>/dev/null; do
    if [ "$waited" -ge "$max_seconds" ]; then
      echo " TIMED OUT after ${max_seconds}s"
      echo "[e2e] $name did not become ready in time — recent logs:" >&2
      $COMPOSE logs --tail=40 "$name" >&2 2>&1 || true
      return 1
    fi
    echo -n "."
    sleep 1
    waited=$((waited + 1))
  done
  echo " ready after ${waited}s"
}

wait_for_http drupal-app "http://localhost:18080/fi" 120
wait_for_http django-app "http://localhost:18081/healthz" 120

echo "[e2e] Generating one-time admin login link..."
LOGIN_URL=$($COMPOSE exec -T drupal-app drush uli --uid=1 --uri="http://drupal-app:8080" 2>/dev/null | tr -d '\r')
# The link grants admin access, so it is passed to the test runner but not printed.
if [ -z "$LOGIN_URL" ]; then
  echo "[e2e] WARNING: failed to generate admin login link; auth tests will be skipped" >&2
fi

echo "[e2e] Running tests..."
set +e
$COMPOSE run --rm -e E2E_LOGIN_URL="$LOGIN_URL" -e PLAYWRIGHT_ARGS="$PLAYWRIGHT_ARGS" test-runner
EXIT_CODE=$?
set -e

# Only tear down if we started the stack and --keep was not given
if [ "$KEEP" -eq 0 ] && [ "$STACK_WAS_RUNNING" -eq 0 ]; then
  $COMPOSE down -v
fi

exit $EXIT_CODE
