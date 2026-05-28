"""
MIDRC Dual-Head Dataset Builder
=================================
Constructs a comprehensive dataset for a dual-head ML model:

  HEAD 1: Disease Classification
    • Multi-label pathology prediction from CT & CXR chest scans
    • Labels: COVID, pneumonia, effusion, fibrosis, emphysema, atelectasis,
              pneumothorax, pulmonary embolism, ARDS, pulmonary edema, normal

  HEAD 2: Risk Assessment  
    • Predicts: risk_tier (ordinal severity: 0=mild, 1=moderate, 2=severe)
    • Predicts: individual risk factors for LLM narrative generation
    • Risk factors: age, BMI, O2 requirements, ventilator status, procedures,
                    length of stay, comorbidities

Outputs (in ./data/):
  cohort_ct.csv            — CT  series with disease & risk labels
  cohort_cxr.csv           — CXR series with disease & risk labels
  manifest_ct.json         — Gen3 download manifest (CT)
  manifest_cxr.json        — Gen3 download manifest (CXR)
  label_map.json           — comprehensive label & feature definitions
  dataset_report.txt       — detailed dataset statistics & diagnostics
"""

import io, json, os, sys
import pandas as pd
import numpy as np
from collections import Counter
from pathlib import Path

try:
    from gen3.auth import Gen3Auth
    from gen3.submission import Gen3Submission
except ImportError:
    print("ERROR: gen3 package not found. Install with: pip install gen3")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# 0. CONFIGURATION & AUTH
# ══════════════════════════════════════════════════════════════════════════════

API = "https://data.midrc.org"
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("MIDRC Dual-Head Dataset Builder")
print("=" * 80)

try:
    auth = Gen3Auth(API, refresh_file="credentials.json")
    sub = Gen3Submission(API, auth)
    print(f"✓ Connected to {API}\n")
except Exception as e:
    print(f"✗ Failed to authenticate: {e}")
    print("  Ensure credentials.json is in the current directory")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATA EXPORT FROM GEN3
# ══════════════════════════════════════════════════════════════════════════════

print("─" * 80)
print("1. Exporting data from Gen3 MIDRC...")
print("─" * 80)

try:
    cases_raw = sub.export_node("Open", "A1", "case",           "tsv")
    ct_raw    = sub.export_node("Open", "A1", "ct_series_file", "tsv")
    cr_raw    = sub.export_node("Open", "A1", "cr_series_file", "tsv")
    study_raw = sub.export_node("Open", "A1", "imaging_study",  "tsv")
    cond_raw  = sub.export_node("Open", "A1", "condition",      "tsv")
    annot_raw = sub.export_node("Open", "A1", "annotation",     "tsv")
    obs_raw   = sub.export_node("Open", "A1", "observation",    "tsv")
    proc_raw  = sub.export_node("Open", "A1", "procedure",      "tsv")
    visit_raw = sub.export_node("Open", "A1", "visit",          "tsv")
except Exception as e:
    print(f"✗ Export failed: {e}")
    sys.exit(1)

df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")
df_ct    = pd.read_csv(io.StringIO(ct_raw),    sep="\t", low_memory=False)
df_cr    = pd.read_csv(io.StringIO(cr_raw),    sep="\t", low_memory=False)
df_study = pd.read_csv(io.StringIO(study_raw), sep="\t", low_memory=False)
df_cond  = pd.read_csv(io.StringIO(cond_raw),  sep="\t")
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)
df_obs   = pd.read_csv(io.StringIO(obs_raw),   sep="\t", low_memory=False)
df_proc  = pd.read_csv(io.StringIO(proc_raw),  sep="\t", low_memory=False)
df_visit = pd.read_csv(io.StringIO(visit_raw), sep="\t", low_memory=False)

print(f"  cases:        {len(df_cases):,}")
print(f"  ct_series:    {len(df_ct):,}")
print(f"  cr_series:    {len(df_cr):,}")
print(f"  imaging_study: {len(df_study):,}")
print(f"  conditions:   {len(df_cond):,}")
print(f"  annotations:  {len(df_annot):,}")
print(f"  observations: {len(df_obs):,}")
print(f"  procedures:   {len(df_proc):,}")
print(f"  visits:       {len(df_visit):,}")


# ══════════════════════════════════════════════════════════════════════════════
# 2. HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def clean_case_id(s):
    """Safely clean case ID strings."""
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

def coerce_float(val):
    """Safely convert to float, return NaN if fails."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return np.nan

def coerce_int(val):
    """Safely convert to int, return 0 if fails."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# 3. LOINC FILTER — Chest region only
# ══════════════════════════════════════════════════════════════════════════════

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
ct_chest_cases  = set(df_study[df_study["loinc_long_common_name"].isin(CT_CHEST_LOINC)]["case_ids_clean"])
cxr_chest_cases = set(df_study[df_study["loinc_long_common_name"].isin(CXR_CHEST_LOINC)]["case_ids_clean"])

