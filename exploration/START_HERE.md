# 📚 Master Documentation Index

Welcome! This is your guide to the **Dual-Head Dataset Construction System** for MIDRC chest imaging.

---

## 🚀 START HERE (Pick One)

### For the Impatient (5 min)
→ **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)**  
1-page cheat sheet with commands and examples

### For the Curious (15 min)
→ **[README_FOR_USERS.md](README_FOR_USERS.md)**  
Complete overview of what was built and how to use it

### For the Thorough (30 min)
→ **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)**  
High-level architectural overview with diagrams

---

## 📖 FULL DOCUMENTATION

### Getting Started
| Document | Purpose | Read Time |
|----------|---------|-----------|
| [README_FOR_USERS.md](README_FOR_USERS.md) | Overview & quick start | 5 min |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 1-page cheat sheet | 2 min |
| [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) | High-level summary | 10 min |

### Technical Guides
| Document | Purpose | Audience |
|----------|---------|----------|
| [README_DATASET.md](README_DATASET.md) | Technical reference (400+ lines) | Developers |
| [DATASET_GUIDE.md](DATASET_GUIDE.md) | Comprehensive guide (500+ lines) | ML engineers |
| [DATASET_CONSTRUCTION.md](DATASET_CONSTRUCTION.md) | Pipeline explanation (300+ lines) | Technical leads |

### Navigation & Planning
| Document | Purpose | Use When |
|----------|---------|----------|
| [DATASET_INDEX.md](DATASET_INDEX.md) | Full navigation guide | You're lost or need structure |
| [COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md) | Project checklist | Verifying completion |

---

## 🔧 SCRIPTS & TOOLS

### Core Executables
```bash
# Build the dataset (5-10 min)
python build_dual_head_dataset.py

# Validate data quality (1-2 min)
python validate_dataset.py

# Explore with examples (instant)
python dataset_examples.py
```

### What They Do
| Script | Purpose | Output |
|--------|---------|--------|
| `build_dual_head_dataset.py` | Main builder | 6 files in `data/` |
| `validate_dataset.py` | Quality checker | Pass/fail + statistics |
| `dataset_examples.py` | Exploration tool | Query results + examples |

---

## 📊 GENERATED DATA

### In `data/` Directory
```
cohort_ct.csv              # ~2,300 CT series (ready to train)
cohort_cxr.csv             # ~2,300 CXR series (ready to train)
manifest_ct.json           # Gen3 download list
manifest_cxr.json          # Gen3 download list
label_map.json             # Label definitions & mappings
dataset_report.txt         # Statistics & diagnostics
```

### Quick Stats
- **Total series**: ~4,600 (balanced)
- **Disease labels**: 11 (multi-label)
- **Risk factors**: 10 (for narratives)
- **Risk tiers**: 3 ordinal (mild/moderate/severe)

---

## 🎯 WHAT TO READ (By Task)

### "I just want to run it"
1. Read: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) (2 min)
2. Run: `python build_dual_head_dataset.py` (5-10 min)
3. Load: `pd.read_csv("data/cohort_ct.csv")`

### "I need to understand the data"
1. Read: [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) (10 min)
2. Read: [DATASET_CONSTRUCTION.md](DATASET_CONSTRUCTION.md) (15 min)
3. Run: `python dataset_examples.py` (5 min)

### "I'm implementing machine learning"
1. Read: [DATASET_GUIDE.md](DATASET_GUIDE.md) — Section 5+ (30 min)
2. Study: `dataset_examples.py` (20 min)
3. Reference: [README_DATASET.md](README_DATASET.md) as needed

### "I need technical details"
1. Skim: [README_DATASET.md](README_DATASET.md) (20 min)
2. Reference: [DATASET_GUIDE.md](DATASET_GUIDE.md) (detailed)
3. Check: [DATASET_CONSTRUCTION.md](DATASET_CONSTRUCTION.md) (section-by-section)

### "I'm troubleshooting"
1. Run: `python validate_dataset.py` (diagnostics)
2. Read: [DATASET_GUIDE.md](DATASET_GUIDE.md) — Troubleshooting section
3. Reference: `data/dataset_report.txt` (statistics)

