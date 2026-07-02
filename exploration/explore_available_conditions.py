#!/usr/bin/env python3
"""
Explore all available conditions and fields in MIDRC
to identify additional comorbidities and risk factors.
"""

import json
import io
import sys
import pandas as pd

try:
    from gen3.auth import Gen3Auth
    from gen3.submission import Gen3Submission
except ImportError:
    print("ERROR: gen3 package not found")
    sys.exit(1)

API = "https://data.midrc.org"

try:
    auth = Gen3Auth(API, refresh_file="credentials.json")
    sub = Gen3Submission(API, auth)
    print(f"✓ Connected to {API}\n")
except Exception as e:
    print(f"✗ Failed to authenticate: {e}")
    sys.exit(1)

# Export all data nodes
print("Exporting data nodes...")
cond_raw = sub.export_node("Open", "A1", "condition", "tsv")
obs_raw = sub.export_node("Open", "A1", "observation", "tsv")

df_cond = pd.read_csv(io.StringIO(cond_raw), sep="\t")
df_obs = pd.read_csv(io.StringIO(obs_raw), sep="\t", low_memory=False)

print(f"\n{'='*80}")
print("CONDITION NODE ANALYSIS")
print(f"{'='*80}")
print(f"Shape: {df_cond.shape}")
print(f"\nColumns: {list(df_cond.columns)}")

print(f"\n\nAll unique conditions ({df_cond['condition_name'].nunique()} total):")
print("─" * 80)
for name in sorted(df_cond["condition_name"].dropna().unique()):
    count = (df_cond["condition_name"] == name).sum()
    print(f"  {count:4d}x  {name}")

print(f"\n\n{'='*80}")
print("OBSERVATION NODE ANALYSIS")
print(f"{'='*80}")
print(f"Shape: {df_obs.shape}")
print(f"\nColumns: {list(df_obs.columns)}")

print(f"\n\nAll unique observations ({df_obs['observation_name'].nunique()} total):")
print("─" * 80)
for name in sorted(df_obs["observation_name"].dropna().unique()):
    count = (df_obs["observation_name"] == name).sum()
    print(f"  {count:4d}x  {name}")

# Save for reference
with open("exploration/available_conditions.txt", "w") as f:
    f.write("ALL AVAILABLE CONDITIONS IN MIDRC\n")
    f.write("=" * 80 + "\n\n")
    for name in sorted(df_cond["condition_name"].dropna().unique()):
        count = (df_cond["condition_name"] == name).sum()
        f.write(f"{count:4d}x  {name}\n")

with open("exploration/available_observations.txt", "w") as f:
    f.write("ALL AVAILABLE OBSERVATIONS IN MIDRC\n")
    f.write("=" * 80 + "\n\n")
    for name in sorted(df_obs["observation_name"].dropna().unique()):
        count = (df_obs["observation_name"] == name).sum()
        f.write(f"{count:4d}x  {name}\n")

print("\n✓ Full lists saved to:")
print("  • exploration/available_conditions.txt")
print("  • exploration/available_observations.txt")
