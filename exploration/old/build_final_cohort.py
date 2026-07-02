"""
MIDRC Multi-Modal Dataset Builder
==================================
Builds a cohort for a dual-head classifier:
  • Disease Head  — multi-label pathology classification (CT + CXR)
  • Risk Head     — severity / outcome regression + risk factor labels

Modalities:
  • CT  chest series  (ct_series_file node)
  • CXR chest series  (cr_series_file node)   

Outputs (in ./data/):
  cohort_ct.csv          — CT cohort with all labels
  cohort_cxr.csv         — CXR cohort with all labels
  manifest_ct.json       — Gen3 download manifest (CT)
  manifest_cxr.json      — Gen3 download manifest (CXR)
  label_map.json         — label definitions
"""

import io, json, os
import pandas as pd
import numpy as np
from collections import Counter
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

# ──────────────────────────────────────────────────────────────────────────────
# 0.  AUTH
# ──────────────────────────────────────────────────────────────────────────────
API  = "https://data.midrc.org"
auth = Gen3Auth(API, refresh_file="credentials.json")
sub  = Gen3Submission(API, auth)

os.makedirs("data", exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# 1.  RAW NODE EXPORT
# ──────────────────────────────────────────────────────────────────────────────
print("── Exporting nodes from Gen3 ──")
cases_raw = sub.export_node("Open", "A1", "case",           "tsv")
ct_raw    = sub.export_node("Open", "A1", "ct_series_file", "tsv")
cr_raw    = sub.export_node("Open", "A1", "cr_series_file", "tsv")   # CXR
study_raw = sub.export_node("Open", "A1", "imaging_study",  "tsv")
cond_raw  = sub.export_node("Open", "A1", "condition",      "tsv")
annot_raw = sub.export_node("Open", "A1", "annotation",     "tsv")
obs_raw   = sub.export_node("Open", "A1", "observation",    "tsv")
proc_raw  = sub.export_node("Open", "A1", "procedure",      "tsv")
visit_raw = sub.export_node("Open", "A1", "visit",          "tsv")

df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")
df_ct    = pd.read_csv(io.StringIO(ct_raw),    sep="\t", low_memory=False)
df_cr    = pd.read_csv(io.StringIO(cr_raw),    sep="\t", low_memory=False)
df_study = pd.read_csv(io.StringIO(study_raw), sep="\t", low_memory=False)
df_cond  = pd.read_csv(io.StringIO(cond_raw),  sep="\t")
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)
df_obs   = pd.read_csv(io.StringIO(obs_raw),   sep="\t", low_memory=False)
df_proc  = pd.read_csv(io.StringIO(proc_raw),  sep="\t", low_memory=False)
df_visit = pd.read_csv(io.StringIO(visit_raw), sep="\t", low_memory=False)

print(f"  cases:   {len(df_cases):>6}")
print(f"  ct:      {len(df_ct):>6}")
print(f"  cr:      {len(df_cr):>6}")
print(f"  studies: {len(df_study):>6}")
print(f"  cond:    {len(df_cond):>6}")
print(f"  annot:   {len(df_annot):>6}")

# ──────────────────────────────────────────────────────────────────────────────
# 2.  HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def clean_case_id(s):
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()


# ──────────────────────────────────────────────────────────────────────────────
# 3.  LOINC FILTER — keep only chest-region studies
# ──────────────────────────────────────────────────────────────────────────────

# CT chest LOINC descriptions
CT_CHEST_LOINC = {
    "CT Chest WO contrast",
    "CT Chest W contrast IV",
    "CTA Pulmonary arteries for pulmonary embolus W contrast IV",
    "CTA Chest vessels W contrast IV",
    "CT Chest and Abdomen and Pelvis W contrast IV",
    "CT Chest and Abdomen and Pelvis WO contrast",
    "CTA Chest vessels WO and W contrast IV",
    "CT Chest and Abdomen W contrast IV",
}

# CXR (conventional radiograph) chest LOINC descriptions
# CR node in MIDRC covers PA, AP, lateral views
CXR_CHEST_LOINC = {
    "XR Chest AP",
    "XR Chest PA",
    "XR Chest AP and Lateral",
    "XR Chest PA and Lateral",
    "XR Chest Lateral",
    "XR Chest AP portable",
    "XR Chest 2 views",
    "XR Chest AP and AP lateral-decubitus",
    "Portable XR Chest AP",
    "XR Chest",
}

df_study["case_ids_clean"] = df_study["case_ids"].apply(clean_case_id)

