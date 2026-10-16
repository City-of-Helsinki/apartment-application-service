"""
Deduplicate a Django JSON fixture before loaddata.
Removes duplicate UserKeyValue rows (unique on user+key+value) which can
appear in dumps taken from a DB that has stale duplicate rows.

Usage: python django-dedup-fixture.py <input.json> <output.json>
"""
import json
import sys

src, dst = sys.argv[1], sys.argv[2]
with open(src) as f:
    data = json.load(f)

seen_ukv = set()
out = []
skipped = 0
for item in data:
    if item["model"] == "users.userkeyvalue":
        k = (item["fields"]["user"], item["fields"]["key"], item["fields"]["value"])
        if k in seen_ukv:
            skipped += 1
            continue
        seen_ukv.add(k)
    out.append(item)

print(f"[e2e] {len(out)} objects kept, {skipped} duplicates removed", file=sys.stderr)
with open(dst, "w") as f:
    json.dump(out, f)
