"""
Dataset Examples & Common Queries
===================================
Quick reference for working with the dual-head dataset
"""

import pandas as pd
import numpy as np

# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE 1: Load and Inspect
# ═══════════════════════════════════════════════════════════════════════════

# Load the datasets
df_ct = pd.read_csv("data/cohort_ct.csv")

# Inspect first row
print("Example CT series:")
print(df_ct.iloc[0][["object_id", "submitter_id", "modality", "age_at_index", "sex"]].to_string())

# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE 2: Disease Labels (HEAD 1)
# ═══════════════════════════════════════════════════════════════════════════

IMAGING_LABELS = ["covid", "pneumonia", "effusion", "fibrosis", "emphysema",
                  "atelectasis", "pneumothorax", "pulm_embolism", "ards", "pulm_edema"]

# ── Query: How many COVID cases?
covid_series = df_ct[df_ct["covid"] == 1]
print(f"\nCOVID-19 prevalence: {len(covid_series)} series ({100*len(covid_series)/len(df_ct):.1f}%)")

# ── Query: How many co-infections (COVID + pneumonia)?
coinfected = df_ct[(df_ct["covid"] == 1) & (df_ct["pneumonia"] == 1)]
print(f"COVID + pneumonia co-infection: {len(coinfected)} series")

# ── Query: What's the most common label combination?
from collections import Counter
label_combos = df_ct[IMAGING_LABELS].apply(
    lambda row: tuple(col for col in IMAGING_LABELS if row[col] == 1),
    axis=1
)
top_combos = Counter(label_combos).most_common(5)
print("\nTop 5 label combinations:")
for combo, count in top_combos:
    if combo:
        print(f"  {combo}: {count} series")
    else:
        print(f"  (normal): {count} series")

# ── Query: Distribution of multi-label complexity
n_labels = df_ct[IMAGING_LABELS].sum(axis=1)
print(f"\nLabel complexity distribution:")
for n in sorted(n_labels.unique()):
    count = (n_labels == n).sum()
    pct = 100 * count / len(df_ct)
    print(f"  {n} labels: {count:>4} series ({pct:>5.1f}%)")

# ── Query: Disease prevalence
print(f"\nDisease prevalence (ranked):")
disease_counts = df_ct[IMAGING_LABELS].sum().sort_values(ascending=False)
for disease, count in disease_counts.items():
    pct = 100 * count / len(df_ct)
    print(f"  {disease:<20}: {count:>4} ({pct:>5.1f}%)")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 3: Risk Assessment Targets (HEAD 2)
# ─────────────────────────────────────────────────────────────────────────

RISK_FACTORS = [
    "age_elderly", "age_very_elderly", "bmi_obese", "bmi_high",
    "high_o2_requirement", "low_o2_saturation", "high_sofa",
    "high_news2", "elevated_creatinine", "prolonged_hospitalization"
]

# ── Query: Risk tier distribution
risk_tier_names = {0: "mild", 1: "moderate", 2: "severe"}
print(f"\nRisk tier distribution:")
for tier in sorted(df_ct["risk_tier"].unique()):
    count = (df_ct["risk_tier"] == tier).sum()
    pct = 100 * count / len(df_ct)
    print(f"  {risk_tier_names[tier]:<10}: {count:>4} ({pct:>5.1f}%)")

# ── Query: How many high-risk patients (severe + elderly)?
high_risk = df_ct[(df_ct["risk_tier"] == 2) & (df_ct["age_elderly"] == 1)]
print(f"\nSevere + elderly: {len(high_risk)} patients ({100*len(high_risk)/len(df_ct):.1f}%)")

# ── Query: Risk factor prevalence
print(f"\nRisk factor prevalence:")
for rf in RISK_FACTORS:
    count = df_ct[rf].sum()
    pct = 100 * count / len(df_ct)
    print(f"  {rf:<30}: {count:>4} ({pct:>5.1f}%)")

