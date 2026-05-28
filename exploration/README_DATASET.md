# Dual-Head Dataset Builder for MIDRC

## Overview

This dataset builder constructs a comprehensive training dataset for a dual-head deep learning model:

- **HEAD 1: Disease Classification** — Multi-label pathology prediction from CT and CXR chest imaging
- **HEAD 2: Risk Assessment** — Severity tiers and individual risk factors for clinical narrative generation

The pipeline extracts data from the MIDRC Gen3 data commons, engineers disease labels from ICD-10 condition codes, and derives risk factors from clinical observations, procedures, and visit records.

---

## Quick Start

### 1. Prepare Credentials

```bash
# Download credentials from MIDRC
# https://data.midrc.org/identity

# Save as credentials.json in project root
cp ~/Downloads/credentials.json .
```

### 2. Run Dataset Builder

```bash
# Activate environment (if not already done)
source venv/bin/activate

# Build dataset
cd exploration
python build_dual_head_dataset.py
```

This will:
1. Connect to MIDRC Gen3 API and export all relevant data nodes
2. Filter to chest-region imaging only (CT & CXR)
3. Engineer disease labels from condition ICD-10 codes
4. Extract and derive risk factors
5. Create balanced sampling cohorts
6. Export CSV, JSON manifests, and statistics

**Output:** ~5-10 minutes depending on internet speed and data volume

---

## Data Architecture

### Generated Files

```
data/
├── cohort_ct.csv              # ~2200-2500 CT series with labels
├── cohort_cxr.csv             # ~2200-2500 CXR series with labels
├── manifest_ct.json            # Gen3 download manifest (CT)
├── manifest_cxr.json           # Gen3 download manifest (CXR)
├── label_map.json              # Comprehensive label definitions
└── dataset_report.txt          # Statistics & diagnostics
```

### Column Structure

#### Identifiers
- `object_id` — Unique imaging series ID (for Gen3 download)
- `submitter_id` — Case/patient ID
- `modality` — "CT" or "CXR"

#### Demographics (case-level)
- `sex` — "Male" / "Female" / etc.
- `age_at_index` — Patient age at first visit
- `race` — Self-reported race
- `covid19_positive` — Case-level COVID status

#### Disease Labels (binary, multi-label) — HEAD 1 TARGETS
- `covid` — COVID-19 infection
- `pneumonia` — Pneumonia (any organism)
- `effusion` — Pleural/pericardial effusion
- `fibrosis` — Pulmonary fibrosis / ILD
- `emphysema` — Emphysema
- `atelectasis` — Atelectasis/collapse
- `pneumothorax` — Pneumothorax
- `pulm_embolism` — Pulmonary embolism
- `ards` — ARDS
- `pulm_edema` — Pulmonary edema
- `normal` — No imaging pathology

#### Risk Assessment — HEAD 2 TARGETS
- `risk_tier` — Ordinal severity: 0=mild, 1=moderate, 2=severe
- Risk factors (binary for narrative generation):
  - `age_elderly` — Age > 65
  - `age_very_elderly` — Age > 80
  - `bmi_obese` — BMI > 30
  - `bmi_high` — BMI > 25
  - `high_o2_requirement` — O₂ flow > 6 L/min
  - `low_o2_saturation` — O₂ sat < 94%
  - `high_sofa` — SOFA ≥ 6
  - `high_news2` — NEWS2 ≥ 5
  - `elevated_creatinine` — Creatinine > 1.5
  - `prolonged_hospitalization` — LOS > 14 days

#### Clinical Measurements (continuous/categorical)
- `o2_flow_rate`, `o2_saturation` — Oxygen metrics
- `bmi`, `pack_years`, `smoking_status` — Lifestyle
- `sofa_score`, `news2_score` — Severity scores
- `heart_rate`, `respiratory_rate`, `temperature` — Vitals
- `sbp`, `dbp` — Blood pressure
- `creatinine` — Renal function
- `days_hospitalized`, `days_icu`, `days_ventilator` — LOS
- `los_hospital_days`, `los_icu_days` — Computed from visit node