# Map: case_id → set of study LOINC names (so we can filter series)
ct_chest_cases  = set(df_study[df_study["loinc_long_common_name"].isin(CT_CHEST_LOINC)]["case_ids_clean"])
cxr_chest_cases = set(df_study[df_study["loinc_long_common_name"].isin(CXR_CHEST_LOINC)]["case_ids_clean"])

# Also build study_id → modality map to join directly on series
# MIDRC imaging_study links to series via submitter_id
study_loinc_map = df_study.set_index("submitter_id")["loinc_long_common_name"].to_dict()

df_ct["case_ids_clean"] = df_ct["case_ids"].apply(clean_case_id)
df_cr["case_ids_clean"] = df_cr["case_ids"].apply(clean_case_id)

# Primary filter: case must have a chest study
df_chest_ct  = df_ct[df_ct["case_ids_clean"].isin(ct_chest_cases)].copy().reset_index(drop=True)
df_chest_cxr = df_cr[df_cr["case_ids_clean"].isin(cxr_chest_cases)].copy().reset_index(drop=True)

# Secondary: if 'loinc_long_common_name' is directly on the series node, use it
for df, loinc_set, tag in [
    (df_chest_ct,  CT_CHEST_LOINC,  "CT"),
    (df_chest_cxr, CXR_CHEST_LOINC, "CXR"),
]:
    if "loinc_long_common_name" in df.columns:
        before = len(df)
        mask = df["loinc_long_common_name"].isin(loinc_set) | df["loinc_long_common_name"].isna()
        df = df[mask].reset_index(drop=True)
        print(f"  {tag} LOINC series-level filter: {before} → {len(df)}")

print(f"\n  CT chest series (after filter):  {len(df_chest_ct)}")
print(f"  CXR chest series (after filter): {len(df_chest_cxr)}")


# ──────────────────────────────────────────────────────────────────────────────
# 4.  DISEASE HEAD — LABEL ENGINEERING
# ──────────────────────────────────────────────────────────────────────────────
#
# Labels are assigned at CASE level (from condition node), then propagated to
# each series for that case.  We deliberately separate imaging-visible labels
# (used for training) from clinical-state labels (kept as metadata only).

