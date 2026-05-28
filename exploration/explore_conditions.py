"""
Explore all conditions in MIDRC dataset to identify additional risk factors
and comorbidities that should be included as inputs to the risk head.
"""

import io, json, sys
import pandas as pd
from collections import Counter

try:
    from gen3.auth import Gen3Auth
    from gen3.submission import Gen3Submission
except ImportError:
    print("ERROR: gen3 package not found")
    sys.exit(1)

API = "https://data.midrc.org"

print("Connecting to MIDRC...")
auth = Gen3Auth(API, refresh_file="credentials.json")
sub = Gen3Submission(API, auth)
print(f"✓ Connected to {API}\n")

print("Exporting condition node...")
cond_raw = sub.export_node("Open", "A1", "condition", "tsv")
df_cond = pd.read_csv(io.StringIO(cond_raw), sep="\t")

print(f"Total condition records: {len(df_cond):,}")
print(f"Unique cases: {df_cond['case_ids'].nunique():,}\n")

# Get all unique condition names
all_conditions = df_cond["condition_name"].dropna().unique()
print(f"Total unique conditions: {len(all_conditions)}\n")

# Count them
condition_counts = Counter(df_cond["condition_name"].dropna())

print("=" * 80)
print("TOP 50 CONDITIONS BY FREQUENCY")
print("=" * 80)
for i, (cond, count) in enumerate(condition_counts.most_common(50), 1):
    pct = 100 * count / len(df_cond)
    print(f"{i:2d}. [{count:5,} / {pct:5.1f}%] {cond}")

print("\n" + "=" * 80)
print("ALL CONDITIONS (sorted alphabetically)")
print("=" * 80)
for i, cond in enumerate(sorted(all_conditions), 1):
    count = condition_counts[cond]
    pct = 100 * count / len(df_cond)
    print(f"{i:3d}. [{count:5,} / {pct:5.1f}%] {cond}")

# Categorize by ICD-10 prefix
print("\n" + "=" * 80)
print("GROUPED BY ICD-10 CATEGORY (prefix)")
print("=" * 80)

categories = {}
for cond in sorted(all_conditions):
    prefix = cond[0] if cond else "?"
    if prefix not in categories:
        categories[prefix] = []
    categories[prefix].append((cond, condition_counts[cond]))

for prefix in sorted(categories.keys()):
    total = sum(count for _, count in categories[prefix])
    pct = 100 * total / len(df_cond)
    print(f"\n{prefix} [{total:,} / {pct:.1f}%]:")
    for cond, count in sorted(categories[prefix], key=lambda x: -x[1])[:15]:
        pct_cat = 100 * count / total
        print(f"    {cond:<60} {count:>5,} ({pct_cat:>5.1f}%)")
    if len(categories[prefix]) > 15:
        print(f"    ... and {len(categories[prefix]) - 15} more")

# Export for manual review
with open("data/all_conditions_in_midrc.json", "w") as f:
    json.dump({
        "total_records": len(df_cond),
        "unique_conditions": len(all_conditions),
        "all_conditions": sorted([
            {"name": cond, "count": int(condition_counts[cond])}
            for cond in all_conditions
        ], key=lambda x: -x["count"])
    }, f, indent=2)

print(f"\n✓ Full list exported to: data/all_conditions_in_midrc.json")
