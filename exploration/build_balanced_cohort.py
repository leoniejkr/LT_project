import pandas as pd
import json
import io
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api = "https://data.midrc.org"
cred = "credentials.json"
auth = Gen3Auth(api, refresh_file=cred)
sub  = Gen3Submission(api, auth)

# Daten laden
print("Lade Cases + CT...")
cases_raw = sub.export_node("Open", "A1", "case", "tsv")
df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")

ct_raw = sub.export_node("Open", "A1", "ct_series_file", "tsv")
df_ct = pd.read_csv(io.StringIO(ct_raw), sep="\t", low_memory=False)

# Merge
df_ct["case_ids_clean"] = df_ct["case_ids"].str.strip("[]'").str.replace("'", "")
df_merged = df_ct.merge(
    df_cases[["submitter_id", "covid19_positive", "sex", 
              "age_at_index", "race", "icu_indicator", "ventilator_indicator"]],
    left_on="case_ids_clean",
    right_on="submitter_id",
    how="left"
)

# Nur Chest CTs
df_chest = df_merged[
    df_merged["series_description"].str.contains(
        "chest|thorax|lung|thor", case=False, na=False)
]

# ------------------------------------------------------------------ #
# BALANCIERTE KOHORTE: je 500 COVID+ und COVID-
# (klein genug zum Testen, groß genug zum Trainieren)
# ------------------------------------------------------------------ #
N = 500  # pro Klasse – kannst du später erhöhen

df_pos = df_chest[df_chest["covid19_positive"] == "Yes"].sample(n=N, random_state=42)
df_neg = df_chest[df_chest["covid19_positive"] == "No"].sample(n=N, random_state=42)

df_cohort = pd.concat([df_pos, df_neg]).reset_index(drop=True)

print(f"\nKohorte: {len(df_cohort)} Serien")
print(df_cohort["covid19_positive"].value_counts())
print(f"Geschätzte Größe: {df_cohort['file_size'].sum() / 1e9:.1f} GB")

# Manifest + CSV
manifest = [{"object_id": oid} for oid in df_cohort["object_id"].dropna()]
with open("data/manifest_balanced.json", "w") as f:
    json.dump(manifest, f, indent=2)

df_cohort.to_csv("data/cohort_balanced.csv", index=False)
print(f"\n✓ {len(manifest)} Serien → manifest_balanced.json")
print("✓ cohort_balanced.csv gespeichert")