CONDITION_LABEL_MAP = {

    # ── COVID ──────────────────────────────────────────────────────────────
    "COVID-19":                                                   "covid",
    "Emergency use of U07.1 | COVID-19":                         "covid",
    "Pneumonia due to coronavirus disease 2019":                  "covid",
    "Post COVID-19 condition, unspecified":                       "covid",
    "SARS-associated coronavirus as the cause of diseases classified elsewhere": "covid",

    # ── Pleural effusion ───────────────────────────────────────────────────
    "Pleural effusion, not elsewhere classified":                 "effusion",
    "Pleural effusion":                                           "effusion",
    "Pleural effusion in other conditions classified elsewhere":  "effusion",
    "Malignant pleural effusion":                                 "effusion",
    "Chylous effusion":                                           "effusion",
    "Unspecified pleural effusion":                               "effusion",
    "Hemothorax":                                                 "effusion",
    "Pyothorax without fistula":                                  "effusion",
    "Pyothorax with fistula":                                     "effusion",
    "Other specified pleural conditions":                         "effusion",
    "Pericardial effusion (noninflammatory)":                     "effusion",

    # ── Pneumonia ──────────────────────────────────────────────────────────
    "Pneumonia, unspecified organism":                            "pneumonia",
    "Pneumonia, unspecified":                                     "pneumonia",
    "Viral pneumonia, unspecified":                               "pneumonia",
    "Other viral pneumonia":                                      "pneumonia",
    "Lobar pneumonia, unspecified organism":                      "pneumonia",
    "Unspecified bacterial pneumonia":                            "pneumonia",
    "Pneumonia due to Pseudomonas":                               "pneumonia",
    "Pneumonia due to Klebsiella pneumoniae":                     "pneumonia",
    "Pneumonia due to Methicillin susceptible Staphylococcus aureus": "pneumonia",
    "Pneumonia due to Methicillin resistant Staphylococcus aureus":   "pneumonia",
    "Pneumonia due to other Gram-negative bacteria":              "pneumonia",
    "Pneumonia due to Escherichia coli":                          "pneumonia",
    "Pneumonia due to Hemophilus influenzae":                     "pneumonia",
    "Pneumonia due to Streptococcus pneumoniae":                  "pneumonia",
    "Pneumonia due to other streptococci":                        "pneumonia",
    "Pneumonia due to other specified bacteria":                  "pneumonia",
    "Pneumonia due to other specified infectious organisms":      "pneumonia",
    "Ventilator associated pneumonia":                            "pneumonia",
    "Pneumonitis due to inhalation of food and vomit":            "pneumonia",
    "Pneumonitis due to inhalation of food or vomitus":           "pneumonia",
    "Other pneumonia, unspecified organism":                      "pneumonia",
    "Pneumonia in diseases classified elsewhere":                 "pneumonia",
    "Hypostatic pneumonia, unspecified organism":                 "pneumonia",
    "Bronchopneumonia, unspecified organism":                     "pneumonia",
    "Respiratory syncytial virus pneumonia":                      "pneumonia",
    "Human metapneumovirus pneumonia":                            "pneumonia",
    "Cryptogenic organizing pneumonia":                           "pneumonia",
    "Hypersensitivity pneumonitis due to unspecified organic dust": "pneumonia",
    "Acute interstitial pneumonitis":                             "pneumonia",
    "Idiopathic non-specific interstitial pneumonitis":           "pneumonia",
    "Respiratory bronchiolitis interstitial lung disease":        "pneumonia",
    "Lymphoid interstitial pneumonia":                            "pneumonia",
    "Pneumonia due to SARS-associated coronavirus":               "pneumonia",

    # ── Fibrosis / ILD ─────────────────────────────────────────────────────
    "Pulmonary fibrosis, unspecified":                            "fibrosis",
    "Other pulmonary fibrosis":                                   "fibrosis",
    "Idiopathic pulmonary fibrosis":                              "fibrosis",
    "Interstitial pulmonary disease, unspecified":                "fibrosis",
    "Other interstitial pulmonary diseases with fibrosis in diseases classified elsewhere": "fibrosis",
    "Other specified interstitial pulmonary diseases":            "fibrosis",
    "Postinflammatory pulmonary fibrosis":                        "fibrosis",
    "Chronic drug-induced interstitial lung disorders":           "fibrosis",
    "Drug-induced interstitial lung disorders, unspecified":      "fibrosis",
    "Interstitial lung disease with progressive fibrotic phenotype in diseases classified elsewhere": "fibrosis",
    "Other interstitial lung diseases of childhood":              "fibrosis",
    "Sarcoidosis of lung":                                        "fibrosis",
    "Sarcoidosis, unspecified":                                   "fibrosis",
    "Sarcoidosis of lung with sarcoidosis of lymph nodes":        "fibrosis",
    "Sarcoidosis of other sites":                                 "fibrosis",
    "Wegener's granulomatosis without renal involvement":         "fibrosis",
    "Wegener's granulomatosis with renal involvement":            "fibrosis",
    "Pulmonary alveolar microlithiasis":                          "fibrosis",
    "Asbestosis":                                                 "fibrosis",
    "Pneumoconiosis due to asbestos and other mineral fibers":    "fibrosis",
    "Unspecified pneumoconiosis":                                 "fibrosis",
    "Pulmonary mycobacterial infection":                          "fibrosis",

    # ── Emphysema ──────────────────────────────────────────────────────────
    "Emphysema, unspecified":                                     "emphysema",
    "Pulmonary emphysema":                                        "emphysema",
    "Centrilobular emphysema":                                    "emphysema",
    "Panlobular emphysema":                                       "emphysema",
    "Other emphysema":                                            "emphysema",
    "Interstitial emphysema":                                     "emphysema",
    "Unilateral pulmonary emphysema [MacLeod's syndrome]":        "emphysema",

    # ── Atelectasis ────────────────────────────────────────────────────────
    "Atelectasis":                                                "atelectasis",
    "Other pulmonary collapse":                                   "atelectasis",
    "Pulmonary collapse":                                         "atelectasis",

    # ── Pneumothorax ───────────────────────────────────────────────────────
    "Pneumothorax, unspecified":                                  "pneumothorax",
    "Other pneumothorax":                                         "pneumothorax",
    "Spontaneous tension pneumothorax":                           "pneumothorax",
    "Primary spontaneous pneumothorax":                           "pneumothorax",
    "Secondary spontaneous pneumothorax":                         "pneumothorax",
    "Postprocedural pneumothorax":                                "pneumothorax",
    "Chronic pneumothorax":                                       "pneumothorax",
    "Other air leak":                                             "pneumothorax",
    "Other pneumothorax and air leak":                            "pneumothorax",
    "Postprocedural air leak":                                    "pneumothorax",

    # ── Pulmonary embolism ─────────────────────────────────────────────────
    "Other pulmonary embolism without acute cor pulmonale":       "pulm_embolism",
    "Other pulmonary embolism with acute cor pulmonale":          "pulm_embolism",
    "Single subsegmental pulmonary embolism without acute cor pulmonale": "pulm_embolism",
    "Multiple subsegmental pulmonary emboli without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery with acute cor pulmonale": "pulm_embolism",
    "Chronic pulmonary embolism":                                 "pulm_embolism",
    "Septic pulmonary embolism without acute cor pulmonale":      "pulm_embolism",
    "Septic pulmonary embolism with acute cor pulmonale":         "pulm_embolism",
    "Other pulmonary embolism and infarction":                    "pulm_embolism",

    # ── ARDS ───────────────────────────────────────────────────────────────
    "Acute respiratory distress syndrome":                        "ards",
    "Acute respiratory distress":                                 "ards",

    # ── Pulmonary oedema ───────────────────────────────────────────────────
    "Chronic pulmonary edema":                                    "pulm_edema",
    "Acute pulmonary edema":                                      "pulm_edema",

    # ── Clinical state labels (NOT used for imaging training)  ────────────
    "Acute respiratory failure with hypoxia":                     "resp_failure",
    "Acute respiratory failure, unspecified":                     "resp_failure",
    "Chronic respiratory failure with hypoxia":                   "resp_failure",
    "Acute and chronic respiratory failure with hypoxia":         "resp_failure",
    "Respiratory failure, unspecified with hypoxia":              "resp_failure",
    "Acute respiratory failure with hypercapnia":                 "resp_failure",
    "Chronic respiratory failure with hypercapnia":               "resp_failure",
    "Acute postprocedural respiratory failure":                   "resp_failure",
    "Acute respiratory failure, unspecified whether with hypoxia or hypercapnia": "resp_failure",
    "Respiratory failure, unspecified, unspecified whether with hypoxia or hypercapnia": "resp_failure",
    "Acute respiratory failure":                                  "resp_failure",
}

