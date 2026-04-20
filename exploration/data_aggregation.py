import pandas as pd
import json
import os
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from gen3.query import Gen3Query

api = "https://data.midrc.org"
cred = "credentials.json"
auth = Gen3Auth(api, refresh_file=cred)
sub  = Gen3Submission(api, auth)
query = Gen3Query(auth)

# ------------------------------------------------------------------ #
# 1. Case-Metadata laden (demografisch + COVID-Status)
# ------------------------------------------------------------------ #
cases_raw = sub.export_node("Open", "A1", "case", "tsv")
df_cases = pd.read_csv(pd.io.common.StringIO(cases_raw), sep="\t")

# Nur COVID-positive Fälle
df_covid_pos = df_cases[df_cases["covid19_positive"] == "Yes"]
df_covid_neg = df_cases[df_cases["covid19_positive"] == "No"]
print(f"COVID+: {len(df_covid_pos)}, COVID-: {len(df_covid_neg)}")

# ------------------------------------------------------------------ #
# 2. CT-Serien abfragen
# ------------------------------------------------------------------ #
ct_raw = sub.export_node("Open", "A1", "ct_series_file", "tsv")
df_ct = pd.read_csv(pd.io.common.StringIO(ct_raw), sep="\t")
print(f"\nCT Serien total: {len(df_ct)}")
print(df_ct.columns.tolist())

# ------------------------------------------------------------------ #
# 3. Chest X-Rays abfragen (DX = Digital X-Ray, CR = Computed Radiography)
# ------------------------------------------------------------------ #
try:
    dx_raw = sub.export_node("Open", "A1", "dx_series_file", "tsv")
    df_dx = pd.read_csv(pd.io.common.StringIO(dx_raw), sep="\t")
    print(f"DX Serien: {len(df_dx)}")
except Exception as e:
    print(f"dx_series_file: {e}")

try:
    cr_raw = sub.export_node("Open", "A1", "cr_series_file", "tsv")
    df_cr = pd.read_csv(pd.io.common.StringIO(cr_raw), sep="\t")
    print(f"CR Serien: {len(df_cr)}")
except Exception as e:
    print(f"cr_series_file: {e}")


# ------------------------------------------------------------------ #
# MERGE: Cases + CT Serien via case_ids
# ------------------------------------------------------------------ #

# case_ids in CT ist ein String wie "['case-123']" → bereinigen
df_ct["case_ids_clean"] = df_ct["case_ids"].str.strip("[]'").str.replace("'", "")

# Cases index setzen
df_cases_indexed = df_cases.set_index("submitter_id")

# Merge
df_ct_merged = df_ct.merge(
    df_cases[["submitter_id", "covid19_positive", "sex", "age_at_index", 
              "race", "icu_indicator", "ventilator_indicator"]],
    left_on="case_ids_clean",
    right_on="submitter_id",
    how="left"
)

print(f"CT mit Case-Metadata: {len(df_ct_merged)}")
print(df_ct_merged["covid19_positive"].value_counts())

# ------------------------------------------------------------------ #
# FILTER: Nur Chest CTs von COVID+ Patienten → deine Trainingskohorte
# ------------------------------------------------------------------ #
df_cohort = df_ct_merged[
    (df_ct_merged["covid19_positive"] == "Yes") &
    (df_ct_merged["series_description"].str.contains("chest|thorax|lung|thor", 
                                                       case=False, na=False))
]

print(f"\nKohorte (Chest CT, COVID+): {len(df_cohort)}")
print(df_cohort["series_description"].value_counts().head(20))

# ------------------------------------------------------------------ #
# MANIFEST: object_ids für Download speichern
# ------------------------------------------------------------------ #
object_ids = df_cohort["object_id"].dropna().tolist()

manifest = [{"object_id": oid} for oid in object_ids]
with open("manifest_chest_ct_covid.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"\nManifest gespeichert: {len(manifest)} Serien")

# Übersicht speichern
df_cohort.to_csv("cohort_metadata.csv", index=False)
print("cohort_metadata.csv gespeichert ✓")