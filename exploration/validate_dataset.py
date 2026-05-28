"""
Dataset Validation & Exploration Tool
======================================
Quick utilities for understanding the dual-head dataset structure
and validating data integrity before training.

Usage:
    python validate_dataset.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATASETS
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path("data")

print("Loading datasets...\n")

df_ct = pd.read_csv(DATA_DIR / "cohort_ct.csv")
df_cxr = pd.read_csv(DATA_DIR / "cohort_cxr.csv")

with open(DATA_DIR / "label_map.json") as f:
    label_map = json.load(f)

print(f"✓ CT cohort:  {len(df_ct):,} series")
print(f"✓ CXR cohort: {len(df_cxr):,} series")
print(f"✓ Label map loaded\n")

# ══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

IMAGING_LABELS = ["covid", "pneumonia", "effusion", "fibrosis", "emphysema",
                  "atelectasis", "pneumothorax", "pulm_embolism", "ards", "pulm_edema"]

RISK_FACTORS = ["age_elderly", "age_very_elderly", "bmi_obese", "bmi_high",
                "high_o2_requirement", "low_o2_saturation", "high_sofa",
                "high_news2", "elevated_creatinine", "prolonged_hospitalization"]


def validate_labels(df: pd.DataFrame, name: str):
    """Check label columns are binary [0, 1]."""
    print(f"\n{'='*70}")
    print(f"LABEL VALIDATION: {name}")
    print(f"{'='*70}")
    
    issues = []
    for label in IMAGING_LABELS + ["normal"]:
        if label not in df.columns:
            issues.append(f"  ✗ Missing label column: {label}")
            continue
        
        unique_vals = df[label].dropna().unique()
        if not set(unique_vals).issubset({0, 1}):
            issues.append(f"  ✗ {label}: non-binary values {unique_vals}")
    
    if issues:
        for issue in issues:
            print(issue)
        return False
    else:
        print("✓ All labels are binary [0, 1]")
        return True


def validate_risk_tier(df: pd.DataFrame, name: str):
    """Check risk_tier is ordinal [0, 1, 2]."""
    print(f"\n{'='*70}")
    print(f"RISK TIER VALIDATION: {name}")
    print(f"{'='*70}")
    
    if "risk_tier" not in df.columns:
        print("✗ Missing risk_tier column")
        return False
    
    unique_vals = df["risk_tier"].dropna().unique()
    if not set(unique_vals).issubset({0, 1, 2}):
        print(f"✗ Non-ordinal values: {unique_vals}")
        return False
    
    print("✓ risk_tier values are ordinal [0, 1, 2]")
    dist = df["risk_tier"].value_counts().sort_index()
    print(f"  Distribution: {dict(dist)}")
    return True


def validate_risk_factors(df: pd.DataFrame, name: str):
    """Check risk_factors are binary."""
    print(f"\n{'='*70}")
    print(f"RISK FACTORS VALIDATION: {name}")
    print(f"{'='*70}")
    
    issues = []
    for rf in RISK_FACTORS:
        if rf not in df.columns:
            issues.append(f"  ✗ Missing risk factor: {rf}")
            continue
        
        unique_vals = df[rf].dropna().unique()
        if not set(unique_vals).issubset({0, 1}):
            issues.append(f"  ✗ {rf}: non-binary values {unique_vals}")
    
    if issues:
        for issue in issues:
            print(issue)
        return False
    else:
        print("✓ All risk factors are binary [0, 1]")
        return True


def check_label_coverage(df: pd.DataFrame, name: str):
    """Ensure all cases have at least one label."""
    print(f"\n{'='*70}")
    print(f"LABEL COVERAGE: {name}")
    print(f"{'='*70}")
    
    label_cols = IMAGING_LABELS + ["normal"]
    available_labels = [c for c in label_cols if c in df.columns]
    
    cases_with_labels = (df[available_labels].sum(axis=1) > 0).sum()
    total_cases = len(df)
    coverage = 100 * cases_with_labels / total_cases
    
    if coverage == 100:
        print(f"✓ All {total_cases:,} series have ≥1 label ({coverage:.1f}%)")
    else:
        print(f"⚠ Only {cases_with_labels:,}/{total_cases:,} series have ≥1 label ({coverage:.1f}%)")
        orphan_idx = (df[available_labels].sum(axis=1) == 0)
        print(f"  {orphan_idx.sum()} unlabeled series")
    
    return coverage == 100


def check_multilabel_structure(df: pd.DataFrame, name: str):
    """Analyze label co-occurrence and multi-label distribution."""
    print(f"\n{'='*70}")
    print(f"MULTI-LABEL STRUCTURE: {name}")
    print(f"{'='*70}")
    
    label_cols = IMAGING_LABELS + ["normal"]
    available_labels = [c for c in label_cols if c in df.columns]
    
    n_labels_per_series = df[available_labels].sum(axis=1)
    
    print(f"Labels per series (excluding 'normal'):")
    for n in sorted(n_labels_per_series.unique()):
        count = (n_labels_per_series == n).sum()
        pct = 100 * count / len(df)
        print(f"  {n} labels: {count:>5} ({pct:>5.1f}%)")
    
    print(f"\nLabel prevalence:")
    for label in available_labels:
        count = df[label].sum()
        pct = 100 * count / len(df)
        print(f"  {label:<20}: {count:>5} ({pct:>5.1f}%)")


def check_demographics(df: pd.DataFrame, name: str):
    """Validate demographic columns."""
    print(f"\n{'='*70}")
    print(f"DEMOGRAPHICS: {name}")
    print(f"{'='*70}")
    
    # Age
    if "age_at_index" in df.columns:
        age_valid = pd.to_numeric(df["age_at_index"], errors="coerce")
        age_valid = age_valid[age_valid.notna()]
        if len(age_valid) > 0:
            print(f"Age (n={len(age_valid):,}):")
            print(f"  mean: {age_valid.mean():.1f}, median: {age_valid.median():.1f}")
            print(f"  range: [{age_valid.min():.0f}, {age_valid.max():.0f}]")
            missing = len(df) - len(age_valid)
            if missing > 0:
                print(f"  missing: {missing} ({100*missing/len(df):.1f}%)")
    
    # Sex
    if "sex" in df.columns:
        print(f"\nSex distribution:")
        sex_dist = df["sex"].value_counts()
        for sex, count in sex_dist.items():
            pct = 100 * count / len(df)
            print(f"  {str(sex):<20}: {count:>5} ({pct:>5.1f}%)")
        missing = df["sex"].isna().sum()
        if missing > 0:
            print(f"  missing: {missing} ({100*missing/len(df):.1f}%)")
    
    # COVID status
    if "covid19_positive" in df.columns:
        print(f"\nCOVID-19 status (case-level):")
        covid_dist = df["covid19_positive"].value_counts()
        for status, count in covid_dist.items():
            pct = 100 * count / len(df)
            print(f"  {str(status):<20}: {count:>5} ({pct:>5.1f}%)")


def check_clinical_data(df: pd.DataFrame, name: str):
    """Check clinical measurement columns."""
    print(f"\n{'='*70}")
    print(f"CLINICAL DATA: {name}")
    print(f"{'='*70}")
    
    clinical_cols = ["o2_saturation", "o2_flow_rate", "bmi", "sofa_score",
                     "news2_score", "heart_rate", "respiratory_rate",
                     "temperature", "sbp", "dbp", "creatinine"]
    
    for col in clinical_cols:
        if col in df.columns:
            valid = pd.to_numeric(df[col], errors="coerce")
            valid = valid[valid.notna()]
            n_missing = len(df) - len(valid)
            
            if len(valid) > 0:
                print(f"\n{col}:")
                print(f"  n: {len(valid):,}")
                print(f"  mean: {valid.mean():.2f}, median: {valid.median():.2f}")
                print(f"  range: [{valid.min():.2f}, {valid.max():.2f}]")
            else:
                print(f"\n{col}: ALL MISSING")
            
            if n_missing > 0:
                print(f"  missing: {n_missing} ({100*n_missing/len(df):.1f}%)")


def check_procedures(df: pd.DataFrame, name: str):
    """Check treatment procedure flags."""
    print(f"\n{'='*70}")
    print(f"PROCEDURES: {name}")
    print(f"{'='*70}")
    
    proc_cols = [c for c in df.columns if c.startswith("proc_")]
    
    if not proc_cols:
        print("No procedure columns found")
        return
    
    for proc in sorted(proc_cols):
        if proc in df.columns:
            count = df[proc].sum()
            pct = 100 * count / len(df)
            print(f"  {proc:<35}: {count:>5} ({pct:>5.1f}%)")


def check_modality_distribution(df_ct: pd.DataFrame, df_cxr: pd.DataFrame):
    """Compare CT and CXR cohorts."""
    print(f"\n{'='*70}")
    print(f"MODALITY COMPARISON")
    print(f"{'='*70}")
    
    print(f"\nCT vs CXR cohort sizes:")
    print(f"  CT:  {len(df_ct):,} series")
    print(f"  CXR: {len(df_cxr):,} series")
    print(f"  Total: {len(df_ct) + len(df_cxr):,} series")
    
    print(f"\nLabel comparison (% of cohort):")
    for label in IMAGING_LABELS + ["normal"]:
        if label in df_ct.columns and label in df_cxr.columns:
            ct_pct = 100 * df_ct[label].sum() / len(df_ct)
            cxr_pct = 100 * df_cxr[label].sum() / len(df_cxr)
            print(f"  {label:<20}: CT={ct_pct:>5.1f}%, CXR={cxr_pct:>5.1f}%")


def check_for_nulls(df: pd.DataFrame, name: str):
    """Identify missing/null values."""
    print(f"\n{'='*70}")
    print(f"NULL VALUES: {name}")
    print(f"{'='*70}")
    
    null_counts = df.isnull().sum()
    null_counts = null_counts[null_counts > 0].sort_values(ascending=False)
    
    if len(null_counts) == 0:
        print("✓ No null values found")
    else:
        print(f"Columns with missing data:")
        for col, n_null in null_counts.items():
            pct = 100 * n_null / len(df)
            print(f"  {col:<35}: {n_null:>5} ({pct:>5.1f}%)")


def integrity_check(df: pd.DataFrame, name: str):
    """Run full integrity check."""
    print(f"\n{'='*70}")
    print(f"INTEGRITY CHECK: {name}")
    print(f"{'='*70}")
    
    checks = {
        "Labels binary": validate_labels(df, name),
        "Risk tier valid": validate_risk_tier(df, name),
        "Risk factors binary": validate_risk_factors(df, name),
        "Label coverage": check_label_coverage(df, name),
    }
    
    passed = sum(checks.values())
    total = len(checks)
    
    print(f"\n{'─'*70}")
    print(f"Summary: {passed}/{total} checks passed")
    if passed == total:
        print("✓ Dataset is ready for training")
    else:
        print("⚠ Review issues above before training")
    
    return passed == total


# ══════════════════════════════════════════════════════════════════════════════
# MAIN VALIDATION FLOW
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("DATASET VALIDATION & EXPLORATION")
    print("=" * 70)
    
    # Run full integrity checks
    ct_ok = integrity_check(df_ct, "CT Cohort")
    cxr_ok = integrity_check(df_cxr, "CXR Cohort")
    
    # Detailed exploration
    check_multilabel_structure(df_ct, "CT")
    check_multilabel_structure(df_cxr, "CXR")
    
    check_demographics(df_ct, "CT")
    check_demographics(df_cxr, "CXR")
    
    check_clinical_data(df_ct, "CT")
    check_procedures(df_ct, "CT")
    
    check_modality_distribution(df_ct, df_cxr)
    
    check_for_nulls(df_ct, "CT")
    check_for_nulls(df_cxr, "CXR")
    
    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)
    
    if ct_ok and cxr_ok:
        print("\n✓ Dataset is ready for training")
    else:
        print("\n⚠ Please review issues above")