# Ordered unique label names
LABEL_COLS      = list(dict.fromkeys(CONDITION_LABEL_MAP.values()))
IMAGING_LABELS  = [l for l in LABEL_COLS if l != "resp_failure"]   # train targets
CLINICAL_LABELS = ["resp_failure"]                                  # metadata only

print(f"\nDisease labels ({len(LABEL_COLS)}): {LABEL_COLS}")


def build_condition_labels(df_cond_: pd.DataFrame) -> pd.DataFrame:
    """Return one row per case with binary columns for each label."""
    df_ = df_cond_.copy()
    df_["case_ids_clean"] = df_["case_ids"].apply(clean_case_id)
    rows = []
    for case_id, grp in df_.groupby("case_ids_clean"):
        conditions = set(grp["condition_name"].tolist())
        row = {"case_ids_clean": case_id}
        for label in LABEL_COLS:
            row[label] = int(any(CONDITION_LABEL_MAP.get(c) == label for c in conditions))
        rows.append(row)
    return pd.DataFrame(rows)


df_case_labels = build_condition_labels(df_cond)
print(f"\nCase-level label distribution:")
print(df_case_labels[LABEL_COLS].sum().sort_values(ascending=False).to_string())


# ──────────────────────────────────────────────────────────────────────────────
# 5.  RISK HEAD — LABEL / FEATURE ENGINEERING
# ──────────────────────────────────────────────────────────────────────────────
#
# The risk head predicts a structured risk profile, which is later used to
# generate a natural-language narrative via an LLM.
#
# Risk features fall into three tiers:
#   A. Continuous severity scores   → regression targets
#   B. Binary outcome flags         → binary classification targets
#   C. Metadata features            → passed through to the narrative generator
#
# All features are computed at CASE level and merged onto each series row.
#
# ── 5a. mRALE score (continuous imaging severity) ──────────────────────────
#   mRALE = modified Radiological Assessment of Lung Edema score (0-8).
#   Source: annotation node, field midrc_mRALE_score.
#   We keep per-series mRALE (already series-linked) and also compute a
#   per-case max/mean for cases with multiple annotations.

df_annot_ct  = df_annot[df_annot["ct_series_files.submitter_id"].notna()].copy()
df_annot_cxr = df_annot[df_annot["cr_series_files.submitter_id"].notna()].copy()

# Annotation → class labels (COVID pneumonia, airspace disease)
ANNOT_KEEP = ["class_covid19_pneumonia", "airspace_disease_grading", "midrc_mRALE_score"]

df_annot_ct_clean = (
    df_annot_ct[["ct_series_files.submitter_id"] + [c for c in ANNOT_KEEP if c in df_annot_ct.columns]]
    .drop_duplicates("ct_series_files.submitter_id")
    .rename(columns={"ct_series_files.submitter_id": "submitter_id"})
)

df_annot_cxr_clean = (
    df_annot_cxr[["cr_series_files.submitter_id"] + [c for c in ANNOT_KEEP if c in df_annot_cxr.columns]]
    .drop_duplicates("cr_series_files.submitter_id")
    .rename(columns={"cr_series_files.submitter_id": "submitter_id"})
)