# ── Query: Correlation of age and risk tier
elderly = df_ct["age_elderly"].mean()
young = (1 - df_ct["age_elderly"]).mean()
elderly_severe = df_ct[df_ct["age_elderly"] == 1]["risk_tier"].mean()
young_severe = df_ct[df_ct["age_elderly"] == 0]["risk_tier"].mean()
print(f"\nAge and severity correlation:")
print(f"  Elderly avg risk tier: {elderly_severe:.2f} vs Young: {young_severe:.2f}")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 4: Demographics
# ─────────────────────────────────────────────────────────────────────────

# ── Query: Age statistics
age_valid = pd.to_numeric(df_ct["age_at_index"], errors="coerce").dropna()
print(f"\nAge statistics:")
print(f"  count: {len(age_valid)}")
print(f"  mean: {age_valid.mean():.1f} years")
print(f"  median: {age_valid.median():.1f} years")
print(f"  range: {age_valid.min():.0f} - {age_valid.max():.0f} years")
print(f"  25th percentile: {age_valid.quantile(0.25):.0f}")
print(f"  75th percentile: {age_valid.quantile(0.75):.0f}")

# ── Query: Sex distribution
print(f"\nSex distribution:")
sex_dist = df_ct["sex"].value_counts()
for sex, count in sex_dist.items():
    pct = 100 * count / len(df_ct)
    print(f"  {sex:<20}: {count:>4} ({pct:>5.1f}%)")

# ── Query: COVID status
print(f"\nCOVID-19 status (case-level flag):")
covid_dist = df_ct["covid19_positive"].value_counts()
for status, count in covid_dist.items():
    pct = 100 * count / len(df_ct)
    print(f"  {status:<20}: {count:>4} ({pct:>5.1f}%)")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 5: Clinical Measurements
# ─────────────────────────────────────────────────────────────────────────

# ── Query: O2 saturation statistics
o2_sat = pd.to_numeric(df_ct["o2_saturation"], errors="coerce")
o2_sat_valid = o2_sat.dropna()
print(f"\nOxygen saturation (SpO₂):")
print(f"  n: {len(o2_sat_valid)}")
print(f"  mean: {o2_sat_valid.mean():.1f}%")
print(f"  median: {o2_sat_valid.median():.1f}%")
print(f"  <94%: {(o2_sat_valid < 94).sum()} cases")

# ── Query: BMI categories
bmi = pd.to_numeric(df_ct["bmi"], errors="coerce")
bmi_valid = bmi.dropna()
print(f"\nBMI distribution (n={len(bmi_valid)}):")
print(f"  mean: {bmi_valid.mean():.1f} kg/m²")
print(f"  obese (>30): {(bmi_valid > 30).sum()}")
print(f"  overweight (25-30): {((bmi_valid >= 25) & (bmi_valid <= 30)).sum()}")
print(f"  normal (<25): {(bmi_valid < 25).sum()}")

# ── Query: SOFA and NEWS2 scores
sofa = pd.to_numeric(df_ct["sofa_score"], errors="coerce")
sofa_valid = sofa.dropna()
news2 = pd.to_numeric(df_ct["news2_score"], errors="coerce")
news2_valid = news2.dropna()
print(f"\nSeverity scores:")
print(f"  SOFA (n={len(sofa_valid)}): mean={sofa_valid.mean():.1f}, high(≥6)={int((sofa_valid >= 6).sum())}")
print(f"  NEWS2 (n={len(news2_valid)}): mean={news2_valid.mean():.1f}, high(≥5)={int((news2_valid >= 5).sum())}")

# ── Query: Creatinine (kidney function)
creatinine = pd.to_numeric(df_ct["creatinine"], errors="coerce")
creatinine_valid = creatinine.dropna()
print(f"\nCreatinine (kidney function):")
print(f"  n: {len(creatinine_valid)}")
print(f"  mean: {creatinine_valid.mean():.2f} mg/dL")
print(f"  elevated (>1.5): {(creatinine_valid > 1.5).sum()}")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 6: Procedures & Treatments
# ─────────────────────────────────────────────────────────────────────────