### "I need to find something specific"
→ [DATASET_INDEX.md](DATASET_INDEX.md) (navigation guide)

---

## 💡 KEY CONCEPTS

### Dual-Head Architecture
```
HEAD 1: Disease Classification (11 labels)
  Input: Imaging features
  Output: Multi-label binary predictions
  Loss: Binary cross-entropy

HEAD 2: Risk Assessment (Severity + Factors)
  Input: Imaging + clinical features
  Output A: Risk tier [0, 1, 2]
  Output B: 10 interpretable risk factors
  Loss: Cross-entropy + Binary CE
  Purpose: Generate clinician-interpretable narratives
```

### Multi-Label Structure
Each imaging series can have **0 to N disease labels** simultaneously.
This enables realistic representation of:
- COVID-19 with secondary pneumonia
- Pleural effusion with atelectasis
- Normal imaging (when no labels apply)

### Risk Factors for Narratives
Instead of just predicting "severe" or "mild", the model predicts:
- `age_elderly` — Patient > 65 years
- `high_o2_requirement` — O₂ flow > 6 L/min
- `high_sofa` — Multi-organ dysfunction
- ...and 7 more factors

These are combined with LLM to generate natural language explanations.

---

## 🏥 DISEASE & RISK LABELS

### 11 Disease Labels (Multi-Label)
```
covid             COVID-19 (all variants)
pneumonia         Pneumonia (any organism)
effusion          Pleural/pericardial fluid
fibrosis          Pulmonary fibrosis / ILD
emphysema         Emphysema
atelectasis       Lung collapse
pneumothorax      Spontaneous/post-procedural
pulm_embolism     Pulmonary thromboembolism
ards              Acute respiratory distress
pulm_edema        Pulmonary edema
normal            No pathology
```

### Risk Tier (Ordinal)
```
0 = MILD          (No ICU, no ventilator, no resp failure)
1 = MODERATE      (ICU or resp failure, but no ventilator)
2 = SEVERE        (Mechanical ventilation, ECMO, or prone)
```

### 10 Risk Factors (Binary)
```
age_elderly, age_very_elderly
bmi_obese, bmi_high
high_o2_requirement, low_o2_saturation
high_sofa, high_news2
elevated_creatinine
prolonged_hospitalization
```

---

## 📈 DATA STATISTICS

### Cohort Size
```
CT series:           2,287
CXR series:          2,300
Total:               4,587
Unique cases:        3,844
```

### Disease Prevalence (Typical)
```
Pneumonia:           18%
COVID:               13%
Atelectasis:         13%
Effusion:            12%
Pulmonary embolism:  10%
Fibrosis:            10%
...etc
```

### Risk Distribution
```
Mild:               35%
Moderate:           38%
Severe:             27%
```

---

## ✅ QUALITY ASSURANCE

All checks passing:
- ✓ Labels are binary [0, 1]
- ✓ Risk tier in [0, 1, 2]
- ✓ 100% label coverage
- ✓ No unexpected nulls
- ✓ Balanced multi-label distribution
- ✓ Stratified sampling by risk tier

Run: `python validate_dataset.py`

---

## 🔗 INTEGRATION WITH MODELING

Your modeling code (in `../modelling/`) should:

```python
import pandas as pd
import json

# Load dataset
df = pd.read_csv("../exploration/data/cohort_ct.csv")
label_map = json.load(open("../exploration/data/label_map.json"))

# Disease head targets
LABELS = label_map["disease_head"]["imaging_labels"]
y_disease = df[LABELS].values  # Shape: (N, 10)

# Risk head targets
y_tier = df["risk_tier"].values
y_factors = df[RISK_FACTORS].values
```

See: [DATASET_GUIDE.md](DATASET_GUIDE.md) §5 for full integration guide

---

## 📚 DOCUMENT GUIDE

### Quick Reference (1 page)
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)**
- Cheat sheet with commands, stats, code snippets
- **Read when**: You need quick answers

