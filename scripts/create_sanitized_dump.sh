#!/bin/bash
#
# Write an anonymized SQL dump to django_sanitized_YYYYMMDDHHMMSS.sql and keep only
# the newest dumps in the target directory. Live rows are not modified.

set -euo pipefail

usage() {
  echo "Usage: $0 [-d directory] [-k keep]"
  echo "  -d  Directory for django_sanitized_*.sql (default: SANITIZED_DUMP_DIR or current directory)"
  echo "  -k  Number of newest dumps to keep after creating (default: 5)"
}

dump_dir="${SANITIZED_DUMP_DIR:-.}"
# Drupal dumps use "drupal_sanitized_", so both can share a directory.
prefix="django_sanitized_"
keep=5

while getopts ":d:k:h" opt; do
  case $opt in
    d) dump_dir="$OPTARG" ;;
    k) keep="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) echo "Error: -$OPTARG requires an argument." >&2; usage >&2; exit 1 ;;
    *) echo "Error: Invalid option -$OPTARG." >&2; usage >&2; exit 1 ;;
  esac
done

if ! [[ "$keep" =~ ^[1-9][0-9]*$ ]]; then
  echo "Error: -k must be a positive integer." >&2
  exit 1
fi

mkdir -p -- "$dump_dir"
if [ ! -w "$dump_dir" ]; then
  echo "Error: Dump directory '$dump_dir' is not writable. Pass a writable -d." >&2
  exit 1
fi
# Resolve before changing directory so relative paths keep working.
dump_dir="$(cd -- "$dump_dir" && pwd)"

# manage.py and .sanitizerconfig are resolved relative to the project root.
cd -- "$(dirname -- "$0")/.."

# Write to a .tmp file first so a failed dump never replaces or prunes good ones.
outfile="$dump_dir/${prefix}$(date +%Y%m%d%H%M%S).sql"
if ! ./manage.py create_sanitized_dump > "$outfile.tmp" || [ ! -s "$outfile.tmp" ]; then
  rm -f -- "$outfile.tmp"
  echo "Sanitized dump failed; existing dumps left untouched." >&2
  exit 1
fi
mv -- "$outfile.tmp" "$outfile"
echo "Created $outfile"

old=$(ls -1 "$dump_dir"/"$prefix"*.sql 2>/dev/null | sort -r | tail -n +$((keep + 1)))
if [ -n "$old" ]; then
  echo "Removing old dumps:"
  echo "$old"
  echo "$old" | xargs rm -f --
fi
