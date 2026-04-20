import pandas as pd
import json
import io
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api = "https://data.midrc.org"
cred = "credentials.json"
auth = Gen3Auth(api, refresh_file=cred)
sub  = Gen3Submission(api, auth)

# ------------------------------------------------------------------ #
# Daten neu laden 
# ------------------------------------------------------------------ #
print("Lade Cases...")
cases_raw = sub.export_node("Open", "A1", "case", "tsv")
df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")

print("Lade CT Serien...")
ct_raw = sub.export_node("Open", "A1", "ct_series_file", "tsv")
df_ct = pd.read_csv(io.StringIO(ct_raw), sep="\t", low_memory=False)

# ------------------------------------------------------------------ #
# MERGE
# ------------------------------------------------------------------ #
df_ct["case_ids_clean"] = df_ct["case_ids"].str.strip("[]'").str.replace("'", "")

df_ct_merged = df_ct.merge(
    df_cases[["submitter_id", "covid19_positive", "sex", 
              "age_at_index", "race", "icu_indicator", "ventilator_indicator"]],
    left_on="case_ids_clean",
    right_on="submitter_id",
    how="left"
)

print(f"\nCT mit Metadata: {len(df_ct_merged)}")
print(df_ct_merged["covid19_positive"].value_counts())



# Nur Chest CTs
df_cohort = df_ct_merged[
    df_ct_merged["series_description"].str.contains(
        "chest|thorax|lung|thor", case=False, na=False)
]

print(f"\nKohorte (Chest CT, COVID+): {len(df_cohort)}")
print(df_cohort["series_description"].value_counts().head(20))

# ------------------------------------------------------------------ #
# MANIFEST + CSV speichern
# ------------------------------------------------------------------ #
object_ids = df_cohort["object_id"].dropna().tolist()
manifest = [{"object_id": oid} for oid in object_ids]

with open("data/manifest_chest_ct_covid.json", "w") as f:
    json.dump(manifest, f, indent=2)

df_cohort.to_csv("data/cohort_metadata.csv", index=False)

print(f"\n✓ Manifest: {len(manifest)} Serien → manifest.json")
print("✓ Metadata  → cohort_metadata.csv")