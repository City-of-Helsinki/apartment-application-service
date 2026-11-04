#!/bin/bash
#
# Replace the database at DATABASE_URL with a sanitized dump, then migrate.
# Everything in the public schema is dropped first.

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

psql -v ON_ERROR_STOP=1 -q "$DATABASE_URL" \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql -v ON_ERROR_STOP=1 -q "$DATABASE_URL" -f "$dump"
./manage.py migrate --noinput
echo "Restored $dump. Users' passwords are the SANITIZED_DUMP_PASSWORD used when dumping."