#### Treatment Procedures (binary)
- `proc_mechanical_ventilation` — Intubated/on ventilator
- `proc_niv` — Non-invasive ventilation (CPAP/BiPAP)
- `proc_hfnc` — High-flow nasal cannula
- `proc_intubation` — Endotracheal intubation
- `proc_ecmo` — ECMO support
- `proc_vasopressor` — Vasoactive drugs
- `proc_prone` — Prone positioning
- `proc_rrt` — Renal replacement therapy
- `proc_tocilizumab` — IL-6 inhibitor immunotherapy
- `proc_remdesivir` — Antiviral (if COVID)
- `proc_dexamethasone` — Corticosteroid
- `proc_anticoagulation` — Anticoagulation/VTE prophylaxis

#### Imaging Annotations (series-level)
- `midrc_mRALE_score` — Modified RALE score (0-8, continuous)
- `airspace_disease_grading` — Airspace involvement categorical grade
- `class_covid19_pneumonia` — Radiologist COVID pneumonia classification

#### Clinical Metadata
- `icu_indicator` — "Yes"/"No" ICU admission
- `ventilator_indicator` — "Yes"/"No" mechanical ventilation
- `resp_failure` — Respiratory failure diagnosis (binary)

---

## HEAD 1: Disease Classification

### Target Labels (11 classes)

Derived from **ICD-10 condition codes** in the MIDRC condition node. The mapping is **synonym-aware**, grouping related codes:

| Label | Count | Examples |
|-------|-------|----------|
| **covid** | ~200 | U07.1, COVID-19, post-COVID |
| **pneumonia** | ~200 | Bacterial, viral, atypical, aspiration pneumonia |
| **effusion** | ~200 | Pleural effusion, hemothorax, pyothorax |
| **atelectasis** | ~175 | Atelectasis, pulmonary collapse |
| **fibrosis** | ~175 | IPF, ILD, sarcoidosis, asbestosis |
| **pulm_embolism** | ~150 | PE, acute/chronic/septic |
| **pneumothorax** | ~150 | Spontaneous, post-procedural, tension |
| **emphysema** | ~100 | Centrilobular, panlobular |
| **ards** | ~100 | Acute respiratory distress syndrome |
| **pulm_edema** | ~100 | Acute/chronic pulmonary edema |
| **normal** | ~200 | No imaging pathology |

### Label Definitions

- **Imaging-visible**: Labels tied to radiographic findings (covid, pneumonia, effusion, etc.)
- **Clinical state** (metadata only): `resp_failure` — kept in dataset but not used for training

### Multi-label Structure

Each series can have **0 to N labels**. Examples:
- `[covid, pneumonia]` — COVID-19 with secondary pneumonia
- `[effusion, atelectasis]` — Pleural effusion with collapse
- `[normal]` — No pathology
- `[]` → converted to `normal=1`

### Data Engineering

**Source**: `condition` node (ICD-10 codes)
**Granularity**: Case-level (all series for a case share the same disease labels)
**Method**:
1. Clean case IDs from structured arrays
2. Group conditions by case
3. Map condition names to labels (case-insensitive)
4. Create binary columns for each label

---

## HEAD 2: Risk Assessment

### Target 1: Risk Tier (Ordinal Severity)

**Ordinal regression target**: Predicts severity on 3-point scale

```
Risk Tier 0 — MILD
├─ No ICU admission
├─ No mechanical ventilation
└─ No respiratory failure

Risk Tier 1 — MODERATE
├─ ICU admission OR respiratory failure
└─ BUT no mechanical ventilation/ECMO/prone

Risk Tier 2 — SEVERE
├─ Mechanical ventilation OR
├─ ECMO support OR
└─ Prone positioning
```

