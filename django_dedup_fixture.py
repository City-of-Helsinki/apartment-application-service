"""
Deduplicate a Django JSON fixture before loaddata.
Removes duplicate UserKeyValue rows (unique on user+key+value) which can
appear in dumps taken from a DB that has stale duplicate rows.

Usage: python django_dedup_fixture.py <input.json> <output.json>
"""

import json
import sys

USER_KEY_VALUE_MODEL = "users.userkeyvalue"


def dedup_user_key_values(items):
    """
    Remove duplicate UserKeyValue items, keeping the first occurrence.

            Parameters:
                    items (list[dict]): Django fixture items

            Returns:
                    result (tuple[list[dict], int]): Kept items in original order
                    and the number of removed duplicates
    """
    seen = set()
    kept = []
    skipped = 0
    for item in items:
        if item["model"] == USER_KEY_VALUE_MODEL:
            fields = item["fields"]
            identity = (fields["user"], fields["key"], fields["value"])
            if identity in seen:
                skipped += 1
                continue
            seen.add(identity)
        kept.append(item)
    return kept, skipped


def main(argv=None):
    """
    Read a fixture file, deduplicate it and write the result.

            Parameters:
                    argv (list[str] | None): Input and output paths; defaults to
                    sys.argv[1:]

            Returns:
                    exit_code (int): 0 on success, 2 on invalid arguments
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(
            "Usage: python django_dedup_fixture.py <input.json> <output.json>",
            file=sys.stderr,
        )
        return 2

    src, dst = args
    with open(src) as f:
        items = json.load(f)

    kept, skipped = dedup_user_key_values(items)
    print(
        f"[e2e] {len(kept)} objects kept, {skipped} duplicates removed",
        file=sys.stderr,
    )
    with open(dst, "w") as f:
        json.dump(kept, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