PROCEDURES = [
    "proc_mechanical_ventilation", "proc_niv", "proc_hfnc",
    "proc_intubation", "proc_ecmo", "proc_vasopressor", "proc_prone"
]

# ── Query: Respiratory support prevalence
print(f"\nRespiratory support treatments:")
for proc in ["proc_mechanical_ventilation", "proc_niv", "proc_hfnc"]:
    if proc in df_ct.columns:
        count = df_ct[proc].sum()
        pct = 100 * count / len(df_ct)
        print(f"  {proc:<35}: {int(count):>4} ({pct:>5.1f}%)")

# ── Query: Critical care procedures
critical = [
    "proc_mechanical_ventilation", "proc_intubation",
    "proc_ecmo", "proc_prone", "proc_vasopressor"
]
critical_count = df_ct[critical].sum(axis=1) > 0
print(f"\nPatients with critical care procedures: {critical_count.sum()}")

# ── Query: Therapeutic drug use
drugs = ["proc_tocilizumab", "proc_remdesivir", "proc_dexamethasone"]
print(f"\nTherapeutic drugs:")
for drug in drugs:
    if drug in df_ct.columns:
        count = df_ct[drug].sum()
        pct = 100 * count / len(df_ct)
        print(f"  {drug:<35}: {int(count):>4} ({pct:>5.1f}%)")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 7: Length of Stay
# ─────────────────────────────────────────────────────────────────────────

# ── Query: Hospitalization length
los_hosp = pd.to_numeric(df_ct["days_hospitalized"], errors="coerce")
los_hosp_valid = los_hosp.dropna()
if len(los_hosp_valid) > 0:
    print(f"\nHospitalization length of stay:")
    print(f"  n: {len(los_hosp_valid)}")
    print(f"  mean: {los_hosp_valid.mean():.1f} days")
    print(f"  median: {los_hosp_valid.median():.1f} days")
    print(f"  prolonged (>14 days): {(los_hosp_valid > 14).sum()}")

# ── Query: ICU length of stay
los_icu = pd.to_numeric(df_ct["los_icu_days"], errors="coerce")
los_icu_valid = los_icu.dropna()
if len(los_icu_valid) > 0:
    print(f"\nICU length of stay:")
    print(f"  n: {len(los_icu_valid)}")
    print(f"  mean: {los_icu_valid.mean():.1f} days")
    print(f"  median: {los_icu_valid.median():.1f} days")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 8: Data Preparation for Machine Learning
# ─────────────────────────────────────────────────────────────────────────

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

print("\n" + "="*70)
print("DATA PREPARATION FOR ML")
print("="*70)

# ── Setup labels
y_disease = df_ct[IMAGING_LABELS].values  # Multi-label
y_risk_tier = df_ct["risk_tier"].values    # Ordinal [0, 1, 2]
y_risk_factors = df_ct[RISK_FACTORS].values  # Binary

print(f"\nLabel shapes:")
print(f"  Disease (multi-label): {y_disease.shape}")
print(f"  Risk tier (ordinal): {y_risk_tier.shape}")
print(f"  Risk factors (binary): {y_risk_factors.shape}")

# ── Setup clinical features
clinical_cols = ["age_at_index", "bmi", "o2_saturation", "o2_flow_rate",
                 "heart_rate", "respiratory_rate", "sbp", "dbp", "creatinine"]
clinical_available = [c for c in clinical_cols if c in df_ct.columns]
X_clinical = df_ct[clinical_available].fillna(df_ct[clinical_available].mean())
X_clinical_scaled = StandardScaler().fit_transform(X_clinical)

print(f"\nClinical features: {X_clinical.shape}")

# ── Train/test split (stratified by risk tier to preserve distribution)
idx_train, idx_test = train_test_split(
    np.arange(len(df_ct)),
    test_size=0.2,
    random_state=42,
    stratify=y_risk_tier
)

print(f"\nTrain/test split (stratified by risk tier):")
print(f"  Train: {len(idx_train)} samples")
print(f"  Test: {len(idx_test)} samples")