# ── 5b. Observation node → structured clinical signals ────────────────────
#
# The observation node contains free-text signal/answer pairs.
# We pivot interesting observations into wide format (one column per signal).
#
# Key signals relevant to risk:
RISK_OBSERVATION_SIGNALS = {
    # Observation name (as in MIDRC)             → canonical column name
    "O2 Flow Rate":                               "o2_flow_rate",
    "Oxygen Saturation":                          "o2_saturation",
    "Smoking Status":                             "smoking_status",
    "BMI":                                        "bmi",
    "Pack Years":                                 "pack_years",
    "SOFA Score":                                 "sofa_score",
    "NEWS2 Score":                                "news2_score",
    "Days Hospitalized":                          "days_hospitalized",
    "Days in ICU":                                "days_icu",
    "Days on Ventilator":                         "days_ventilator",
}

df_obs["case_ids_clean"] = df_obs["case_ids"].apply(clean_case_id)

# Pivot: one row per case_id, one column per risk signal
obs_subset = df_obs[
    df_obs["observation_name"].isin(RISK_OBSERVATION_SIGNALS)
][["case_ids_clean", "observation_name", "observation_answer"]].copy()

obs_subset["col"] = obs_subset["observation_name"].map(RISK_OBSERVATION_SIGNALS)

# Take first non-null value per (case, signal)
obs_pivot = (
    obs_subset.dropna(subset=["observation_answer"])
    .drop_duplicates(["case_ids_clean", "col"])
    .pivot(index="case_ids_clean", columns="col", values="observation_answer")
    .reset_index()
)
obs_pivot.columns.name = None

print(f"\nObservation pivot: {len(obs_pivot)} cases × {obs_pivot.shape[1]-1} signals")
print(f"  Signals found: {[c for c in obs_pivot.columns if c != 'case_ids_clean']}")

# ── 5c. Procedure node → treatment flags ─────────────────────────────────
RISK_PROCEDURES = {
    "Mechanical Ventilation":           "proc_mechanical_ventilation",
    "Non-invasive Ventilation":         "proc_niv",
    "High Flow Nasal Cannula":          "proc_hfnc",
    "Intubation":                       "proc_intubation",
    "ECMO":                             "proc_ecmo",
    "Vasopressor":                      "proc_vasopressor",
    "Prone Positioning":                "proc_prone",
    "Renal Replacement Therapy":        "proc_rrt",
    "Tocilizumab":                      "proc_tocilizumab",
    "Remdesivir":                       "proc_remdesivir",
    "Dexamethasone":                    "proc_dexamethasone",
    "Anticoagulation":                  "proc_anticoagulation",
}

df_proc["case_ids_clean"] = df_proc["case_ids"].apply(clean_case_id)

proc_subset = df_proc[
    df_proc["procedure_name"].isin(RISK_PROCEDURES)
][["case_ids_clean", "procedure_name"]].copy()

# Binary flag: did this case ever receive this procedure?
for proc_name, col_name in RISK_PROCEDURES.items():
    cases_with_proc = set(
        proc_subset[proc_subset["procedure_name"] == proc_name]["case_ids_clean"]
    )
    # We'll merge this in per-case later

# Build wide proc table
proc_rows = []
for case_id, grp in proc_subset.groupby("case_ids_clean"):
    row = {"case_ids_clean": case_id}
    procs_for_case = set(grp["procedure_name"].tolist())
    for proc_name, col_name in RISK_PROCEDURES.items():
        row[col_name] = int(proc_name in procs_for_case)
    proc_rows.append(row)

df_proc_wide = pd.DataFrame(proc_rows) if proc_rows else pd.DataFrame(
    columns=["case_ids_clean"] + list(RISK_PROCEDURES.values())
)
print(f"\nProcedure wide table: {len(df_proc_wide)} cases")

# ── 5d. Visit node → ICU / hospitalisation details ───────────────────────
df_visit["case_ids_clean"] = df_visit["case_ids"].apply(clean_case_id)

visit_agg_cols = {}
for col in ["days_to_hospital_admission", "days_to_hospital_discharge",
            "days_to_icu_admission", "days_to_icu_discharge",
            "icu_type", "visit_type"]:
    if col in df_visit.columns:
        visit_agg_cols[col] = col

df_visit_agg = (
    df_visit[["case_ids_clean"] + list(visit_agg_cols.keys())]
    .drop_duplicates("case_ids_clean")
    .rename(columns={c: f"visit_{c}" for c in visit_agg_cols if c not in ["case_ids_clean"]})
    .rename(columns={"case_ids_clean": "case_ids_clean"})   # keep key intact
)

