#!/bin/bash
#
# Replace the database at DATABASE_URL with a sanitized dump, then migrate.
# Everything in the public schema is dropped first, in the same transaction as
# the import, so a failed import leaves the database unchanged.

set -euo pipefail

usage() {
  echo "Usage: $0 [-y] dump.sql"
  echo "  -y  Do not ask for confirmation"
}

assume_yes=0
while getopts ":yh" opt; do
  case $opt in
    y) assume_yes=1 ;;
    h) usage; exit 0 ;;
    *) echo "Error: Invalid option -$OPTARG." >&2; usage >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

if [ $# -ne 1 ]; then
  usage >&2
  exit 1
fi
if [ ! -s "$1" ]; then
  echo "Error: Dump file '$1' does not exist or is empty." >&2
  exit 1
fi
if [ -z "${DATABASE_URL:-}" ]; then
  echo "Error: DATABASE_URL is not set." >&2
  exit 1
fi
# Resolve before changing directory so relative paths keep working.
dump="$(cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")"

# Show the target without the password.
target="$(echo "$DATABASE_URL" | sed -E 's#//[^@/]*@#//#')"

# A dump from a newer server uses settings an older one rejects, e.g.
# transaction_timeout (Postgres 17). Check before anything is dropped.
dump_major="$(sed -n -E 's/^-- Dumped from database version ([0-9]+).*/\1/p' "$dump" | head -n 1)"
server_major="$(psql -At "$DATABASE_URL" -c "SHOW server_version_num")"
server_major=$((server_major / 10000))
if [ -n "$dump_major" ] && [ "$dump_major" -gt "$server_major" ]; then
  echo "Error: The dump is from Postgres $dump_major but $target runs Postgres $server_major." >&2
  echo "Restore it into Postgres $dump_major or newer. Nothing was changed." >&2
  exit 1
fi
echo "This drops everything in $target and imports $dump."
if [ "$assume_yes" -ne 1 ]; then
  read -r -p "Type 'yes' to continue: " answer
  if [ "$answer" != "yes" ]; then
    echo "Aborted." >&2
    exit 1
  fi
fi

# manage.py is resolved relative to the project root.
cd -- "$(dirname -- "$0")/.."

# One transaction: if the import fails, the drop is rolled back too.
psql -v ON_ERROR_STOP=1 -q --single-transaction "$DATABASE_URL" \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
  -f "$dump"
./manage.py migrate --noinput
echo "Restored $dump. Users' passwords are the SANITIZED_DUMP_PASSWORD used when dumping."
