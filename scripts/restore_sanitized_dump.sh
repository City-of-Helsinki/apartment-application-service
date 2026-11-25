#!/bin/bash
#
# Replace the database at DATABASE_URL with a sanitized dump, then migrate.
# DATABASE_PASSWORD is used as PGPASSWORD unless PGPASSWORD is already set.
# Tables, views, sequences and foreign tables in schema public are dropped
# (extension members excluded), in the same transaction as the import, so a
# failed import leaves the database unchanged. The schema itself is kept, so the
# connecting role does not need to own it. COMMENT ON SCHEMA/EXTENSION and
# DROP EXTENSION lines are filtered out of the dump, since they need ownership
# of the schema or extension and would drop extension member tables. Empty COPY
# blocks are skipped, since they need INSERT on e.g. extension config tables.

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
# The settings read the password from DATABASE_PASSWORD when the URL lacks it.
if [ -n "${DATABASE_PASSWORD:-}" ] && [ -z "${PGPASSWORD:-}" ]; then
  export PGPASSWORD="$DATABASE_PASSWORD"
fi
# Resolve before changing directory so relative paths keep working.
dump="$(cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")"

# Show the target without the password.
target="$(echo "$DATABASE_URL" | sed -E 's#//[^@/]*@#//#')"

# A dump from a newer server uses settings an older one rejects, e.g.
# transaction_timeout (Postgres 17). Check before anything is dropped.
dump_major="$(sed -n -E '/^-- Dumped from database version [0-9]/{s/^-- Dumped from database version ([0-9]+).*/\1/p;q;}' "$dump")"
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

# Drop relations in public that do not belong to an extension; sequences last,
# since most are dropped with their owning table.
drop_sql="$(cat <<'SQL'
DO $$
DECLARE
  rel record;
BEGIN
  FOR rel IN
    SELECT n.nspname, c.relname, c.relkind
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
      AND NOT EXISTS (
        SELECT 1 FROM pg_depend d
        WHERE d.classid = 'pg_class'::regclass
          AND d.objid = c.oid
          AND d.deptype = 'e'
      )
    ORDER BY c.relkind = 'S', c.relname
  LOOP
    EXECUTE format(
      'DROP %s IF EXISTS %I.%I CASCADE',
      CASE rel.relkind
        WHEN 'v' THEN 'VIEW'
        WHEN 'm' THEN 'MATERIALIZED VIEW'
        WHEN 'S' THEN 'SEQUENCE'
        WHEN 'f' THEN 'FOREIGN TABLE'
        ELSE 'TABLE'
      END,
      rel.nspname,
      rel.relname
    );
  END LOOP;
END
$$;
SQL
)"

# Print the dump without statements that need schema or extension ownership,
# and without empty COPY blocks: COPY needs INSERT privilege even for zero rows,
# and dumps hold one for extension config tables such as spatial_ref_sys.
# COPY data lines are passed through unchanged.
filter_dump() {
  awk '
    pending != "" {
      if ($0 == "\\.") { pending = ""; next }
      print pending
      pending = ""
      in_copy = 1
    }
    in_copy { print; if ($0 == "\\.") in_copy = 0; next }
    /^COPY .* FROM stdin;$/ { pending = $0; next }
    /^(COMMENT ON (SCHEMA|EXTENSION)|DROP EXTENSION) / { next }
    { print }
    END { if (pending != "") print pending }
  ' "$dump"
}

# One transaction: if the import fails, the drop is rolled back too.
# RESET ALL undoes the dump's session SETs (e.g. search_path = ''), which a
# transaction-pooling PgBouncer would otherwise leave on the server connection.
filter_dump | psql -v ON_ERROR_STOP=1 -q --single-transaction "$DATABASE_URL" \
  -c "$drop_sql" \
  -f - \
  -c "RESET ALL"
./manage.py migrate --noinput
echo "Restored $dump. Users' passwords are the SANITIZED_DUMP_PASSWORD used when dumping."
