# Dual-Head Dataset Assembly Guide

## Architecture Overview

This guide walks through building and using a comprehensive dataset for a **dual-head deep learning model** that combines:

1. **Disease Classification Head** — Multi-label pathology prediction from chest imaging
2. **Risk Assessment Head** — Severity tiers and individual risk factors for clinical narrative

---

## Dataset Building Pipeline

### Phase 1: Data Export from MIDRC

**Script**: `build_dual_head_dataset.py`

```bash
cd exploration
python build_dual_head_dataset.py
```

**What it does**:
1. Connects to MIDRC Gen3 API using `credentials.json`
2. Exports 9 data nodes:
   - `case` — Patient demographics & outcomes (age, sex, ICU/vent status)
   - `ct_series_file` / `cr_series_file` — Imaging series metadata
   - `imaging_study` — Study LOINC codes (filters chest vs other regions)
   - `condition` — ICD-10 diagnoses (→ disease labels)
   - `annotation` — Radiologist scores (mRALE, COVID classification)
   - `observation` — Vital signs & clinical measurements (O2, BMI, scores)
   - `procedure` — Treatments received (ventilation, drugs, supportive care)
   - `visit` — Hospitalization details (dates, ICU stays, LOS)

3. **Filters**:
   - Keeps only chest-region studies (via LOINC codes)
   - Separates CT and CXR cohorts

4. **Exports 6 files** to `data/`:
   ```
   cohort_ct.csv           # ~2,200-2,500 CT series
   cohort_cxr.csv          # ~2,200-2,500 CXR series
   manifest_ct.json        # Gen3 download list
   manifest_cxr.json       # Gen3 download list
   label_map.json          # Label definitions & mappings
   dataset_report.txt      # Statistics & diagnostics
   ```

**Time**: ~5-10 minutes (depending on network)

---

## Data Structure Details

### HEAD 1: Disease Classification

#### Label Engineering from ICD-10

Each **condition node** record contains an ICD-10 code (string) like:
```
"Pneumonia due to Klebsiella pneumoniae"
"Emergency use of U07.1 | COVID-19"
"Pleural effusion, not elsewhere classified"
```

**Mapping** via `CONDITION_LABEL_MAP` dictionary:
```python
{
    "Pneumonia due to Klebsiella pneumoniae": "pneumonia",
    "COVID-19": "covid",
    "Pleural effusion, not elsewhere classified": "effusion",
    # ... 150+ entries
}
```

**Result**: 11 binary disease labels per case

#### Disease Labels (11 classes)

| Label | Typical % | Clinical Meaning |
|-------|-----------|------------------|
| `covid` | 10-15% | COVID-19 infection |
| `pneumonia` | 15-20% | Pneumonia (any cause) |
| `effusion` | 10-15% | Pleural fluid collection |
| `fibrosis` | 8-12% | Pulmonary fibrosis / ILD |
| `emphysema` | 5-8% | Emphysema |
| `atelectasis` | 10-15% | Lung collapse |
| `pneumothorax` | 5-10% | Collapsed lung (air) |
| `pulm_embolism` | 8-12% | Blood clot in lungs |
| `ards` | 3-5% | Acute respiratory distress |
| `pulm_edema` | 3-5% | Fluid in lungs |
| `normal` | 15-20% | No imaging pathology |

#### Multi-label Structure

Each series gets **0 or more labels** (binary multi-hot encoding):

```
Series A: covid=1, pneumonia=0, effusion=0, fibrosis=0, ... normal=0
Series B: covid=0, pneumonia=1, effusion=1, fibrosis=0, ... normal=0
Series C: covid=0, pneumonia=0, effusion=0, fibrosis=0, ... normal=1
```

---

### HEAD 2: Risk Assessment

#### Target 1: Risk Tier (Ordinal Severity)

**Computed from case-level flags**:

```
RISK TIER 0 — MILD
  ✓ No ICU admission (icu_indicator ≠ "yes")
  ✓ No mechanical ventilation (ventilator_indicator ≠ "yes")
  ✓ No respiratory failure (resp_failure label = 0)
  ✓ No ECMO / prone positioning

RISK TIER 1 — MODERATE
  ✓ ICU admission OR respiratory failure
  ✓ BUT no mechanical ventilation / ECMO

RISK TIER 2 — SEVERE
  ✗ Mechanical ventilation OR
  ✗ ECMO support OR
  ✗ Prone positioning
```

**Data fusion**:
- Primary: `case.icu_indicator`, `case.ventilator_indicator`
- Secondary: `condition.resp_failure` (from ICD-10)
- Tertiary: `procedure.*` flags (validation)

#### Target 2: Individual Risk Factors

**Binary flags for LLM narrative generation**:

| Factor | Threshold | Source | Purpose |
|--------|-----------|--------|---------|
| `age_elderly` | > 65 yrs | `case.age_at_index` | Geriatric risk |
| `age_very_elderly` | > 80 yrs | `case.age_at_index` | Extreme age risk |
| `bmi_obese` | BMI > 30 | `observation.BMI` | Respiratory mechanics |
| `bmi_high` | BMI > 25 | `observation.BMI` | Baseline risk |
| `high_o2_requirement` | Flow > 6 L/min | `observation.O2_Flow_Rate` | Oxygenation failure |
| `low_o2_saturation` | SpO₂ < 94% | `observation.O2_Saturation` | Hypoxemia |
| `high_sofa` | SOFA ≥ 6 | `observation.SOFA_Score` | Multi-organ dysfunction |
| `high_news2` | NEWS2 ≥ 5 | `observation.NEWS2_Score` | Clinical deterioration |
| `elevated_creatinine` | > 1.5 mg/dL | `observation.Creatinine` | Acute kidney injury |
| `prolonged_hospitalization` | LOS > 14 days | `visit.*` (computed) | Disease severity |

**Usage in narrative**:
```
"Patient is 73 years old with obesity (BMI 32).
Hypoxemic despite 8L oxygen (SpO₂ 91%).
Elevated creatinine suggests possible kidney involvement.
Extended ICU stay (18 days) indicates severe disease course."
```

---

## Data Integrity

### Quality Checks (Run before training)

```bash
python validate_dataset.py
```

Checks:
- ✓ Binary labels [0, 1]
- ✓ Ordinal risk_tier [0, 1, 2]
- ✓ All series have ≥1 label
- ✓ No unexpected null values
- ✓ Label distribution reasonable

### Expected Output

```
╔════════════════════════════════════════════╗
║   INTEGRITY CHECK: CT Cohort               ║
╠════════════════════════════════════════════╣
║ ✓ Labels binary                            ║
║ ✓ Risk tier valid                          ║
║ ✓ Risk factors binary                      ║
║ ✓ Label coverage: 2,287/2,287 (100%)      ║
╠════════════════════════════════════════════╣
║ Summary: 4/4 checks passed                 ║
║ ✓ Dataset is ready for training            ║
╚════════════════════════════════════════════╝
```

---

## Using the Dataset

### For Disease Classification

#### Setup

```python
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

# Load
df = pd.read_csv("data/cohort_ct.csv")

# Define labels
IMAGING_LABELS = [
    "covid", "pneumonia", "effusion", "fibrosis", "emphysema",
    "atelectasis", "pneumotharax", "pulm_embolism", "ards", "pulm_edema"
]

# Extract
X = df[["object_id", "modality"]].values
y = df[IMAGING_LABELS].values  # Shape: (N, 10) — binary multi-hot

# Split (stratify by risk_tier to preserve distribution)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42,
    stratify=df["risk_tier"]  # Keep risk tiers balanced
)
```

#### Model Training

```python
import torch
import torch.nn as nn

# Multi-label classifier (10 outputs, sigmoid activation)
model = nn.Sequential(
    nn.Linear(2048, 1024),  # From encoder
    nn.ReLU(),
    nn.Dropout(0.5),
    nn.Linear(1024, 512),
    nn.ReLU(),
    nn.Dropout(0.5),
    nn.Linear(512, 10),     # 10 disease labels
    nn.Sigmoid()            # Per-label probability
)

# Loss: Binary Cross-Entropy (no class weighting needed due to balancing)
criterion = nn.BCELoss()

# Training
for epoch in range(50):
    outputs = model(features)
    loss = criterion(outputs, y_train)
    loss.backward()
    optimizer.step()
```

### For Risk Assessment

#### Setup

```python
# Ordinal regression target
y_tier = df["risk_tier"].values  # [0, 1, 2]

# Individual risk factors (for narrative)
risk_factors = [
    "age_elderly", "age_very_elderly", "bmi_obese", "bmi_high",
    "high_o2_requirement", "low_o2_saturation", "high_sofa",
    "high_news2", "elevated_creatinine", "prolonged_hospitalization"
]
y_factors = df[risk_factors].values  # Shape: (N, 10)

# Clinical metadata (context for LLM)
metadata = df[["age_at_index", "sex", "o2_saturation", "sofa_score"]]
```

#### Model Training

```python
# Ordinal regression (3 classes)
model = nn.Sequential(
    nn.Linear(2048, 512),
    nn.ReLU(),
    nn.Dropout(0.3),
    nn.Linear(512, 3),  # Logits for [0, 1, 2]
)

# Loss: Cross-Entropy (could also use ordinal regression loss)
criterion = nn.CrossEntropyLoss()
```

#### Narrative Generation

```python
def generate_risk_narrative(model_output_tier, risk_factors, metadata):
    """Generate clinical narrative from model predictions."""
    
    tier_names = {0: "mild", 1: "moderate", 2: "severe"}
    risk_narrative = f"Clinical risk: {tier_names[model_output_tier]}\n"
    
    if risk_factors["age_very_elderly"]:
        risk_narrative += "Extreme age (>80) is a significant risk factor. "
    elif risk_factors["age_elderly"]:
        risk_narrative += "Elderly patient (>65) with increased baseline risk. "
    
    if risk_factors["high_o2_requirement"]:
        risk_narrative += "Significant hypoxemia requiring high-flow oxygen. "
    
    if risk_factors["high_sofa"]:
        risk_narrative += "Elevated SOFA score suggests multi-organ involvement. "
    
    if risk_factors["prolonged_hospitalization"]:
        risk_narrative += "Extended hospitalization indicates severe disease course. "
    
    return risk_narrative
```

