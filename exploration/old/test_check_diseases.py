import pandas as pd
import io, json
from collections import Counter
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api  = "https://data.midrc.org"
auth = Gen3Auth(api, refresh_file="credentials.json")
sub  = Gen3Submission(api, auth)

# ── Daten laden ────────────────────────────────────────────────
cases_raw = sub.export_node("Open", "A1", "case",           "tsv")
ct_raw    = sub.export_node("Open", "A1", "ct_series_file", "tsv")
study_raw = sub.export_node("Open", "A1", "imaging_study",  "tsv")
cond_raw  = sub.export_node("Open", "A1", "condition",      "tsv")
annot_raw = sub.export_node("Open", "A1", "annotation",     "tsv")

df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")
df_ct    = pd.read_csv(io.StringIO(ct_raw),    sep="\t", low_memory=False)
df_study = pd.read_csv(io.StringIO(study_raw), sep="\t", low_memory=False)
df_cond  = pd.read_csv(io.StringIO(cond_raw),  sep="\t")
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)

# Add this to your existing pipeline after building df_cond
print("\n=== All condition_name values with counts ===")
print(
    df_cond["condition_name"]
    .value_counts()
    .reset_index()
    .rename(columns={"index":"condition","condition_name":"count"})
    .to_string(index=False)
)

df_cond["condition_name"].value_counts().reset_index().rename(columns={"index":"condition","condition_name":"count"}).to_csv("data/condition_counts.csv", index=False)
print("✓ saved to data/condition_counts.csv")