df_ct["case_ids_clean"] = df_ct["case_ids"].apply(clean_case_id)
df_cr["case_ids_clean"] = df_cr["case_ids"].apply(clean_case_id)

df_chest_ct  = df_ct[df_ct["case_ids_clean"].isin(ct_chest_cases)].copy().reset_index(drop=True)
df_chest_cxr = df_cr[df_cr["case_ids_clean"].isin(cxr_chest_cases)].copy().reset_index(drop=True)

print(f"\n✓ Chest region filter applied:")
print(f"  CT chest series:  {len(df_chest_ct):,}")
print(f"  CXR chest series: {len(df_chest_cxr):,}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. HEAD 1: DISEASE LABELS — Condition Node Engineering
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("2. Engineering Disease Labels (HEAD 1)")
print("─" * 80)

# Comprehensive ICD-10 to disease label mapping
CONDITION_LABEL_MAP = {
    # ── COVID-19 (all variants) ────────────────────────────────────────────
    "COVID-19": "covid",
    "Emergency use of U07.1 | COVID-19": "covid",
    "Pneumonia due to coronavirus disease 2019": "covid",
    "Post COVID-19 condition, unspecified": "covid",
    "SARS-associated coronavirus as the cause of diseases classified elsewhere": "covid",

    # ── Pleural Effusion (all types) ────────────────────────────────────────
    "Pleural effusion, not elsewhere classified": "effusion",
    "Pleural effusion": "effusion",
    "Pleural effusion in other conditions classified elsewhere": "effusion",
    "Malignant pleural effusion": "effusion",
    "Chylous effusion": "effusion",
    "Unspecified pleural effusion": "effusion",
    "Hemothorax": "effusion",
    "Pyothorax without fistula": "effusion",
    "Pyothorax with fistula": "effusion",
    "Other specified pleural conditions": "effusion",
    "Pericardial effusion (noninflammatory)": "effusion",

    # ── Pneumonia (organism-specific + generic) ────────────────────────────
    "Pneumonia, unspecified organism": "pneumonia",
    "Pneumonia, unspecified": "pneumonia",
    "Viral pneumonia, unspecified": "pneumonia",
    "Other viral pneumonia": "pneumonia",
    "Lobar pneumonia, unspecified organism": "pneumonia",
    "Unspecified bacterial pneumonia": "pneumonia",
    "Pneumonia due to Pseudomonas": "pneumonia",
    "Pneumonia due to Klebsiella pneumoniae": "pneumonia",
    "Pneumonia due to Methicillin susceptible Staphylococcus aureus": "pneumonia",
    "Pneumonia due to Methicillin resistant Staphylococcus aureus": "pneumonia",
    "Pneumonia due to other Gram-negative bacteria": "pneumonia",
    "Pneumonia due to Escherichia coli": "pneumonia",
    "Pneumonia due to Hemophilus influenzae": "pneumonia",
    "Pneumonia due to Streptococcus pneumoniae": "pneumonia",
    "Pneumonia due to other streptococci": "pneumonia",
    "Pneumonia due to other specified bacteria": "pneumonia",
    "Pneumonia due to other specified infectious organisms": "pneumonia",
    "Ventilator associated pneumonia": "pneumonia",
    "Pneumonitis due to inhalation of food and vomit": "pneumonia",
    "Pneumonitis due to inhalation of food or vomitus": "pneumonia",
    "Other pneumonia, unspecified organism": "pneumonia",
    "Pneumonia in diseases classified elsewhere": "pneumonia",
    "Hypostatic pneumonia, unspecified organism": "pneumonia",
    "Bronchopneumonia, unspecified organism": "pneumonia",
    "Respiratory syncytial virus pneumonia": "pneumonia",
    "Human metapneumovirus pneumonia": "pneumonia",
    "Cryptogenic organizing pneumonia": "pneumonia",
    "Hypersensitivity pneumonitis due to unspecified organic dust": "pneumonia",
    "Acute interstitial pneumonitis": "pneumonia",
    "Idiopathic non-specific interstitial pneumonitis": "pneumonia",
    "Respiratory bronchiolitis interstitial lung disease": "pneumonia",
    "Lymphoid interstitial pneumonia": "pneumonia",
    "Pneumonia due to SARS-associated coronavirus": "pneumonia",

    # ── Fibrosis / Interstitial Lung Disease ────────────────────────────────
    "Pulmonary fibrosis, unspecified": "fibrosis",
    "Other pulmonary fibrosis": "fibrosis",
    "Idiopathic pulmonary fibrosis": "fibrosis",
    "Interstitial pulmonary disease, unspecified": "fibrosis",
    "Other interstitial pulmonary diseases with fibrosis in diseases classified elsewhere": "fibrosis",
    "Other specified interstitial pulmonary diseases": "fibrosis",
    "Postinflammatory pulmonary fibrosis": "fibrosis",
    "Chronic drug-induced interstitial lung disorders": "fibrosis",
    "Drug-induced interstitial lung disorders, unspecified": "fibrosis",
    "Interstitial lung disease with progressive fibrotic phenotype in diseases classified elsewhere": "fibrosis",
    "Other interstitial lung diseases of childhood": "fibrosis",
    "Sarcoidosis of lung": "fibrosis",
    "Sarcoidosis, unspecified": "fibrosis",
    "Sarcoidosis of lung with sarcoidosis of lymph nodes": "fibrosis",
    "Sarcoidosis of other sites": "fibrosis",
    "Wegener's granulomatosis without renal involvement": "fibrosis",
    "Wegener's granulomatosis with renal involvement": "fibrosis",
    "Pulmonary alveolar microlithiasis": "fibrosis",
    "Asbestosis": "fibrosis",
    "Pneumoconiosis due to asbestos and other mineral fibers": "fibrosis",
    "Unspecified pneumoconiosis": "fibrosis",
    "Pulmonary mycobacterial infection": "fibrosis",

    # ── Emphysema (all subtypes) ───────────────────────────────────────────
    "Emphysema, unspecified": "emphysema",
    "Pulmonary emphysema": "emphysema",
    "Centrilobular emphysema": "emphysema",
    "Panlobular emphysema": "emphysema",
    "Other emphysema": "emphysema",
    "Interstitial emphysema": "emphysema",
    "Unilateral pulmonary emphysema [MacLeod's syndrome]": "emphysema",

    # ── Atelectasis ────────────────────────────────────────────────────────
    "Atelectasis": "atelectasis",
    "Other pulmonary collapse": "atelectasis",
    "Pulmonary collapse": "atelectasis",

    # ── Pneumothorax ───────────────────────────────────────────────────────
    "Pneumothorax, unspecified": "pneumothorax",
    "Other pneumothorax": "pneumothorax",
    "Spontaneous tension pneumothorax": "pneumothorax",
    "Primary spontaneous pneumothorax": "pneumothorax",
    "Secondary spontaneous pneumothorax": "pneumothorax",
    "Postprocedural pneumothorax": "pneumothorax",
    "Chronic pneumothorax": "pneumothorax",
    "Other air leak": "pneumothorax",
    "Other pneumothorax and air leak": "pneumothorax",
    "Postprocedural air leak": "pneumothorax",

    # ── Pulmonary Embolism ─────────────────────────────────────────────────
    "Other pulmonary embolism without acute cor pulmonale": "pulm_embolism",
    "Other pulmonary embolism with acute cor pulmonale": "pulm_embolism",
    "Single subsegmental pulmonary embolism without acute cor pulmonale": "pulm_embolism",
    "Multiple subsegmental pulmonary emboli without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery with acute cor pulmonale": "pulm_embolism",
    "Chronic pulmonary embolism": "pulm_embolism",
    "Septic pulmonary embolism without acute cor pulmonale": "pulm_embolism",
    "Septic pulmonary embolism with acute cor pulmonale": "pulm_embolism",
    "Other pulmonary embolism and infarction": "pulm_embolism",

    # ── ARDS ───────────────────────────────────────────────────────────────
    "Acute respiratory distress syndrome": "ards",
    "Acute respiratory distress": "ards",

    # ── Pulmonary Edema ────────────────────────────────────────────────────
    "Chronic pulmonary edema": "pulm_edema",
    "Acute pulmonary edema": "pulm_edema",

    # ── Clinical state (metadata, not training targets) ────────────────────
    "Acute respiratory failure with hypoxia": "resp_failure",
    "Acute respiratory failure, unspecified": "resp_failure",
    "Chronic respiratory failure with hypoxia": "resp_failure",
    "Acute and chronic respiratory failure with hypoxia": "resp_failure",
    "Respiratory failure, unspecified with hypoxia": "resp_failure",
    "Acute respiratory failure with hypercapnia": "resp_failure",
    "Chronic respiratory failure with hypercapnia": "resp_failure",
    "Acute postprocedural respiratory failure": "resp_failure",
    "Acute respiratory failure, unspecified whether with hypoxia or hypercapnia": "resp_failure",
    "Respiratory failure, unspecified, unspecified whether with hypoxia or hypercapnia": "resp_failure",
    "Acute respiratory failure": "resp_failure",
}

LABEL_COLS      = list(dict.fromkeys(CONDITION_LABEL_MAP.values()))
IMAGING_LABELS  = [l for l in LABEL_COLS if l != "resp_failure"]
CLINICAL_LABELS = ["resp_failure"]

print(f"\nDisease labels defined ({len(LABEL_COLS)}):")
for i, label in enumerate(LABEL_COLS, 1):
    print(f"  {i:2d}. {label}")


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
print(f"\nDisease label distribution (case-level):")
for label in sorted(LABEL_COLS, key=lambda x: -df_case_labels[x].sum()):
    count = int(df_case_labels[label].sum())
    pct = 100 * count / len(df_case_labels)
    print(f"  {label:<22}: {count:5,} ({pct:5.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# 5. HEAD 2: RISK ASSESSMENT — Feature Engineering
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("3. Engineering Risk Assessment Features (HEAD 2)")
print("─" * 80)

# ── 5a. Series-level annotations: mRALE score, COVID pneumonia classification ──
ANNOT_KEEP = ["class_covid19_pneumonia", "airspace_disease_grading", "midrc_mRALE_score"]

df_annot_ct = df_annot[df_annot["ct_series_files.submitter_id"].notna()].copy()
df_annot_cxr = df_annot[df_annot["cr_series_files.submitter_id"].notna()].copy()

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

print(f"\n✓ Annotations:")
print(f"  CT annotations:  {len(df_annot_ct_clean)}")
print(f"  CXR annotations: {len(df_annot_cxr_clean)}")

# ── 5b. Observation node: vital signs & clinical measurements ─────────────────
RISK_OBSERVATION_SIGNALS = {
    "O2 Flow Rate": "o2_flow_rate",
    "Oxygen Saturation": "o2_saturation",
    "Smoking Status": "smoking_status",
    "BMI": "bmi",
    "Pack Years": "pack_years",
    "SOFA Score": "sofa_score",
    "NEWS2 Score": "news2_score",
    "Days Hospitalized": "days_hospitalized",
    "Days in ICU": "days_icu",
    "Days on Ventilator": "days_ventilator",
    "Heart Rate": "heart_rate",
    "Respiratory Rate": "respiratory_rate",
    "Temperature": "temperature",
    "Systolic Blood Pressure": "sbp",
    "Diastolic Blood Pressure": "dbp",
    "Baseline Creatinine": "creatinine",
}

df_obs["case_ids_clean"] = df_obs["case_ids"].apply(clean_case_id)

obs_subset = df_obs[
    df_obs["observation_name"].isin(RISK_OBSERVATION_SIGNALS)
][["case_ids_clean", "observation_name", "observation_answer"]].copy()

obs_subset["col"] = obs_subset["observation_name"].map(RISK_OBSERVATION_SIGNALS)

obs_pivot = (
    obs_subset.dropna(subset=["observation_answer"])
    .drop_duplicates(["case_ids_clean", "col"])
    .pivot(index="case_ids_clean", columns="col", values="observation_answer")
    .reset_index()
)
obs_pivot.columns.name = None

# Attempt numeric conversion for numeric columns
numeric_cols = ["o2_flow_rate", "o2_saturation", "bmi", "pack_years", "sofa_score", "news2_score",
                "days_hospitalized", "days_icu", "days_ventilator", "heart_rate", "respiratory_rate",
                "temperature", "sbp", "dbp", "creatinine"]
for col in numeric_cols:
    if col in obs_pivot.columns:
        obs_pivot[col] = obs_pivot[col].apply(coerce_float)

print(f"✓ Observations: {len(obs_pivot)} cases with clinical signals")

# ── 5c. Procedure node: treatment flags ────────────────────────────────────────
RISK_PROCEDURES = {
    "Mechanical Ventilation": "proc_mechanical_ventilation",
    "Non-invasive Ventilation": "proc_niv",
    "High Flow Nasal Cannula": "proc_hfnc",
    "Intubation": "proc_intubation",
    "ECMO": "proc_ecmo",
    "Vasopressor": "proc_vasopressor",
    "Prone Positioning": "proc_prone",
    "Renal Replacement Therapy": "proc_rrt",
    "Tocilizumab": "proc_tocilizumab",
    "Remdesivir": "proc_remdesivir",
    "Dexamethasone": "proc_dexamethasone",
    "Anticoagulation": "proc_anticoagulation",
}

df_proc["case_ids_clean"] = df_proc["case_ids"].apply(clean_case_id)

proc_subset = df_proc[
    df_proc["procedure_name"].isin(RISK_PROCEDURES)
][["case_ids_clean", "procedure_name"]].copy()

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

print(f"✓ Procedures: {len(df_proc_wide)} cases with treatment data")

# ── 5d. Visit node: hospitalisation length-of-stay ────────────────────────────
df_visit["case_ids_clean"] = df_visit["case_ids"].apply(clean_case_id)

visit_cols = ["days_to_hospital_admission", "days_to_hospital_discharge",
              "days_to_icu_admission", "days_to_icu_discharge", "icu_type"]
visit_cols_available = [c for c in visit_cols if c in df_visit.columns]

df_visit_agg = (
    df_visit[["case_ids_clean"] + visit_cols_available]
    .drop_duplicates("case_ids_clean")
)

# Compute length-of-stay
if "days_to_hospital_admission" in df_visit_agg.columns and "days_to_hospital_discharge" in df_visit_agg.columns:
    df_visit_agg["los_hospital_days"] = (
        pd.to_numeric(df_visit_agg["days_to_hospital_discharge"], errors="coerce") -
        pd.to_numeric(df_visit_agg["days_to_hospital_admission"], errors="coerce")
    ).clip(lower=0)

if "days_to_icu_admission" in df_visit_agg.columns and "days_to_icu_discharge" in df_visit_agg.columns:
    df_visit_agg["los_icu_days"] = (
        pd.to_numeric(df_visit_agg["days_to_icu_discharge"], errors="coerce") -
        pd.to_numeric(df_visit_agg["days_to_icu_admission"], errors="coerce")
    ).clip(lower=0)

print(f"✓ Visits: {len(df_visit_agg)} cases with hospitalization data")

# ── 5e. Ordinal Risk Tier: Severity classification ──────────────────────────────
def compute_risk_tier(row) -> int:
    """
    Compute severity tier from case-level flags:
      0 = mild      (no ICU, no ventilator, no respiratory failure)
      1 = moderate  (ICU or respiratory failure, but no mechanical ventilation)
      2 = severe    (mechanical ventilation, ECMO, or prone positioning)
    """
    icu = str(row.get("icu_indicator", "")).lower() == "yes"
    vent = str(row.get("ventilator_indicator", "")).lower() == "yes"
    
    rf_val = row.get("resp_failure", 0)
    rf = (int(rf_val) == 1) if not pd.isna(rf_val) else False
    
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


# ── 5f. Individual risk factor flags (for narrative generation) ─────────────────
RISK_FACTORS = {
    # Age-based risk
    "age_elderly": ("age_at_index", lambda x: coerce_int(x) > 65 if not pd.isna(x) else False),
    "age_very_elderly": ("age_at_index", lambda x: coerce_int(x) > 80 if not pd.isna(x) else False),
    
    # BMI-based risk
    "bmi_obese": ("bmi", lambda x: coerce_float(x) > 30 if not pd.isna(x) else False),
    "bmi_high": ("bmi", lambda x: coerce_float(x) > 25 if not pd.isna(x) else False),
    
    # Oxygen requirements
    "high_o2_requirement": ("o2_flow_rate", lambda x: coerce_float(x) > 6 if not pd.isna(x) else False),
    "low_o2_saturation": ("o2_saturation", lambda x: coerce_float(x) < 94 if not pd.isna(x) else False),
    
    # Severity scores
    "high_sofa": ("sofa_score", lambda x: coerce_int(x) >= 6 if not pd.isna(x) else False),
    "high_news2": ("news2_score", lambda x: coerce_int(x) >= 5 if not pd.isna(x) else False),
    
    # Renal dysfunction
    "elevated_creatinine": ("creatinine", lambda x: coerce_float(x) > 1.5 if not pd.isna(x) else False),
    
    # Long hospitalization
    "prolonged_hospitalization": ("days_hospitalized", lambda x: coerce_int(x) > 14 if not pd.isna(x) else False),
}


# ══════════════════════════════════════════════════════════════════════════════
# 6. CASE-LEVEL TABLE: Merge demographics, disease labels, risk features
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("4. Building Case-Level Table")
print("─" * 80)

DEMO_COLS = ["submitter_id", "covid19_positive", "sex", "age_at_index",
             "race", "icu_indicator", "ventilator_indicator"]

df_cases_unique = df_cases.drop_duplicates("submitter_id")[DEMO_COLS].copy()

df_case_all = (
    df_cases_unique
    .merge(df_case_labels, left_on="submitter_id", right_on="case_ids_clean", how="left")
    .merge(obs_pivot, left_on="submitter_id", right_on="case_ids_clean", how="left", suffixes=("", "_obs"))
    .merge(df_proc_wide, left_on="submitter_id", right_on="case_ids_clean", how="left", suffixes=("", "_proc"))
    .merge(df_visit_agg, left_on="submitter_id", right_on="case_ids_clean", how="left", suffixes=("", "_visit"))
)

# Fill missing label columns
for col in LABEL_COLS:
    if col in df_case_all.columns:
        df_case_all[col] = df_case_all[col].fillna(0).astype(int)
    else:
        df_case_all[col] = 0

# Reinforce COVID from case-level flag
df_case_all["covid"] = (
    (df_case_all.get("covid", pd.Series(0, index=df_case_all.index)) == 1) |
    (df_case_all["covid19_positive"].fillna("").str.lower() == "yes")
).astype(int)

# Compute risk tier
df_case_all["risk_tier"] = df_case_all.apply(compute_risk_tier, axis=1)

# Compute individual risk factors
for risk_factor, (source_col, fn) in RISK_FACTORS.items():
    if source_col in df_case_all.columns:
        df_case_all[risk_factor] = df_case_all[source_col].apply(fn).astype(int)
    else:
        df_case_all[risk_factor] = 0

print(f"✓ Merged case table: {len(df_case_all):,} cases")
print(f"\nRisk tier distribution:")
risk_tier_names = {0: "mild", 1: "moderate", 2: "severe"}
for tier in sorted(df_case_all["risk_tier"].unique()):
    count = (df_case_all["risk_tier"] == tier).sum()
    pct = 100 * count / len(df_case_all)
    print(f"  {risk_tier_names[tier]:<10}: {count:5,} ({pct:5.1f}%)")

print(f"\nRisk factors prevalence:")
risk_factor_names = list(RISK_FACTORS.keys())
for rf in risk_factor_names:
    if rf in df_case_all.columns:
        count = df_case_all[rf].sum()
        pct = 100 * count / len(df_case_all)
        print(f"  {rf:<30}: {count:5,} ({pct:5.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# 7. SERIES-LEVEL TABLES: Merge case-level labels onto CT/CXR series
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("5. Building Series-Level Tables (CT and CXR)")
print("─" * 80)

def build_series_df(df_series: pd.DataFrame,
                    df_annot_clean: pd.DataFrame,
                    modality: str) -> pd.DataFrame:
    """Merge case-level features onto series."""
    df = df_series.copy()
    
    # Merge case-level data
    df = df.merge(df_case_all, left_on="case_ids_clean", right_on="submitter_id",
                  how="left", suffixes=("_series", ""))
    
    # Merge series-level annotations
    df = df.merge(df_annot_clean, left_on="submitter_id", right_on="submitter_id",
                  how="left", suffixes=("", "_annot"))
    
    # Add modality tag
    df["modality"] = modality
    
    # Coerce mRALE score to float
    if "midrc_mRALE_score" in df.columns:
        df["midrc_mRALE_score"] = df["midrc_mRALE_score"].apply(coerce_float)
    
    return df

df_ct_merged = build_series_df(df_chest_ct, df_annot_ct_clean, "CT")
df_cxr_merged = build_series_df(df_chest_cxr, df_annot_cxr_clean, "CXR")

print(f"  CT  merged series:  {len(df_ct_merged):,}")
print(f"  CXR merged series:  {len(df_cxr_merged):,}")


# ══════════════════════════════════════════════════════════════════════════════
# 8. BALANCED SAMPLING: Create balanced cohorts for training
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("6. Balanced Sampling")
print("─" * 80)

# Target samples per disease label
TIER_N = {
    "covid": 200,
    "pneumonia": 200,
    "effusion": 200,
    "atelectasis": 175,
    "fibrosis": 175,
    "pulm_embolism": 150,
    "emphysema": 100,
    "pneumothorax": 150,
    "pulm_edema": 100,
    "ards": 100,
    "normal": 200,
}

# For CXR, PE is less visible (no CTA)
TIER_N_CXR = {**TIER_N, "pulm_embolism": 50}

def balanced_sample(df: pd.DataFrame,
                    tier_n: dict,
                    id_col: str = "object_id",
                    random_state: int = 42) -> pd.DataFrame:
    """Sample balanced cohort across disease labels."""
    df_unique = df.drop_duplicates(id_col).copy()
    
    balanced_frames = []
    print("\n  Sampling:")
    for label in IMAGING_LABELS:
        pool = df_unique[df_unique[label] == 1]
        n = min(tier_n.get(label, 150), len(pool))
        if n > 0:
            balanced_frames.append(pool.sample(n=n, random_state=random_state))
            print(f"    {label:<20}: {n:>3} / {len(pool):>5} available")
    
    # Sample normals
    normal_pool = df_unique[df_unique["normal"] == 1]
    n_normal = min(tier_n.get("normal", 200), len(normal_pool))
    if n_normal > 0:
        balanced_frames.append(normal_pool.sample(n=n_normal, random_state=random_state))
        print(f"    {'normal':<20}: {n_normal:>3} / {len(normal_pool):>5} available")
    
    df_cohort = pd.concat(balanced_frames).drop_duplicates(id_col).reset_index(drop=True)
    return df_cohort

print("CT cohort:")
df_cohort_ct = balanced_sample(df_ct_merged, TIER_N, id_col="object_id")

print("\nCXR cohort:")
df_cohort_cxr = balanced_sample(df_cxr_merged, TIER_N_CXR, id_col="object_id")


# ══════════════════════════════════════════════════════════════════════════════
# 9. DEFINE "NORMAL": Series with no imaging labels
# ══════════════════════════════════════════════════════════════════════════════

ALL_LABEL_COLS = IMAGING_LABELS + CLINICAL_LABELS + ["normal"]

def add_normal_label(df: pd.DataFrame) -> pd.DataFrame:
    """Mark series as normal if no other imaging label is present."""
    df["normal"] = (df[IMAGING_LABELS].sum(axis=1) == 0).astype(int)
    return df

df_cohort_ct = add_normal_label(df_cohort_ct)
df_cohort_cxr = add_normal_label(df_cohort_cxr)


# ══════════════════════════════════════════════════════════════════════════════
# 10. DIAGNOSTICS & REPORTING
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("7. Final Cohort Statistics")
print("─" * 80)

def print_cohort_stats(df: pd.DataFrame, name: str, outfile=None):
    """Print comprehensive cohort statistics."""
    lines = []
    
    def log(msg):
        print(msg)
        if outfile:
            lines.append(msg)
    
    log(f"\n{'='*70}")
    log(f"{name}")
    log(f"{'='*70}")
    log(f"Series total: {len(df):,}")
    log(f"Unique cases: {df['submitter_id'].nunique():,}")
    
    log(f"\n{'-'*70}")
    log("DISEASE LABELS (imaging targets):")
    log(f"{'-'*70}")
    for label in sorted(IMAGING_LABELS, key=lambda x: -df[x].sum()):
        count = int(df[label].sum())
        pct = 100 * count / len(df)
        log(f"  {label:<20}: {count:5,} ({pct:5.1f}%)")
    
    normal_count = int(df["normal"].sum())
    normal_pct = 100 * normal_count / len(df)
    log(f"  {'normal':<20}: {normal_count:5,} ({normal_pct:5.1f}%)")
    
    log(f"\n{'-'*70}")
    log("RISK ASSESSMENT TARGETS:")
    log(f"{'-'*70}")
    for tier in sorted(df["risk_tier"].unique()):
        count = (df["risk_tier"] == tier).sum()
        pct = 100 * count / len(df)
        log(f"  {risk_tier_names[tier]:<20}: {count:5,} ({pct:5.1f}%)")
    
    log(f"\n{'-'*70}")
    log("RISK FACTORS (for narrative generation):")
    log(f"{'-'*70}")
    for rf in risk_factor_names:
        if rf in df.columns:
            count = df[rf].sum()
            pct = 100 * count / len(df)
            log(f"  {rf:<30}: {count:5,} ({pct:5.1f}%)")
    
    log(f"\n{'-'*70}")
    log("DEMOGRAPHICS:")
    log(f"{'-'*70}")
    if "sex" in df.columns:
        for sex_val in df["sex"].dropna().unique():
            count = (df["sex"] == sex_val).sum()
            pct = 100 * count / len(df)
            log(f"  {sex_val:<20}: {count:5,} ({pct:5.1f}%)")
    
    if "age_at_index" in df.columns:
        age_valid = pd.to_numeric(df["age_at_index"], errors="coerce")
        age_valid = age_valid[age_valid.notna()]
        if len(age_valid) > 0:
            log(f"  Age: mean={age_valid.mean():.1f}, median={age_valid.median():.1f}, "
                f"range=[{age_valid.min():.0f}, {age_valid.max():.0f}]")
    
    log(f"\n{'-'*70}")
    log("LABEL CO-OCCURRENCE (top 10 combinations):")
    log(f"{'-'*70}")
    combos = df[IMAGING_LABELS].apply(
        lambda x: tuple(col for col in IMAGING_LABELS if x[col] == 1), axis=1
    )
    for combo, count in Counter(combos).most_common(10):
        label = combo if combo else ("normal",)
        log(f"  {str(label):<60}: {count:>4}")
    
    return lines

report_ct = print_cohort_stats(df_cohort_ct, "CT COHORT")
report_cxr = print_cohort_stats(df_cohort_cxr, "CXR COHORT")


# ══════════════════════════════════════════════════════════════════════════════
# 11. EXPORT
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("8. Exporting Datasets")
print("─" * 80)

# Select key columns for export
EXPORT_COLS = (
    ["object_id", "submitter_id", "modality", "case_ids_clean"] +
    DEMO_COLS +
    IMAGING_LABELS +
    CLINICAL_LABELS +
    ["normal", "risk_tier"] +
    risk_factor_names +
    ["midrc_mRALE_score", "airspace_disease_grading", "class_covid19_pneumonia"] +
    [c for c in obs_pivot.columns if c != "case_ids_clean"] +
    list(RISK_PROCEDURES.values()) +
    [c for c in df_visit_agg.columns if c not in ["case_ids_clean", "submitter_id"]]
)

# Filter to existing columns
EXPORT_COLS = [c for c in EXPORT_COLS if c in df_cohort_ct.columns]

# Export CT cohort
df_cohort_ct[EXPORT_COLS].to_csv(OUTPUT_DIR / "cohort_ct.csv", index=False)
print(f"✓ Exported: {OUTPUT_DIR / 'cohort_ct.csv'}")

# Export CXR cohort
df_cohort_cxr[EXPORT_COLS].to_csv(OUTPUT_DIR / "cohort_cxr.csv", index=False)
print(f"✓ Exported: {OUTPUT_DIR / 'cohort_cxr.csv'}")

# Create Gen3 download manifests
def make_manifest(df: pd.DataFrame) -> list:
    """Create Gen3 download manifest."""
    return [{"object_id": oid} for oid in df["object_id"].dropna().unique()]

with open(OUTPUT_DIR / "manifest_ct.json", "w") as f:
    json.dump(make_manifest(df_cohort_ct), f, indent=2)
print(f"✓ Exported: {OUTPUT_DIR / 'manifest_ct.json'}")

with open(OUTPUT_DIR / "manifest_cxr.json", "w") as f:
    json.dump(make_manifest(df_cohort_cxr), f, indent=2)
print(f"✓ Exported: {OUTPUT_DIR / 'manifest_cxr.json'}")

# Export label map
label_map_export = {
    "disease_head": {
        "description": "Multi-label pathology classification from chest imaging",
        "condition_label_map": CONDITION_LABEL_MAP,
        "imaging_labels": IMAGING_LABELS,
        "clinical_labels": CLINICAL_LABELS,
        "label_definitions": {
            "covid": "COVID-19 or related coronavirus infection",
            "pneumonia": "Pneumonia of any organism type",
            "effusion": "Pleural or pericardial fluid collection",
            "fibrosis": "Pulmonary fibrosis or interstitial lung disease",
            "emphysema": "Pulmonary emphysema",
            "atelectasis": "Lung collapse",
            "pneumothorax": "Air in pleural space",
            "pulm_embolism": "Pulmonary thromboembolism",
            "ards": "Acute respiratory distress syndrome",
            "pulm_edema": "Pulmonary edema/fluid in lungs",
            "normal": "No imaging abnormality",
            "resp_failure": "Acute or chronic respiratory failure (metadata only)",
        },
    },
    "risk_head": {
        "description": "Severity prediction and risk factors for narrative generation",
        "risk_tier": {
            "0": "Mild — no ICU admission, no mechanical ventilation, no respiratory failure",
            "1": "Moderate — ICU admission or respiratory failure, without mechanical ventilation",
            "2": "Severe — mechanical ventilation, ECMO support, or prone positioning",
        },
        "risk_observation_signals": RISK_OBSERVATION_SIGNALS,
        "risk_procedures": RISK_PROCEDURES,
        "risk_factors": {
            "age_elderly": "Patient age > 65 years",
            "age_very_elderly": "Patient age > 80 years",
            "bmi_obese": "BMI > 30 kg/m²",
            "bmi_high": "BMI > 25 kg/m²",
            "high_o2_requirement": "Oxygen flow rate > 6 L/min",
            "low_o2_saturation": "Oxygen saturation < 94%",
            "high_sofa": "SOFA score ≥ 6",
            "high_news2": "NEWS2 score ≥ 5",
            "elevated_creatinine": "Creatinine > 1.5 mg/dL",
            "prolonged_hospitalization": "Hospitalization > 14 days",
        },
    },
}

with open(OUTPUT_DIR / "label_map.json", "w") as f:
    json.dump(label_map_export, f, indent=2)
print(f"✓ Exported: {OUTPUT_DIR / 'label_map.json'}")

# Export detailed report
report_text = "\n".join(report_ct) + "\n" + "\n".join(report_cxr)
with open(OUTPUT_DIR / "dataset_report.txt", "w") as f:
    f.write(report_text)
print(f"✓ Exported: {OUTPUT_DIR / 'dataset_report.txt'}")

print("\n" + "=" * 80)
print("DATASET CONSTRUCTION COMPLETE")
print("=" * 80)
print(f"\nGenerated files in {OUTPUT_DIR}/:")
print(f"  • cohort_ct.csv          ({len(df_cohort_ct):,} CT series)")
print(f"  • cohort_cxr.csv         ({len(df_cohort_cxr):,} CXR series)")
print(f"  • manifest_ct.json       ({len(make_manifest(df_cohort_ct)):,} objects)")
print(f"  • manifest_cxr.json      ({len(make_manifest(df_cohort_cxr)):,} objects)")
print(f"  • label_map.json         (disease & risk definitions)")
print(f"  • dataset_report.txt     (statistics & diagnostics)")
print("\nTotal imaging series ready for training:", len(df_cohort_ct) + len(df_cohort_cxr))