---

## Dataset Statistics Reference

### Typical Distributions

#### CT Cohort (n ≈ 2,300)
- Unique cases: ~1,800-1,900 (some have multiple CT series)
- Multi-labeled: ~60% have 2+ labels
- Normal only: ~15-20%
- Risk distribution: 35% mild, 38% moderate, 27% severe

#### CXR Cohort (n ≈ 2,300)
- Unique cases: ~1,800-1,900
- Multi-labeled: ~55% have 2+ labels
- Normal only: ~18-22%
- Slightly lower PE prevalence (CXR less sensitive)

### Modality Comparison

| Feature | CT | CXR |
|---------|----|----|
| Sample size | ~2,300 | ~2,300 |
| COVID prev. | 12-15% | 11-14% |
| PE prev. | 10-12% | 3-5% |
| Fibrosis det. | Better | Limited |
| Cost/accessibility | Higher | Lower |
| Annotation quality | Higher | Lower |

---

## Advanced Features

### Using Continuous Risk Features

Combine binary risk factors with continuous measurements:

```python
# Create feature matrix combining discrete & continuous
continuous_features = df[[
    "age_at_index", "bmi", "o2_saturation", "sofa_score",
    "news2_score", "creatinine", "days_hospitalized"
]].fillna(df.mean())

# Standardize
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
continuous_features = scaler.fit_transform(continuous_features)

# Concatenate with binary factors
risk_feature_matrix = np.hstack([
    df[risk_factors].values,  # Binary
    continuous_features      # Continuous
])
```

### Class Weighting for Imbalanced Labels

If certain labels are underrepresented:

```python
from sklearn.utils.class_weight import compute_class_weight

# Per-label class weights
for i, label in enumerate(IMAGING_LABELS):
    weights = compute_class_weight(
        "balanced",
        classes=[0, 1],
        y=y_train[:, i]
    )
    # Use in loss: weighted_loss = weights[y] * ce_loss(y, pred)
```

### Handling Missing Values

```python
# Strategy 1: Drop rows with >30% missingness
missing_pct = df.isnull().sum() / len(df)
df_clean = df.loc[:, missing_pct < 0.3]

# Strategy 2: Impute with mean
df_filled = df.fillna(df.mean())

# Strategy 3: Create "missing" indicator column
df["o2_saturation_missing"] = df["o2_saturation"].isnull().astype(int)
df["o2_saturation"] = df["o2_saturation"].fillna(df["o2_saturation"].mean())
```

---

## Troubleshooting

### Issue: Slow export from Gen3

**Cause**: Network latency or API rate limiting  
**Fix**: 
- Run during off-peak hours
- Split export into modalities separately
- Cache TSV files locally after first run

### Issue: Missing observation data

**Cause**: Sparse clinical measurements in MIDRC  
**Fix**:
- Treat NaN as "unknown" or "not measured"
- Use forward-fill within patients over time
- Train with NaN-aware architectures (embeddings for missing)

### Issue: Class imbalance

**Cause**: Some labels (e.g., ARDS) naturally rare  
**Fix**:
- Already handled by sampling strategy (TIER_N dict)
- Can up-weight rare labels in loss
- Can use focal loss or class weights

### Issue: Data leakage

**Cause**: Multiple series from same patient in train/test  
**Fix**:
```python
# Split by CASE not series
train_cases = df.groupby("submitter_id").sample(frac=0.8, random_state=42)
train_idx = df["submitter_id"].isin(train_cases["submitter_id"])
X_train, y_train = X[train_idx], y[train_idx]
X_test, y_test = X[~train_idx], y[~train_idx]
```

---

## Next Steps

1. **Download imaging files**:
   ```bash
   gen3 drs-pull data/manifest_ct.json
   ```

2. **Integrate with modeling pipeline** (see `../modelling/dual_head_architecture.py`)

3. **Train disease head**:
   - Input: DICOM images or extracted features
   - Output: 10 binary labels
   - Loss: Binary cross-entropy
   - Metric: Area under PR curve (per label)

4. **Train risk head**:
   - Input: Patient features + imaging features (shared encoder)
   - Output A: risk_tier (ordinal 0-2)
   - Output B: 10 risk factors (binary)
   - Loss: Cross-entropy (tier) + BCE (factors)

5. **Deploy narrative generation**:
   - Use risk_tier + risk_factors as LLM prompt
   - Generate explainable clinical summary

---

## References

- **MIDRC**: https://data.midrc.org/
- **Gen3 SDK**: https://gen3.org/
- **ICD-10 codes**: https://www.cms.gov/Medicare/Coding-and-Billing/ICD-10-Codes/

---

**Last Updated**: 2026-05-28  
**Dataset Version**: v2 (multi-label + risk tiers)