# Compute length-of-stay from admission/discharge days if available
for prefix, adm, dis in [
    ("hosp",  "visit_days_to_hospital_admission", "visit_days_to_hospital_discharge"),
    ("icu",   "visit_days_to_icu_admission",       "visit_days_to_icu_discharge"),
]:
    if adm in df_visit_agg.columns and dis in df_visit_agg.columns:
        df_visit_agg[f"los_{prefix}_days"] = (
            pd.to_numeric(df_visit_agg[dis], errors="coerce") -
            pd.to_numeric(df_visit_agg[adm], errors="coerce")
        ).clip(lower=0)

print(f"Visit agg: {len(df_visit_agg)} cases")


# ── 5e. Composite risk score & tier labels ───────────────────────────────
#
# We derive a simple ordinal RISK_TIER label for the risk head to predict:
#
#   0  mild      — no ICU, no ventilator, no resp_failure
#   1  moderate  — ICU OR resp_failure, but no ventilator
#   2  severe    — mechanical ventilation OR ECMO OR prone positioning
#
# This gives the model an ordinal regression target that summarises outcome
# severity.  It is computed *before* sampling so all cases get a tier.

def compute_risk_tier(row) -> int:
    """Ordinal severity tier from case-level flags."""
    icu    = str(row.get("icu_indicator",        "")).lower() == "yes"
    vent   = str(row.get("ventilator_indicator", "")).lower() == "yes"
    
    # Handle resp_failure safely (coerce NaN to 0)
    rf_val = row.get("resp_failure", 0)
    rf = (int(rf_val) == 1) if not pd.isna(rf_val) else False

    # Check procedure flags if available (will be NaN if proc table is empty)
    # Safe handling of NaN values
    mv_val = row.get("proc_mechanical_ventilation", 0)
    mv = (int(mv_val) == 1) if not pd.isna(mv_val) else False
    
    ecmo_val = row.get("proc_ecmo", 0)
    ecmo = (int(ecmo_val) == 1) if not pd.isna(ecmo_val) else False
    
    prone_val = row.get("proc_prone", 0)
    prone = (int(prone_val) == 1) if not pd.isna(prone_val) else False

    if vent or mv or ecmo or prone:
        return 2
    if icu or rf:
        return 1
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# 6.  CASE TABLE — merge demographics + disease labels + risk features
# ──────────────────────────────────────────────────────────────────────────────
DEMO_COLS = ["submitter_id", "covid19_positive", "sex", "age_at_index",
             "race", "icu_indicator", "ventilator_indicator"]

df_cases_unique = df_cases.drop_duplicates("submitter_id")[DEMO_COLS]

df_case_all = (
    df_cases_unique
    .merge(df_case_labels,  left_on="submitter_id", right_on="case_ids_clean", how="left")
    .merge(obs_pivot,       left_on="submitter_id", right_on="case_ids_clean", how="left", suffixes=("","_obs"))
    .merge(df_proc_wide,    left_on="submitter_id", right_on="case_ids_clean", how="left", suffixes=("","_proc"))
    .merge(df_visit_agg,    left_on="submitter_id", right_on="case_ids_clean", how="left", suffixes=("","_visit"))
)

# Fill missing label columns
for col in LABEL_COLS:
    if col in df_case_all.columns:
        df_case_all[col] = df_case_all[col].fillna(0).astype(int)

# Reinforce covid from case-level flag
df_case_all["covid"] = (
    (df_case_all.get("covid", pd.Series(0, index=df_case_all.index)) == 1) |
    (df_case_all["covid19_positive"].fillna("").str.lower() == "yes")
).astype(int)

# Compute risk tier
df_case_all["risk_tier"] = df_case_all.apply(compute_risk_tier, axis=1)

print(f"\n=== Risk tier distribution (all cases) ===")
print(df_case_all["risk_tier"].value_counts().sort_index().rename({0:"mild",1:"moderate",2:"severe"}))


# ──────────────────────────────────────────────────────────────────────────────
# 7.  SERIES-LEVEL MERGE (CT + CXR separately)
# ──────────────────────────────────────────────────────────────────────────────

