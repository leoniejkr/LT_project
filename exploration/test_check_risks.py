import pandas as pd
import io, json
from collections import Counter
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api  = "https://data.midrc.org"
auth = Gen3Auth(api, refresh_file="credentials.json")
sub  = Gen3Submission(api, auth)
# ----------------------------
# Load relevant nodes
# ----------------------------
obs_raw   = sub.export_node("Open", "A1", "observation", "tsv")
proc_raw  = sub.export_node("Open", "A1", "procedure", "tsv")
visit_raw = sub.export_node("Open", "A1", "visit", "tsv")
annot_raw = sub.export_node("Open", "A1", "annotation", "tsv")

df_obs   = pd.read_csv(io.StringIO(obs_raw), sep="\t", low_memory=False)
df_proc  = pd.read_csv(io.StringIO(proc_raw), sep="\t", low_memory=False)
df_visit = pd.read_csv(io.StringIO(visit_raw), sep="\t", low_memory=False)
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)

# ----------------------------
# helper: clean case id
# ----------------------------
def clean_case_id(s):
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

# ----------------------------
# STANDARDIZE OBSERVATION
# ----------------------------
if "case_ids" in df_obs.columns:
    df_obs["case_id"] = df_obs["case_ids"].apply(clean_case_id)

df_obs_clean = pd.DataFrame({
    "case_id": df_obs.get("case_id"),
    "node": "observation",
    "signal": df_obs.get("observation_name"),
    "value": df_obs.get("observation_answer")
})

# ----------------------------
# STANDARDIZE PROCEDURE
# ----------------------------
if "case_ids" in df_proc.columns:
    df_proc["case_id"] = df_proc["case_ids"].apply(clean_case_id)

df_proc_clean = pd.DataFrame({
    "case_id": df_proc.get("case_id"),
    "node": "procedure",
    "signal": df_proc.get("procedure_name"),
    "value": df_proc.get("procedure_description") if "procedure_description" in df_proc.columns else None
})

# ----------------------------
# STANDARDIZE VISIT
# ----------------------------
if "case_ids" in df_visit.columns:
    df_visit["case_id"] = df_visit["case_ids"].apply(clean_case_id)

df_visit_clean = pd.DataFrame({
    "case_id": df_visit.get("case_id"),
    "node": "visit",
    "signal": "visit_type",
    "value": df_visit.get("visit_type") if "visit_type" in df_visit.columns else None
})

# ----------------------------
# STANDARDIZE ANNOTATION (important for risk)
# ----------------------------
if "case_ids" in df_annot.columns:
    df_annot["case_id"] = df_annot["case_ids"].apply(clean_case_id)

df_annot_clean = pd.DataFrame({
    "case_id": df_annot.get("case_id"),
    "node": "annotation",
    "signal": "mRALE / severity",
    "value": df_annot.get("midrc_mRALE_score")
})

# ----------------------------
# MERGE ALL
# ----------------------------
df_risk = pd.concat([
    df_obs_clean,
    df_proc_clean,
    df_visit_clean,
    df_annot_clean
], ignore_index=True)

# ----------------------------
# CLEAN UP
# ----------------------------
df_risk = df_risk.dropna(subset=["case_id"])

# ----------------------------
# EXPORT
# ----------------------------
df_risk.to_csv("data/risk_exploration.csv", index=False)

print("✓ Saved: risk_exploration.csv")
print(df_risk.head(20))