**Data source**: Combines:
- `case.icu_indicator` (Yes/No)
- `case.ventilator_indicator` (Yes/No)
- `condition.resp_failure` (binary label)
- `procedure.*` flags (mechanical ventilation, ECMO, prone)

**Typical distribution**:
- 30-35% mild
- 35-40% moderate
- 25-30% severe

### Target 2: Individual Risk Factors (Binary)

For **narrative generation** by LLM. Each factor captures a clinically meaningful risk:

#### Age
- `age_elderly` — > 65 years (common risk threshold)
- `age_very_elderly` — > 80 years (highest risk)

#### Metabolic
- `bmi_obese` — BMI > 30 (obesity increases respiratory risk)
- `bmi_high` — BMI > 25 (overweight threshold)

#### Oxygenation & Ventilation
- `high_o2_requirement` — Flow > 6 L/min (hypoxemia despite supplementation)
- `low_o2_saturation` — SpO₂ < 94% (inadequate oxygenation)

#### Severity Scores
- `high_sofa` — SOFA ≥ 6 (multi-organ dysfunction)
- `high_news2` — NEWS2 ≥ 5 (early warning score threshold)

#### Organ Dysfunction
- `elevated_creatinine` — > 1.5 mg/dL (acute kidney injury)

#### Healthcare Utilization
- `prolonged_hospitalization` — > 14 days LOS (indicates severity)

### Data Sources for Risk Features

| Feature | Node | Field | Processing |
|---------|------|-------|------------|
| Age | `case` | `age_at_index` | Numeric coercion |
| BMI, vitals | `observation` | `observation_answer` | Pivot by signal name, numeric coercion |
| SOFA, NEWS2 | `observation` | `observation_answer` | Parse numeric |
| Procedures | `procedure` | `procedure_name` | Binary flag (any/none) |
| LOS | `visit` | Days admission → discharge | Computed delta, clipped to 0 |
| O₂ saturation | `observation` | `O2 Saturation` | Thresholded |

---

## Dataset Balancing

### Sampling Strategy

**Goal**: Prevent majority labels (e.g., pneumonia) from dominating training

**Method**: Stratified sampling across disease labels with **tiered targets**

```python
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
```

### Result

- **CT cohort**: ~2,200-2,500 series
- **CXR cohort**: ~2,200-2,500 series
- Each label represented by ~100-200 series
- Co-occurrence patterns preserved (e.g., COVID + pneumonia allowed)
- Normal/negative cases included for specificity training

### Data Leakage Prevention

- Sampling by **series** (`object_id`), not case — multiple series per case are independent
- Random seed=42 for reproducibility
- Train/val/test splits handled at model level

---

## Quality Assurance

### Diagnostics

The builder generates `dataset_report.txt` with:

1. **Cohort size & composition**
   - Total series, unique cases
   - Label distribution (count & %)

2. **Label co-occurrence patterns**
   - Top 10 label combinations
   - Ensures balanced multi-label structure

3. **Risk tier distribution**
   - % mild, moderate, severe

4. **Risk factor prevalence**
   - % with age_elderly, high_o2_requirement, etc.

5. **Demographics**
   - Sex distribution
   - Age statistics (mean, median, range)

### Common Issues & Fixes

**Issue**: Few annotations (mRALE scores)
- **OK** — annotations are optional series-level metadata
- Model can train on binary labels without scores
- Use scores only in separate modeling branch if needed

**Issue**: Missing risk factors (e.g., BMI for all cases)
- **Expected** — observation data is sparse
- Use NaN/0 as "unknown" in feature engineering
- LLM narrative generation must handle missing values

**Issue**: Imbalanced risk tiers
- **Acceptable** — real-world severity follows power law
- Can up-weight rare severe cases in training loss

---

## Using the Dataset

### For Disease Classification (HEAD 1)

