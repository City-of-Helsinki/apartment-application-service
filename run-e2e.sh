#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP=0

for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# Load env vars so COMPOSE_PROJECT_NAME etc. are set for docker compose
set -a
# shellcheck source=env.e2e
source "$SCRIPT_DIR/env.e2e"
set +a

COMPOSE="docker compose -f $SCRIPT_DIR/compose.e2e.yaml --env-file $SCRIPT_DIR/env.e2e"

$COMPOSE up --build --abort-on-container-exit --exit-code-from test-runner
EXIT_CODE=$?

if [ "$KEEP" -eq 0 ]; then
  $COMPOSE down -v
fi

exit $EXIT_CODE