def build_series_df(df_series: pd.DataFrame,
                    df_annot_clean: pd.DataFrame,
                    modality: str) -> pd.DataFrame:
    """Merge case-level labels + series-level annotations onto a series table."""
    df = df_series.copy()
    df = df.merge(df_case_all, left_on="case_ids_clean", right_on="submitter_id",
                  how="left", suffixes=("_series", ""))

    # Merge series-level annotation (mRALE etc.)
    if len(df_annot_clean) > 0:
        df = df.merge(df_annot_clean, on="submitter_id", how="left")

    # Fill labels
    for col in LABEL_COLS:
        df[col] = df[col].fillna(0).astype(int)

    # Normal = no imaging label set
    df["normal"] = (df[IMAGING_LABELS].sum(axis=1) == 0).astype(int)

    # Modality tag (useful when creating a combined dataset later)
    df["modality"] = modality

    # mRALE numeric
    if "midrc_mRALE_score" in df.columns:
        df["mrale_score"] = pd.to_numeric(df["midrc_mRALE_score"], errors="coerce")
    else:
        df["mrale_score"] = np.nan

    # Airspace severity numeric encoding (if present)
    AIRSPACE_MAP = {
        "No airspace disease":     0,
        "Mild airspace disease":   1,
        "Moderate airspace disease": 2,
        "Severe airspace disease": 3,
    }
    if "airspace_disease_grading" in df.columns:
        df["airspace_severity"] = df["airspace_disease_grading"].map(AIRSPACE_MAP)
    else:
        df["airspace_severity"] = np.nan

    return df


df_ct_merged  = build_series_df(df_chest_ct,  df_annot_ct_clean,  "CT")
df_cxr_merged = build_series_df(df_chest_cxr, df_annot_cxr_clean, "CXR")

print(f"\n  CT  merged series:  {len(df_ct_merged)}")
print(f"  CXR merged series:  {len(df_cxr_merged)}")


# ──────────────────────────────────────────────────────────────────────────────
# 8.  BALANCED SAMPLING
# ──────────────────────────────────────────────────────────────────────────────

TIER_N = {
    "covid":         200,
    "pneumonia":     200,
    "effusion":      200,
    "atelectasis":   175,
    "fibrosis":      175,
    "pulm_embolism": 150,
    "emphysema":     100,
    "pneumothorax":  150,
    "pulm_edema":    100,
    "ards":          100,
    "normal":        200,
}

# For CXR, PE is much less visible (no CTA) — lower the cap
TIER_N_CXR = {**TIER_N, "pulm_embolism": 50}


def balanced_sample(df: pd.DataFrame,
                    tier_n: dict,
                    id_col: str = "object_id",
                    random_state: int = 42) -> pd.DataFrame:
    """
    Sample per label, then add normal cases, deduplicate on series id.
    Returns balanced cohort.
    """
    df_unique = df.drop_duplicates(id_col).copy().reset_index(drop=True)
    frames = []
    print(f"\n  Sampling (pool size: {len(df_unique)}):")

    for label in IMAGING_LABELS:
        if label not in df_unique.columns:
            continue
        pool = df_unique[df_unique[label] == 1]
        n = min(tier_n.get(label, 150), len(pool))
        if n > 0:
            frames.append(pool.sample(n=n, random_state=random_state))
            print(f"    {label:<22}: {n:>3}  (pool {len(pool)})")
        else:
            print(f"    {label:<22}: NO SAMPLES in pool")

    normal_pool = df_unique[df_unique["normal"] == 1]
    n_normal = min(tier_n.get("normal", 200), len(normal_pool))
    if n_normal > 0:
        frames.append(normal_pool.sample(n=n_normal, random_state=random_state))
        print(f"    {'normal':<22}: {n_normal:>3}  (pool {len(normal_pool)})")

    if not frames:
        return pd.DataFrame()

    cohort = pd.concat(frames).drop_duplicates(id_col).reset_index(drop=True)
    cohort["n_labels"] = cohort[IMAGING_LABELS].sum(axis=1)
    return cohort


print("\n─── CT cohort ───")
df_cohort_ct  = balanced_sample(df_ct_merged,  TIER_N,     id_col="object_id")

print("\n─── CXR cohort ───")
df_cohort_cxr = balanced_sample(df_cxr_merged, TIER_N_CXR, id_col="object_id")


# ──────────────────────────────────────────────────────────────────────────────
# 9.  DIAGNOSTICS
# ──────────────────────────────────────────────────────────────────────────────
ALL_LABEL_COLS = IMAGING_LABELS + CLINICAL_LABELS + ["normal"]