# Verify stratification worked
print(f"\nRisk tier distribution preserved:")
print(f"  Train: {np.bincount(y_risk_tier[idx_train])}")
print(f"  Test: {np.bincount(y_risk_tier[idx_test])}")

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 9: Narrative Generation Example
# ─────────────────────────────────────────────────────────────────────────

print("\n" + "="*70)
print("EXAMPLE: GENERATING RISK NARRATIVES")
print("="*70)

def generate_narrative(row_idx):
    """Generate clinical narrative for a single patient."""
    row = df_ct.iloc[row_idx]
    
    narrative = []
    
    # Age
    age = int(row["age_at_index"]) if pd.notna(row["age_at_index"]) else None
    if age and age > 80:
        narrative.append(f"Very elderly patient ({age} years old) with high baseline risk.")
    elif age and age > 65:
        narrative.append(f"Elderly patient ({age} years old) with increased vulnerability.")
    elif age:
        narrative.append(f"Patient is {age} years old.")
    
    # BMI
    if row["bmi_obese"]:
        narrative.append("Obesity (BMI >30) increases respiratory mechanics burden.")
    elif row["bmi_high"]:
        narrative.append("Overweight status may complicate recovery.")
    
    # Oxygenation
    if row["high_o2_requirement"]:
        narrative.append("Significant hypoxemia requiring high-flow oxygen support.")
    elif row["low_o2_saturation"]:
        narrative.append("Borderline oxygen saturation despite supplementation.")
    
    # Organ dysfunction
    if row["high_sofa"]:
        narrative.append("SOFA score indicates multi-organ involvement.")
    if row["elevated_creatinine"]:
        narrative.append("Elevated creatinine suggests possible acute kidney injury.")
    
    # Course
    if row["prolonged_hospitalization"]:
        narrative.append("Extended hospitalization indicates severe disease course.")
    
    # Risk tier
    tier_names = {0: "mild", 1: "moderate", 2: "severe"}
    risk_tier = int(row["risk_tier"])
    narrative.append(f"Overall risk assessment: {tier_names[risk_tier]}.")
    
    return " ".join(narrative)

# Generate for first severe case
severe_cases = df_ct[df_ct["risk_tier"] == 2]
if len(severe_cases) > 0:
    example_narrative = generate_narrative(severe_cases.index[0])
    print("\nExample narrative (severe patient):")
    print(f'  "{example_narrative}"')

# ─────────────────────────────────────────────────────────────────────────
# EXAMPLE 10: Advanced Filtering
# ─────────────────────────────────────────────────────────────────────────

print("\n" + "="*70)
print("ADVANCED FILTERING EXAMPLES")
print("="*70)

# ── Query: COVID patients with complications
covid_complex = df_ct[
    (df_ct["covid"] == 1) & 
    ((df_ct["pneumonia"] == 1) | (df_ct["ards"] == 1))
]
print(f"\nCOVID-19 with complications: {len(covid_complex)} cases")

# ── Query: Severe cases needing ECMO
ecmo_eligible = df_ct[
    (df_ct["risk_tier"] == 2) & 
    (df_ct["proc_ecmo"] == 1)
]
print(f"Severe cases with ECMO support: {len(ecmo_eligible)}")

# ── Query: Young patients with severe disease
young_severe = df_ct[
    (df_ct["age_elderly"] == 0) & 
    (df_ct["risk_tier"] == 2)
]
print(f"Young (<65) but severe disease: {len(young_severe)}")

# ── Query: Patients with multiple concurrent pathologies
multimorbid = df_ct[df_ct[IMAGING_LABELS].sum(axis=1) >= 3]
print(f"Cases with ≥3 concurrent pathologies: {len(multimorbid)}")

# ── Query: Normal imaging but severe clinically
discordant = df_ct[
    (df_ct["normal"] == 1) & 
    (df_ct["risk_tier"] == 2)
]
print(f"Normal imaging but severe clinically: {len(discordant)}")

print("\n" + "="*70)
print("END OF EXAMPLES")
print("="*70)