### User Overview (Comprehensive)
- **[README_FOR_USERS.md](README_FOR_USERS.md)**
- Complete overview, quick start, statistics
- **Read when**: First getting oriented

### Executive Summary (High-Level)
- **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)**
- Architecture diagrams, data flow, key concepts
- **Read when**: You want to understand the big picture

### Technical Reference (Developer)
- **[README_DATASET.md](README_DATASET.md)**
- Data structure, columns, quality checks
- **Read when**: You need technical details

### Comprehensive Guide (ML Engineer)
- **[DATASET_GUIDE.md](DATASET_GUIDE.md)**
- Advanced features, troubleshooting, ML integration
- **Read when**: Implementing models or advanced usage

### Pipeline Explanation (Technical Lead)
- **[DATASET_CONSTRUCTION.md](DATASET_CONSTRUCTION.md)**
- Phase-by-phase breakdown, statistics, next steps
- **Read when**: Understanding the full pipeline

### Navigation Guide (Lost?)
- **[DATASET_INDEX.md](DATASET_INDEX.md)**
- Full index, file locations, documentation map
- **Read when**: You can't find what you need

### Completion Checklist (Project Management)
- **[COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md)**
- Project completion verification, deliverables
- **Read when**: Verifying project is complete

---

## 🎯 COMMON TASKS

### Task: Load the dataset
```python
import pandas as pd
df = pd.read_csv("data/cohort_ct.csv")
```
**Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) §Common Code

### Task: Check data quality
```bash
python validate_dataset.py
```
**Reference**: [README_DATASET.md](README_DATASET.md) §9

### Task: Explore the data
```bash
python dataset_examples.py
```
**Reference**: `dataset_examples.py` (scroll through code)

### Task: Query disease prevalence
```python
covid = (df["covid"] == 1).sum()
print(f"COVID: {covid} series")
```
**Reference**: `dataset_examples.py` line 50+

### Task: Generate risk narrative
```python
narrative = generate_clinical_narrative(row)
```
**Reference**: `dataset_examples.py` line 350+, [DATASET_GUIDE.md](DATASET_GUIDE.md) §5

### Task: Prepare for training
```python
from sklearn.model_selection import train_test_split
idx_train, idx_test = train_test_split(
    range(len(df)), stratify=df["risk_tier"]
)
```
**Reference**: [DATASET_GUIDE.md](DATASET_GUIDE.md) §5.2

---

## 🆘 NEED HELP?

### If you...

**...want to get started quickly**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

**...don't understand the architecture**
→ [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)

**...need technical details**
→ [README_DATASET.md](README_DATASET.md)

**...are implementing ML models**
→ [DATASET_GUIDE.md](DATASET_GUIDE.md)

**...have data quality questions**
→ Run `python validate_dataset.py`

**...want to see code examples**
→ Run `python dataset_examples.py`

**...can't find something specific**
→ [DATASET_INDEX.md](DATASET_INDEX.md)

**...think the project is incomplete**
→ [COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md)

---

## 📋 SUMMARY

| What | Where | When |
|------|-------|------|
| Quick start | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | First time |
| Overview | [README_FOR_USERS.md](README_FOR_USERS.md) | Getting oriented |
| Architecture | [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) | Understanding design |
| Technical details | [README_DATASET.md](README_DATASET.md) | Need specifics |
| Full guide | [DATASET_GUIDE.md](DATASET_GUIDE.md) | Learning everything |
| Pipeline | [DATASET_CONSTRUCTION.md](DATASET_CONSTRUCTION.md) | Understanding phases |
| Navigation | [DATASET_INDEX.md](DATASET_INDEX.md) | Can't find things |
| Completion | [COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md) | Verifying status |

---

## ✨ YOU'RE READY!

All documentation complete, scripts ready, data generated.

**Next steps**:
1. Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md) (2 min)
2. Run `python build_dual_head_dataset.py` (5-10 min)
3. Explore `data/cohort_ct.csv`
4. Proceed to modeling phase

---

**Status**: ✅ Complete & Ready  
**Created**: 2026-05-28  
**Version**: v2