def print_cohort_stats(df: pd.DataFrame, name: str):
    print(f"\n{'='*60}")
    print(f"  {name}  —  {len(df)} series")
    print(f"{'='*60}")

    print("\n  Disease label distribution:")
    for col in ALL_LABEL_COLS:
        if col in df.columns:
            cnt = int(df[col].sum())
            pct = 100 * cnt / max(len(df), 1)
            print(f"    {col:<24}: {cnt:4d}  ({pct:5.1f}%)")

    print("\n  Risk tier distribution:")
    if "risk_tier" in df.columns:
        tier_labels = {0: "mild", 1: "moderate", 2: "severe"}
        print(df["risk_tier"].map(tier_labels).value_counts().to_string())

    if "mrale_score" in df.columns and df["mrale_score"].notna().any():
        s = df["mrale_score"].dropna()
        print(f"\n  mRALE score  — mean: {s.mean():.2f}  std: {s.std():.2f}"
              f"  min: {s.min():.0f}  max: {s.max():.0f}  (n={len(s)})")

    print("\n  Top 10 label combos:")
    combos = df[IMAGING_LABELS].apply(
        lambda x: tuple(c for c in IMAGING_LABELS if c in df.columns and x.get(c, 0) == 1), axis=1
    )
    for combo, cnt in Counter(combos).most_common(10):
        label = combo if combo else ("normal",)
        print(f"    {label}: {cnt}")


print_cohort_stats(df_cohort_ct,  "CT  cohort")
print_cohort_stats(df_cohort_cxr, "CXR cohort")


# ──────────────────────────────────────────────────────────────────────────────
# 10.  EXPORT
# ──────────────────────────────────────────────────────────────────────────────

def make_manifest(df: pd.DataFrame) -> list:
    return [{"object_id": oid} for oid in df["object_id"].dropna()]


# CT
df_cohort_ct.to_csv("data/cohort_ct.csv", index=False)
with open("data/manifest_ct.json", "w") as f:
    json.dump(make_manifest(df_cohort_ct), f, indent=2)

# CXR
df_cohort_cxr.to_csv("data/cohort_cxr.csv", index=False)
with open("data/manifest_cxr.json", "w") as f:
    json.dump(make_manifest(df_cohort_cxr), f, indent=2)

# Label map
label_map_export = {
    "condition_label_map":  CONDITION_LABEL_MAP,
    "label_cols":           LABEL_COLS,
    "imaging_labels":       IMAGING_LABELS,
    "clinical_labels":      CLINICAL_LABELS,
    "all_label_cols":       ALL_LABEL_COLS,
    "risk_observation_signals": RISK_OBSERVATION_SIGNALS,
    "risk_procedures":      RISK_PROCEDURES,
    "risk_tier": {
        "0": "mild    — no ICU, no ventilator, no resp_failure",
        "1": "moderate — ICU OR resp_failure",
        "2": "severe  — mechanical ventilation / ECMO / prone",
    },
}
with open("data/label_map.json", "w") as f:
    json.dump(label_map_export, f, indent=2)

print(f"\n✓ data/cohort_ct.csv          ({len(df_cohort_ct)} series)")
print(f"✓ data/cohort_cxr.csv         ({len(df_cohort_cxr)} series)")
print(f"✓ data/manifest_ct.json       ({len(make_manifest(df_cohort_ct))} entries)")
print(f"✓ data/manifest_cxr.json      ({len(make_manifest(df_cohort_cxr))} entries)")
print(f"✓ data/label_map.json")


# ──────────────────────────────────────────────────────────────────────────────
# APPENDIX — COLUMN REFERENCE
# ──────────────────────────────────────────────────────────────────────────────
#
# Disease head targets (binary, multi-label):
#   covid, pneumonia, effusion, fibrosis, emphysema, atelectasis,
#   pneumothorax, pulm_embolism, ards, pulm_edema
#   → plus "normal" (no imaging label)
#   → "resp_failure" kept as metadata, NOT a training target
#
# Risk head targets:
#   risk_tier          int  {0,1,2}  ordinal severity class
#   mrale_score        float 0-8     imaging severity (from annotation node)
#   airspace_severity  int  {0,1,2,3} encoded from airspace_disease_grading
#
# Risk metadata features (for narrative generation):
#   age_at_index, sex, race
#   covid19_positive
#   icu_indicator, ventilator_indicator         (from case node)
#   o2_flow_rate, o2_saturation, bmi,           (from observation node)
#     smoking_status, pack_years,
#     sofa_score, news2_score,
#     days_hospitalized, days_icu, days_ventilator
#   proc_mechanical_ventilation, proc_niv,      (from procedure node)
#     proc_hfnc, proc_intubation, proc_ecmo,
#     proc_vasopressor, proc_prone, proc_rrt,
#     proc_tocilizumab, proc_remdesivir,
#     proc_dexamethasone, proc_anticoagulation
#   los_hosp_days, los_icu_days                 (derived from visit node)
#   class_covid19_pneumonia                     (from annotation node)
#
# Modality tag:
#   modality   str   "CT" | "CXR"