```python
import pandas as pd

# Load
df_ct = pd.read_csv("data/cohort_ct.csv")

# Access labels
labels = ["covid", "pneumonia", "effusion", "fibrosis", "emphysema", 
          "atelectasis", "pneumothorax", "pulm_embolism", "ards", "pulm_edema"]

# Get training data
X = df_ct[["object_id", "modality"]]  # Or image tensors loaded from Gen3
y = df_ct[labels]  # Multi-hot binary matrix

# Train multi-label classifier (BCE loss, sigmoid activation)
```

### For Risk Assessment (HEAD 2)

```python
# Ordinal risk tier (0, 1, 2)
y_tier = df_ct["risk_tier"]

# Individual risk factors (for LLM narrative)
risk_factors = [
    "age_elderly", "age_very_elderly",
    "bmi_obese", "high_o2_requirement", "low_o2_saturation",
    "high_sofa", "high_news2", "elevated_creatinine",
    "prolonged_hospitalization"
]
y_factors = df_ct[risk_factors]

# Clinical metadata (for context)
metadata = df_ct[["age_at_index", "sex", "o2_saturation", "sofa_score"]]

# LLM pipeline
narrative = generate_risk_narrative(
    risk_tier=y_tier.iloc[0],
    risk_factors=y_factors.iloc[0],
    metadata=metadata.iloc[0]
)
# → "Patient is 72 years old (elderly) with moderate severity. 
#     Elevated inflammatory markers (SOFA ≥6) and extended ICU stay
#     suggest multi-organ involvement. Close monitoring recommended."
```

### Gen3 Download

```bash
# Download actual imaging files using manifest
gen3 drs-pull manifest_ct.json

# Places DICOM/imaging files in current directory
```

---

## Label Map Reference

Load `label_map.json` for programmatic access:

```python
import json

with open("data/label_map.json") as f:
    label_map = json.load(f)

# Disease definitions
disease_map = label_map["disease_head"]["condition_label_map"]
# ICD-10 code → disease label mapping

# Risk definitions
risk_tier_defs = label_map["risk_head"]["risk_tier"]
# Severity tier descriptions

risk_factors_defs = label_map["risk_head"]["risk_factors"]
# Individual risk factor interpretations
```

---

## Common Queries

### How many cases have COVID?

```python
covid_cases = df_ct[df_ct["covid"] == 1].groupby("submitter_id").size()
print(len(covid_cases))  # Unique cases
```

### What's the most common label combination?

```python
from collections import Counter

label_cols = ["covid", "pneumonia", "effusion", ...]
combos = df_ct[label_cols].apply(
    lambda x: tuple(col for col in label_cols if x[col] == 1), axis=1
)
Counter(combos).most_common(5)
```

### How many high-risk cases (severe tier + old age)?

```python
high_risk = df_ct[(df_ct["risk_tier"] == 2) & (df_ct["age_elderly"] == 1)]
print(len(high_risk))
```

### Distribution of hospitalization length?

```python
los = pd.to_numeric(df_ct["days_hospitalized"], errors="coerce")
print(los.describe())
# count, mean, std, min, 25%, 50%, 75%, max
```

---

## Next Steps

1. **Download imaging data** using Gen3 manifests
2. **Integrate with modeling pipeline** (see `../modelling/dual_head_architecture.py`)
3. **Train disease head** with multi-label BCE loss
4. **Train risk head** with ordinal regression + risk factor classification
5. **Deploy narrative generation** with LLM using risk factors

---

## Citation

**MIDRC Dataset**: <https://data.midrc.org/>

```bibtex
@article{MIDRC2021,
  title={Medical Imaging Data Resource Center (MIDRC): A Case Repository 
         for AI Algorithm Development and Validation},
  journal={Radiology},
  year={2021}
}
```

---

## Questions?

- Review `dataset_report.txt` for detailed diagnostics
- Check `label_map.json` for label definitions
- Examine a few rows: `head -20 cohort_ct.csv | column -t -s,`

