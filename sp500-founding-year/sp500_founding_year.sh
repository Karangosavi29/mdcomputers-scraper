#!/usr/bin/env bash
#
# sp500_founding_year.sh
#
# Downloads the S&P 500 constituents CSV and prints:
#   Company Name | Headquarters Location | Founding Year
# sorted by Founding Year (ascending).
#
# Usage: ./sp500_founding_year.sh
#
# Requires: curl, python3 (used only for robust CSV parsing,
# since quoted fields like "Saint Paul, Minnesota" contain commas
# that plain awk/cut cannot split correctly).

set -euo pipefail

CSV_URL="https://raw.githubusercontent.com/datasets/s-and-p-500-companies/refs/heads/main/data/constituents.csv"
TMP_CSV="$(mktemp /tmp/sp500_XXXXXX.csv)"

cleanup() { rm -f "$TMP_CSV"; }
trap cleanup EXIT

echo "Downloading constituents CSV..." >&2
curl -fsSL "$CSV_URL" -o "$TMP_CSV"

python3 - "$TMP_CSV" << 'PYEOF'
import csv
import re
import sys

path = sys.argv[1]

rows = []
with open(path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row.get("Security", "").strip()
        location = row.get("Headquarters Location", "").strip()
        founded_raw = row.get("Founded", "").strip()

        # "Founded" sometimes looks like "2013 (1888)" -- take the first year found.
        match = re.search(r"\d{4}", founded_raw)
        founded_year = int(match.group()) if match else None

        rows.append((name, location, founded_year, founded_raw))

# Sort by founding year ascending; unknown years go last.
rows.sort(key=lambda r: (r[2] is None, r[2]))

col_w_name = max(len(r[0]) for r in rows) if rows else 10
col_w_loc = max(len(r[1]) for r in rows) if rows else 10

print(f"{'Company Name':<{col_w_name}} | {'Location':<{col_w_loc}} | Founded")
print("-" * (col_w_name + col_w_loc + 12))
for name, location, year, raw in rows:
    year_display = raw if raw else "N/A"
    print(f"{name:<{col_w_name}} | {location:<{col_w_loc}} | {year_display}")
PYEOF