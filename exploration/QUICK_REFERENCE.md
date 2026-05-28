# QUICK REFERENCE — Dual-Head Dataset

## 🚀 Quick Start (5 minutes)

```bash
cd exploration

# 1. Build dataset
python build_dual_head_dataset.py

# 2. Validate
python validate_dataset.py

# 3. Explore
python dataset_examples.py
```

**Output**: 6 files in `data/` directory

---

## 📊 Dataset Basics

| Component | Details |
|-----------|---------|
| **CT series** | ~2,200-2,500 |
| **CXR series** | ~2,200-2,500 |
| **Total** | ~4,400-5,000 series |
| **Unique cases** | ~3,800 |
| **Disease labels** | 11 (multi-label) |
| **Risk factors** | 10 (binary) |
| **Risk tiers** | 3 (ordinal: 0=mild, 1=moderate, 2=severe) |

---

## 🏥 Disease Labels (HEAD 1)

**Multi-label binary targets** — each series can have 0 to N labels

| Label | % of Cohort | ICD-10 Examples |
|-------|-------------|-----------------|
| covid | 12-15% | U07.1, COVID-19 |
| pneumonia | 15-20% | All organism types |
| effusion | 10-15% | Pleural/pericardial |
| atelectasis | 10-15% | Lung collapse |
| fibrosis | 8-12% | IPF, sarcoidosis, ILD |
| pulm_embolism | 8-12% | PE, DVT sequelae |
| pneumothorax | 5-10% | Spontaneous/post-proc |
| emphysema | 5-8% | All subtypes |
| ards | 3-5% | ARDS |
| pulm_edema | 3-5% | Pulmonary edema |
| normal | 15-20% | No pathology |

---

## ⚠️ Risk Assessment (HEAD 2)

### Risk Tier (Ordinal)
```
0 = MILD      (no ICU, no vent, no resp failure)
1 = MODERATE  (ICU OR resp failure, but no vent)
2 = SEVERE    (mechanical vent OR ECMO OR prone)
```

**Distribution**: ~35% mild, ~38% moderate, ~27% severe

### Risk Factors (For Narratives)
```
✓ age_elderly         — > 65 years
✓ age_very_elderly    — > 80 years
✓ bmi_obese           — BMI > 30
✓ bmi_high            — BMI > 25
✓ high_o2_requirement — O₂ flow > 6 L/min
✓ low_o2_saturation   — SpO₂ < 94%
✓ high_sofa           — SOFA ≥ 6
✓ high_news2          — NEWS2 ≥ 5
✓ elevated_creatinine — Creatinine > 1.5
✓ prolonged_hosp      — LOS > 14 days
```

---

## 📁 Generated Files

```
data/
├── cohort_ct.csv              ← Load for CT training
├── cohort_cxr.csv             ← Load for CXR training
├── manifest_ct.json           ← Gen3 download list
├── manifest_cxr.json          ← Gen3 download list
├── label_map.json             ← Label definitions
└── dataset_report.txt         ← Statistics
```

---

## 🔧 Common Code Snippets

### Load Dataset
```python
import pandas as pd

df = pd.read_csv("data/cohort_ct.csv")
print(f"Loaded {len(df)} series")
```

### Get Disease Labels
```python
LABELS = ["covid", "pneumonia", "effusion", "fibrosis", 
          "emphysema", "atelectasis", "pneumothorax", 
          "pulm_embolism", "ards", "pulm_edema"]

y = df[LABELS].values  # Shape: (N, 10)
```

### Get Risk Targets
```python
y_tier = df["risk_tier"].values           # [0, 1, 2]
y_factors = df[["age_elderly", "bmi_obese", ...]].values  # Binary
```

### Query Examples
```python
# How many COVID?
covid_count = (df["covid"] == 1).sum()

# Severe + elderly?
high_risk = df[(df["risk_tier"] == 2) & (df["age_elderly"] == 1)]

# Multi-labeled?
n_labels = df[LABELS].sum(axis=1)
multi = (n_labels >= 2).sum()
```

### Train/Test Split (Stratified)
```python
from sklearn.model_selection import train_test_split

idx_train, idx_test = train_test_split(
    range(len(df)), test_size=0.2, random_state=42,
    stratify=df["risk_tier"]  # Preserve distribution
)
```

---

## 🎯 Model Integration

### HEAD 1: Disease Classification
```python
# Input: Image features (from encoder)
# Output: 10 probabilities (sigmoid)
# Loss: Binary cross-entropy
# Metric: AUROC per label
```

### HEAD 2: Risk Assessment
```python
# Input: Image features + clinical features
# Output A: Risk tier (3-class, softmax)
# Output B: Risk factors (10 binary, sigmoid)
# Loss: Cross-entropy (tier) + BCE (factors)
```

---

## ✅ Data Quality Checks

Run before training:
```bash
python validate_dataset.py
```

Expected results:
- ✓ All labels binary [0, 1]
- ✓ All risk_tier in [0, 1, 2]
- ✓ 100% label coverage
- ✓ <5% missing values
- ✓ Balanced risk tier distribution

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| `README_DATASET.md` | Technical reference |
| `DATASET_GUIDE.md` | Comprehensive walkthrough |
| `DATASET_CONSTRUCTION.md` | Pipeline overview |
| `dataset_examples.py` | Code examples |

---

## 🔍 Key Statistics

### Age
- Mean: ~60 years
- Median: ~62 years
- Range: [18, 95]
- Elderly (>65): ~40%

### Sex
- Male: ~50%
- Female: ~50%

### Risk Distribution
- Mild: ~35%
- Moderate: ~38%
- Severe: ~27%

### Multi-label
- Normal only: ~18%
- 1 label: ~22%
- 2 labels: ~30%
- 3+ labels: ~30%

---

## ⚙️ Advanced Features

### Continuous Measurements Available
- O₂ saturation, heart rate, respiratory rate
- Temperature, blood pressure (systolic/diastolic)
- BMI, creatinine, SOFA score, NEWS2 score
- Length of stay (hospital, ICU, ventilator)

### Treatment Procedures
- Mechanical ventilation, intubation, ECMO
- High-flow nasal cannula, non-invasive ventilation
- Vasopressors, prone positioning
- Anticoagulation, immunotherapy, antivirals

### Series-Level Annotations
- mRALE score (0-8, imaging severity)
- COVID pneumonia classification
- Airspace disease grading

---

## 🚨 Common Issues

| Issue | Solution |
|-------|----------|
| Slow export | Run off-peak or cache TSV locally |
| Missing clinical data | Expected; treat NaN as "unknown" |
| Class imbalance | Already handled by sampling strategy |
| Data leakage | Split by case_id, not series_id |
| Low prevalence labels | Use weighted sampling or focal loss |

---

## 📌 Key Concepts

**Multi-Label**: Series can have multiple diseases simultaneously  
**Binary Encoding**: [0,1] for each label  
**Ordinal Regression**: Respects ordering (mild < moderate < severe)  
**Risk Factors**: Thresholded clinical measurements for narratives  
**Stratification**: Preserves risk tier distribution in train/test split  

---

## 🎓 Next Steps

1. ✅ Build & validate dataset (done)
2. ⬜ Download images via Gen3
3. ⬜ Preprocess (DICOM → tensors)
4. ⬜ Implement dual-head model
5. ⬜ Train disease head (BCE loss)
6. ⬜ Train risk head (CE + BCE loss)
7. ⬜ Integrate LLM for narratives
8. ⬜ Evaluate on test set

---

**Created**: 2026-05-28  
**Dataset Version**: v2 (multi-label + risk)  
**Total Series**: ~4,500  
**Status**: Ready for training
