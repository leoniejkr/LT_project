"""
MIDRC Chest Disease Classification Dataset Builder
====================================================
Constructs a multi-label classification dataset for chest CT and CXR imaging.

  PRIMARY LABELS  (imaging targets — what the model classifies):
    covid              — COVID-19 (own label; large class, distinct GGO phenotype)
    bacterial_pneumonia — Lobar/bronchopneumonia, gram-positive/-negative, MRSA/MSSA/Pseudomonas
    viral_pneumonia    — Viral/atypical pneumonia excl. COVID (RSV, metapneumovirus, influenza, etc.)
    lung_abscess       — Lung abscess (with/without pneumonia), necrotizing pneumonia, gangrene of lung
    emphysema_copd     — COPD (all subtypes) + emphysema (centrilobular, panlobular, unspecified)
    ild_fibrosis       — ILD / pulmonary fibrosis (IPF, NSIP, sarcoidosis, hypersensitivity pneumonitis,
                         autoimmune-ILD, drug/radiation ILD, asbestosis, pneumoconiosis)
    pleural_effusion   — Pleural effusion (all types), empyema, hemothorax, chylothorax
    pneumothorax       — Pneumothorax (spontaneous, tension, postprocedural)
    atelectasis        — Atelectasis / lobar collapse
    pulm_embolism      — Pulmonary embolism (acute, chronic, saddle, septic)
    ards               — ARDS / acute respiratory failure with hypoxia (non-cardiogenic)
    lung_malignancy    — Primary / secondary thoracic malignancy
    normal             — No primary imaging label (derived flag)

  METADATA LABELS  (tabular side-channel features — NOT training targets):
    meta_heart_failure   — All forms of heart failure (influences CXR vascular markings)
    meta_pulm_htn        — Pulmonary arterial/venous hypertension, cor pulmonale
    meta_cardiomegaly    — Cardiomegaly / cardiomyopathy (visible on CXR)
    meta_pulm_edema      — Cardiogenic pulmonary oedema
    meta_arrhythmia      — AF, flutter, VT/VF, AV block, bradycardia
    meta_cad             — Coronary artery disease / MI / ischaemic heart disease
    meta_valvular        — Valvular heart disease / endocarditis / cardiac tamponade
    meta_hypertension    — Essential / secondary systemic hypertension
    meta_diabetes        — Diabetes mellitus (all types)
    meta_renal           — Chronic kidney disease / renal failure
    meta_aortic_disease  — Thoracic aortic aneurysm / dissection / ectasia
    meta_autoimmune      — Systemic autoimmune disease (SLE, scleroderma, Wegener's/GPA,
                           polymyositis, dermatomyositis, Sjogren's)
    meta_transplant      — Lung or heart transplant status (alters anatomy; raises infection risk)
    meta_tb_ntm          — Tuberculosis (active/latent) or NTM/MAC infection
    meta_bronchiectasis  — Bronchiectasis / cystic fibrosis with pulmonary manifestations

  OUTPUTS (in ./data/):
    cohort_ct.csv            — CT  series with all labels & metadata
    cohort_cxr.csv           — CXR series with all labels & metadata
    manifest_ct.json         — Gen3 download manifest (CT)
    manifest_cxr.json        — Gen3 download manifest (CXR)
    label_map.json           — full label & feature definitions
    dataset_report.txt       — statistics & diagnostics
    preprocessed/ct/         — MONAI-preprocessed CT volumes (.nii.gz)
    preprocessed/cxr/        — MONAI-preprocessed CXR arrays (.npy)

  PIPELINE:
    1.  Authenticate & export Gen3 nodes
    2.  Filter to chest-region series via LOINC codes
    3.  Build multi-label disease columns from condition node (ICD-10 mapping)
    4.  Build metadata comorbidity columns from condition node
    5.  Merge demographics from case node
    6.  Balanced cohort sampling across primary labels
    7.  MONAI preprocessing for CT (HU windowing → resize → normalize)
        and CXR (CLAHE → resize → normalize)
    8.  Export CSVs, manifests, label_map, report
"""

import io
import json
import os
import sys
import logging
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

# ── optional MONAI import (skipped gracefully if unavailable) ────────────────
try:
    import monai
    from monai.transforms import (
        Compose,
        LoadImage,
        EnsureChannelFirst,
        Orientation,
        Spacing,
        ScaleIntensityRangePercentiles,
        CropForeground,
        Resize,
        NormalizeIntensity,
        Lambda,
    )
    from monai.data import ITKReader
    MONAI_AVAILABLE = True
except ImportError:
    MONAI_AVAILABLE = False
    logging.warning(
        "MONAI not installed — image preprocessing will be skipped. "
        "Install with: pip install monai[itk,nibabel,pillow]"
    )

try:
    from gen3.auth import Gen3Auth
    from gen3.submission import Gen3Submission
except ImportError:
    print("ERROR: gen3 package not found. Install with: pip install gen3")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
# ==============================================================================
# 0. CONFIGURATION (UPDATED FOR MULTI-PROJECT)
# ==============================================================================

API        = "https://data.midrc.org"
PROGRAM    = "Open"
PROJECTS   = ["R1", "A1"]  # Dual-project ingestion
OUTPUT_DIR = Path("data")
PREP_DIR   = OUTPUT_DIR / "preprocessed"
RANDOM_SEED = 42

OUTPUT_DIR.mkdir(exist_ok=True)
(PREP_DIR / "ct").mkdir(parents=True, exist_ok=True)
(PREP_DIR / "cxr").mkdir(parents=True, exist_ok=True)

# ── MONAI preprocessing parameters (Guarantees definition scope) ──────────────
CT_TARGET_SPACING   = (1.5, 1.5, 2.0)   # mm  (x, y, z)
CT_TARGET_SHAPE     = (224, 224, 96)     # voxels after resize
CT_HU_WIN_LOW       = -1000             # air
CT_HU_WIN_HIGH      = 400               # soft tissue / mild bone
CXR_TARGET_SHAPE    = (224, 224)        # pixels (H, W)

# ── Dynamic Sampler Limit ────────────────────────────────────────────────────
TARGET_MAX_PER_CLASS = 500  # Cap majority classes to prevent balancing issues

print("=" * 80)
print("MIDRC Chest Disease Cross-Project Dataset Builder")
print("=" * 80)

# ==============================================================================
# 1. AUTH & CROSS-PROJECT EXPORT
# ==============================================================================

try:
    auth = Gen3Auth(API, refresh_file="credentials.json")
    sub  = Gen3Submission(API, auth)
    log.info(f"Connected to {API}")
except Exception as e:
    log.error(f"Authentication failed: {e}")
    sys.exit(1)

print("\n" + "─" * 80)
print("1. Exporting and merging Gen3 nodes from R1 and A1 …")
print("─" * 80)

# Temporary lists to hold dataframes from each project tier
cases_list, ct_list, cr_list, study_list, cond_list = [], [], [], [], []

for proj in PROJECTS:
    print(f"  Fetching nodes for project: {PROGRAM}-{proj}...")
    try:
        c_raw  = sub.export_node(PROGRAM, proj, "case",            "tsv")
        ct_raw = sub.export_node(PROGRAM, proj, "ct_series_file",  "tsv")
        cr_raw = sub.export_node(PROGRAM, proj, "cr_series_file",  "tsv")
        s_raw  = sub.export_node(PROGRAM, proj, "imaging_study",   "tsv")
        co_raw = sub.export_node(PROGRAM, proj, "condition",       "tsv")
        
        # Append dataframes, appending a project tracking column for auditing
        df_c = pd.read_csv(io.StringIO(c_raw), sep="\t")
        df_c["origin_project"] = proj
        cases_list.append(df_c)
        
        ct_list.append(pd.read_csv(io.StringIO(ct_raw), sep="\t", low_memory=False))
        cr_list.append(pd.read_csv(io.StringIO(cr_raw), sep="\t", low_memory=False))
        study_list.append(pd.read_csv(io.StringIO(s_raw), sep="\t", low_memory=False))
        cond_list.append(pd.read_csv(io.StringIO(co_raw), sep="\t"))
        
    except Exception as e:
        log.error(f"Failed to export node from project {proj}: {e}")
        sys.exit(1)

# Concatenate all project pools into global tracking tables
df_cases = pd.concat(cases_list, ignore_index=True).drop_duplicates("submitter_id")
df_ct    = pd.concat(ct_list, ignore_index=True).drop_duplicates("object_id")
df_cr    = pd.concat(cr_list, ignore_index=True).drop_duplicates("object_id")
df_study = pd.concat(study_list, ignore_index=True).drop_duplicates("study_uid")
df_cond  = pd.concat(cond_list, ignore_index=True) # Multi-row per case, keep duplicates here

print(f"\nGlobal Combined Pool Statistics:")
print(f"  Total unique cases:        {len(df_cases):,}")
print(f"  Total unique ct_series:    {len(df_ct):,}")
print(f"  Total unique cr_series:    {len(df_cr):,}")
print(f"  Total unique imaging_study:{len(df_study):,}")
print(f"  Total conditions rows:     {len(df_cond):,}")
# ══════════════════════════════════════════════════════════════════════════════
# 2. HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def clean_case_id(s: str) -> str:
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

def coerce_int(val) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0

# ══════════════════════════════════════════════════════════════════════════════
# 3. LOINC FILTER — chest region only
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

print(f"\n✓ Chest filter: CT={len(df_chest_ct):,}, CXR={len(df_chest_cxr):,}")

# ══════════════════════════════════════════════════════════════════════════════
# 4. ICD-10 → LABEL MAP
# ══════════════════════════════════════════════════════════════════════════════
#
# Two tiers:
#   PRIMARY_LABELS  — direct imaging targets used as training labels
#   METADATA_LABELS — comorbidities / tabular side-channel features (not trained on)
#
# Condition strings are verified against available_conditions.txt from MIDRC.
# Label priority for ambiguous conditions (applied during case-level assembly):
#   covid > bacterial_pneumonia > viral_pneumonia > lung_abscess
#   (each condition maps to exactly one label; overlapping cases are multi-label
#    at the case level — a COVID patient can also have atelectasis, etc.)
#
# ════════════════════════════════════════════════════════════════════════════

CONDITION_PRIMARY_MAP: dict[str, str] = {

    # ── COVID-19 ─────────────────────────────────────────────────────────────
    # Own label: 25,000+ cases in MIDRC, distinct GGO/crazy-paving CT phenotype.
    # "Pneumonia due to coronavirus disease 2019" → covid (not viral_pneumonia).
    "COVID-19":                                                         "covid",
    "Emergency use of U07.1 | COVID-19":                               "covid",
    "Pneumonia due to coronavirus disease 2019":                        "covid",
    "Post COVID-19 condition, unspecified":                             "covid",
    "SARS-associated coronavirus as the cause of diseases classified elsewhere": "covid",
    "Pneumonia due to SARS-associated coronavirus":                     "covid",

    # ── Bacterial pneumonia / consolidation ──────────────────────────────────
    # Lobar consolidation pattern. Includes gram-positive, gram-negative,
    # MRSA/MSSA, Pseudomonas, Klebsiella, aspiration pneumonitis (food/vomit
    # causes consolidation indistinguishable from bacterial pneumonia on imaging).
    "Pneumonia, unspecified organism":                                  "bacterial_pneumonia",
    "Pneumonia, organism unspecified":                                  "bacterial_pneumonia",
    "Lobar pneumonia, unspecified organism":                            "bacterial_pneumonia",
    "Unspecified bacterial pneumonia":                                  "bacterial_pneumonia",
    "Bronchopneumonia, unspecified organism":                           "bacterial_pneumonia",
    "Pneumonia due to Pseudomonas":                                     "bacterial_pneumonia",
    "Pneumonia due to Klebsiella pneumoniae":                           "bacterial_pneumonia",
    "Pneumonia due to Methicillin susceptible Staphylococcus aureus":   "bacterial_pneumonia",
    "Pneumonia due to Methicillin resistant Staphylococcus aureus":     "bacterial_pneumonia",
    "Pneumonia due to other Gram-negative bacteria":                    "bacterial_pneumonia",
    "Pneumonia due to Escherichia coli":                                "bacterial_pneumonia",
    "Pneumonia due to Hemophilus influenzae":                           "bacterial_pneumonia",
    "Pneumonia due to Streptococcus pneumoniae":                        "bacterial_pneumonia",
    "Pneumonia due to other streptococci":                              "bacterial_pneumonia",
    "Pneumonia due to other specified bacteria":                        "bacterial_pneumonia",
    "Pneumonia due to other staphylococcus":                            "bacterial_pneumonia",
    "Pneumonia due to staphylococcus, unspecified":                     "bacterial_pneumonia",
    "Pneumonia due to other specified infectious organisms":            "bacterial_pneumonia",
    "Pneumonia due to other specified organism":                        "bacterial_pneumonia",
    "Ventilator associated pneumonia":                                  "bacterial_pneumonia",
    "Hypostatic pneumonia, unspecified organism":                       "bacterial_pneumonia",
    "Other pneumonia, unspecified organism":                            "bacterial_pneumonia",
    "Pneumonia in diseases classified elsewhere":                       "bacterial_pneumonia",
    "Pneumonitis due to inhalation of food and vomit":                  "bacterial_pneumonia",
    "Pneumonitis due to inhalation of food or vomitus":                 "bacterial_pneumonia",
    "Pneumonitis due to inhalation of other solids and liquids":        "bacterial_pneumonia",
    "Aspiration pneumonitis due to anesthesia during pregnancy, unspecified trimester": "bacterial_pneumonia",
    "Bronchitis and pneumonitis due to chemicals, gases, fumes and vapors": "bacterial_pneumonia",
    # Sepsis-causing organisms that produce pneumonia patterns:
    "Streptococcus pneumoniae as the cause of diseases classified elsewhere": "bacterial_pneumonia",

    # ── Viral / atypical pneumonia (non-COVID) ───────────────────────────────
    # Bilateral interstitial / GGO pattern but not COVID.
    # Includes atypical organisms (Mycoplasma) and influenza pneumonia.
    # Cryptogenic organizing pneumonia (COP) and hypersensitivity pneumonitis
    # sit here because they produce bilateral inflammatory/GGO patterns that
    # on CT look more like viral/atypical than fibrosis.
    "Viral pneumonia, unspecified":                                     "viral_pneumonia",
    "Other viral pneumonia":                                            "viral_pneumonia",
    "Pneumonia due to other virus not elsewhere classified":            "viral_pneumonia",
    "Respiratory syncytial virus pneumonia":                            "viral_pneumonia",
    "Human metapneumovirus pneumonia":                                  "viral_pneumonia",
    "Influenza due to identified novel influenza A virus with pneumonia": "viral_pneumonia",
    "Influenza due to other identified influenza virus with other specified pneumonia": "viral_pneumonia",
    "Influenza due to other identified influenza virus with unspecified type of pneumonia": "viral_pneumonia",
    "Acute interstitial pneumonitis":                                   "viral_pneumonia",
    "Cryptogenic organizing pneumonia":                                 "viral_pneumonia",
    "Hypersensitivity pneumonitis due to unspecified organic dust":     "viral_pneumonia",
    "Idiopathic interstitial pneumonia, not otherwise specified":       "viral_pneumonia",
    "Idiopathic non-specific interstitial pneumonitis":                 "viral_pneumonia",
    "Lymphoid interstitial pneumonia":                                  "viral_pneumonia",
    "Respiratory bronchiolitis interstitial lung disease":              "viral_pneumonia",
    # Fungal / opportunistic (bilateral infiltrates, may mimic viral):
    "Pneumocystosis":                                                   "viral_pneumonia",
    "Aspergillosis, unspecified":                                       "viral_pneumonia",
    "Invasive pulmonary aspergillosis":                                 "viral_pneumonia",
    "Allergic bronchopulmonary aspergillosis":                         "viral_pneumonia",
    "Other pulmonary aspergillosis":                                    "viral_pneumonia",
    "Other forms of aspergillosis":                                     "viral_pneumonia",
    "Pulmonary candidiasis":                                            "viral_pneumonia",
    "Pulmonary cryptococcosis":                                         "viral_pneumonia",
    "Pulmonary mucormycosis":                                           "viral_pneumonia",
    "Pulmonary nocardiosis":                                            "viral_pneumonia",
    "Histoplasmosis capsulati, unspecified":                            "viral_pneumonia",

    # ── Lung abscess / necrotizing pneumonia ─────────────────────────────────
    # Cavitary / necrotic lung parenchyma on CT — distinct from simple consolidation.
    "Abscess of lung with pneumonia":                                   "lung_abscess",
    "Abscess of lung without pneumonia":                                "lung_abscess",
    "Gangrene and necrosis of lung":                                    "lung_abscess",
    "Abscess of mediastinum":                                           "lung_abscess",
    "Pyothorax with fistula":                                           "lung_abscess",
    "Pyothorax without fistula":                                        "lung_abscess",

    # ── Emphysema / COPD ─────────────────────────────────────────────────────
    # Obstructive ventilatory pattern; hyperinflation, air trapping on CT.
    # Subcutaneous/interstitial emphysema are procedure-related and NOT included.
    "Emphysema, unspecified":                                           "emphysema_copd",
    "Centrilobular emphysema":                                          "emphysema_copd",
    "Panlobular emphysema":                                             "emphysema_copd",
    "Other emphysema":                                                  "emphysema_copd",
    "Unilateral pulmonary emphysema [MacLeod's syndrome]":              "emphysema_copd",
    "Chronic obstructive pulmonary disease, unspecified":               "emphysema_copd",
    "Chronic obstructive pulmonary disease with (acute) exacerbation":  "emphysema_copd",
    "Chronic obstructive pulmonary disease with (acute) lower respiratory infection": "emphysema_copd",
    "Chronic obstructive asthma, unspecified":                          "emphysema_copd",
    "Obstructive chronic bronchitis with (acute) exacerbation":         "emphysema_copd",
    "Chronic airway obstruction, not elsewhere classified":             "emphysema_copd",

    # ── ILD / fibrosis ───────────────────────────────────────────────────────
    # Fibrotic / reticular / ground-glass pattern on HRCT.
    # Includes: IPF, NSIP, sarcoidosis, drug/radiation ILD, asbestosis,
    # pneumoconiosis, autoimmune-ILD (lupus, scleroderma, RA-lung, Sjogren,
    # polymyositis, dermatomyositis). Sarcoidosis stays here because its
    # perilymphatic nodule + hilar adenopathy pattern is a fibrotic/granulomatous
    # finding best grouped with ILD for imaging classification.
    "Pulmonary fibrosis, unspecified":                                  "ild_fibrosis",
    "Idiopathic pulmonary fibrosis":                                    "ild_fibrosis",
    "Postinflammatory pulmonary fibrosis":                              "ild_fibrosis",
    "Interstitial pulmonary disease, unspecified":                      "ild_fibrosis",
    "Other interstitial pulmonary diseases with fibrosis in diseases classified elsewhere": "ild_fibrosis",
    "Other specified interstitial pulmonary diseases":                  "ild_fibrosis",
    "Interstitial lung disease with progressive fibrotic phenotype in diseases classified elsewhere": "ild_fibrosis",
    "Other interstitial lung diseases of childhood":                    "ild_fibrosis",
    "Chronic drug-induced interstitial lung disorders":                 "ild_fibrosis",
    "Drug-induced interstitial lung disorders, unspecified":            "ild_fibrosis",
    "Chronic and other pulmonary manifestations due to radiation":      "ild_fibrosis",
    "Acute pulmonary manifestations due to radiation":                  "ild_fibrosis",
    "Asbestosis":                                                       "ild_fibrosis",
    "Pneumoconiosis due to asbestos and other mineral fibers":          "ild_fibrosis",
    "Unspecified pneumoconiosis":                                       "ild_fibrosis",
    "Pleural plaque with presence of asbestos":                         "ild_fibrosis",
    "Pleural plaque without asbestos":                                  "ild_fibrosis",
    # Sarcoidosis:
    "Sarcoidosis":                                                      "ild_fibrosis",
    "Sarcoidosis of lung":                                              "ild_fibrosis",
    "Sarcoidosis of lung with sarcoidosis of lymph nodes":              "ild_fibrosis",
    "Sarcoidosis of other sites":                                       "ild_fibrosis",
    "Sarcoidosis, unspecified":                                         "ild_fibrosis",
    # Autoimmune-ILD:
    "Rheumatoid lung disease with rheumatoid arthritis of unspecified site": "ild_fibrosis",
    "Lung involvement in systemic lupus erythematosus":                 "ild_fibrosis",
    "Sjogren syndrome with lung involvement":                           "ild_fibrosis",
    "Polymyositis with respiratory involvement":                        "ild_fibrosis",
    "Other dermatomyositis with respiratory involvement":               "ild_fibrosis",
    "Pulmonary alveolar microlithiasis":                                "ild_fibrosis",
    # Cystic fibrosis with pulmonary fibrotic features:
    "Cystic fibrosis with pulmonary manifestations":                    "ild_fibrosis",
    "Cystic fibrosis, unspecified":                                     "ild_fibrosis",

    # ── Pleural effusion ─────────────────────────────────────────────────────
    # Fluid in pleural space — classic blunting of costophrenic angle on CXR,
    # layering fluid on CT. Includes all aetiologies as the imaging finding
    # (not the cause) is what the model learns.
    "Pleural effusion, not elsewhere classified":                       "pleural_effusion",
    "Unspecified pleural effusion":                                     "pleural_effusion",
    "Pleural effusion in other conditions classified elsewhere":        "pleural_effusion",
    "Malignant pleural effusion":                                       "pleural_effusion",
    "Chylous effusion":                                                 "pleural_effusion",
    "Other specified pleural conditions":                               "pleural_effusion",
    "Pleural condition, unspecified":                                   "pleural_effusion",
    "Pleurisy":                                                         "pleural_effusion",
    "Pleurisy without mention of effusion or current tuberculosis":     "pleural_effusion",
    "Hemothorax":                                                       "pleural_effusion",
    "Traumatic hemothorax, initial encounter":                          "pleural_effusion",
    # Pericardial effusion visible on CXR as enlarged cardiac silhouette:
    "Pericardial effusion (noninflammatory)":                           "pleural_effusion",

    # ── Pneumothorax ─────────────────────────────────────────────────────────
    # Air in pleural space — visceral pleural line on CXR, distinct on CT.
    "Pneumothorax, unspecified":                                        "pneumothorax",
    "Other pneumothorax":                                               "pneumothorax",
    "Other pneumothorax and air leak":                                  "pneumothorax",
    "Spontaneous tension pneumothorax":                                 "pneumothorax",
    "Primary spontaneous pneumothorax":                                 "pneumothorax",
    "Secondary spontaneous pneumothorax":                               "pneumothorax",
    "Postprocedural pneumothorax":                                      "pneumothorax",
    "Chronic pneumothorax":                                             "pneumothorax",
    "Other air leak":                                                   "pneumothorax",
    "Postprocedural air leak":                                          "pneumothorax",

    # ── Atelectasis ──────────────────────────────────────────────────────────
    # Lobar / segmental / subsegmental collapse.
    "Atelectasis":                                                      "atelectasis",
    "Other pulmonary collapse":                                         "atelectasis",
    "Pulmonary collapse":                                               "atelectasis",

    # ── Pulmonary embolism ───────────────────────────────────────────────────
    # Filling defect on CTPA; RV strain on CXR.
    "Other pulmonary embolism without acute cor pulmonale":             "pulm_embolism",
    "Other pulmonary embolism with acute cor pulmonale":                "pulm_embolism",
    "Single subsegmental pulmonary embolism without acute cor pulmonale": "pulm_embolism",
    "Multiple subsegmental pulmonary emboli without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery without acute cor pulmonale":   "pulm_embolism",
    "Saddle embolus of pulmonary artery with acute cor pulmonale":      "pulm_embolism",
    "Chronic pulmonary embolism":                                       "pulm_embolism",
    "Septic pulmonary embolism without acute cor pulmonale":            "pulm_embolism",
    "Septic pulmonary embolism with acute cor pulmonale":               "pulm_embolism",
    "Other pulmonary embolism and infarction":                          "pulm_embolism",

    # ── ARDS / acute respiratory failure ─────────────────────────────────────
    # Bilateral diffuse alveolar damage pattern.
    # Chronic respiratory failure is metadata (no distinct imaging phenotype).
    "Acute respiratory distress syndrome":                              "ards",
    "Acute respiratory distress":                                       "ards",
    "Acute respiratory failure":                                        "ards",
    "Acute respiratory failure with hypoxia":                           "ards",
    "Acute respiratory failure with hypercapnia":                       "ards",
    "Acute respiratory failure, unspecified whether with hypoxia or hypercapnia": "ards",
    "Respiratory failure, unspecified with hypoxia":                    "ards",
    "Respiratory failure, unspecified with hypercapnia":                "ards",
    "Respiratory failure, unspecified, unspecified whether with hypoxia or hypercapnia": "ards",
    "Acute and chronic respiratory failure with hypoxia":               "ards",
    "Acute and chronic respiratory failure with hypercapnia":           "ards",
    "Acute and chronic respiratory failure, unspecified whether with hypoxia or hypercapnia": "ards",
    "Acute and chronic respiratory failure":                            "ards",
    "Acute postprocedural respiratory failure":                         "ards",

    # ── Lung malignancy ──────────────────────────────────────────────────────
    # All primary/secondary thoracic malignancies including mediastinal and pleural.
    # NOTE: "Solitary pulmonary nodule" is NOT included — it is radiological sign,
    # not a confirmed malignancy; it inflates the label without confirmed cancer.
    "Malignant neoplasm of bronchus and lung, unspecified":             "lung_malignancy",
    "Malignant neoplasm of left main bronchus":                         "lung_malignancy",
    "Malignant neoplasm of right main bronchus":                        "lung_malignancy",
    "Malignant neoplasm of unspecified main bronchus":                  "lung_malignancy",
    "Malignant neoplasm of lower lobe, left bronchus or lung":          "lung_malignancy",
    "Malignant neoplasm of lower lobe, right bronchus or lung":         "lung_malignancy",
    "Malignant neoplasm of upper lobe, left bronchus or lung":          "lung_malignancy",
    "Malignant neoplasm of upper lobe, right bronchus or lung":         "lung_malignancy",
    "Malignant neoplasm of upper lobe, bronchus or lung":               "lung_malignancy",
    "Malignant neoplasm of unspecified part of left bronchus or lung":  "lung_malignancy",
    "Malignant neoplasm of unspecified part of right bronchus or lung": "lung_malignancy",
    "Malignant neoplasm of unspecified part of unspecified bronchus or lung": "lung_malignancy",
    "Malignant neoplasm of overlapping sites of left bronchus and lung": "lung_malignancy",
    "Malignant neoplasm of overlapping sites of right bronchus and lung": "lung_malignancy",
    "Malignant neoplasm of mediastinum, part unspecified":              "lung_malignancy",
    "Malignant neoplasm of thymus":                                     "lung_malignancy",
    "Mesothelioma of pleura":                                           "lung_malignancy",
    "Secondary malignant neoplasm of pleura":                           "lung_malignancy",
    "Secondary malignant neoplasm of mediastinum":                      "lung_malignancy",
    "Secondary malignant neoplasm of right lung":                       "lung_malignancy",
    "Secondary malignant neoplasm of unspecified lung":                 "lung_malignancy",
    "Secondary and unspecified malignant neoplasm of intrathoracic lymph nodes": "lung_malignancy",
    "Acquired absence of lung [part of]":                               "lung_malignancy",  # post-resection
}


# ── Metadata comorbidity map ─────────────────────────────────────────────────
# Not training targets; included as tabular side-channel features.
# These conditions affect chest imaging indirectly (vascular markings, cardiac
# silhouette, aortic contour) and serve as risk stratifiers.

CONDITION_METADATA_MAP: dict[str, str] = {

    # ── Heart failure (all forms) ────────────────────────────────────────────
    "Acute systolic (congestive) heart failure":                        "meta_heart_failure",
    "Acute systolic heart failure":                                     "meta_heart_failure",
    "Acute diastolic (congestive) heart failure":                       "meta_heart_failure",
    "Acute on chronic systolic (congestive) heart failure":             "meta_heart_failure",
    "Acute on chronic systolic heart failure":                          "meta_heart_failure",
    "Acute on chronic diastolic (congestive) heart failure":            "meta_heart_failure",
    "Acute on chronic diastolic heart failure":                         "meta_heart_failure",
    "Acute on chronic combined systolic (congestive) and diastolic (congestive) heart failure": "meta_heart_failure",
    "Acute on chronic combined systolic and diastolic heart failure":   "meta_heart_failure",
    "Chronic systolic (congestive) heart failure":                      "meta_heart_failure",
    "Chronic systolic heart failure":                                   "meta_heart_failure",
    "Chronic diastolic (congestive) heart failure":                     "meta_heart_failure",
    "Chronic diastolic heart failure":                                  "meta_heart_failure",
    "Chronic combined systolic (congestive) and diastolic (congestive) heart failure": "meta_heart_failure",
    "Biventricular heart failure":                                      "meta_heart_failure",
    "Acute right heart failure":                                        "meta_heart_failure",
    "Acute on chronic right heart failure":                             "meta_heart_failure",
    "Chronic right heart failure":                                      "meta_heart_failure",
    "Right heart failure, unspecified":                                 "meta_heart_failure",
    "Right heart failure due to left heart failure":                    "meta_heart_failure",
    "Left heart failure":                                               "meta_heart_failure",
    "Congestive heart failure, unspecified":                            "meta_heart_failure",
    "Heart failure, unspecified":                                       "meta_heart_failure",
    "End stage heart failure":                                          "meta_heart_failure",
    "High output heart failure":                                        "meta_heart_failure",
    "Other heart failure":                                              "meta_heart_failure",
    "Systolic heart failure, unspecified":                              "meta_heart_failure",
    "Unspecified systolic (congestive) heart failure":                  "meta_heart_failure",
    "Unspecified diastolic (congestive) heart failure":                 "meta_heart_failure",
    "Unspecified combined systolic (congestive) and diastolic (congestive) heart failure": "meta_heart_failure",
    "Hypertensive heart disease with heart failure":                    "meta_heart_failure",
    "Hypertensive heart and chronic kidney disease with heart failure and stage 1 through stage 4 chronic kidney disease, or unspecified chronic kidney disease": "meta_heart_failure",
    "Hypertensive heart and chronic kidney disease with heart failure and with stage 5 chronic kidney disease, or end stage renal disease": "meta_heart_failure",
    "Postprocedural heart failure following cardiac surgery":           "meta_heart_failure",
    "Postprocedural heart failure following other surgery":             "meta_heart_failure",

    # ── Pulmonary hypertension ───────────────────────────────────────────────
    "Pulmonary hypertension, unspecified":                              "meta_pulm_htn",
    "Primary pulmonary hypertension":                                   "meta_pulm_htn",
    "Secondary pulmonary arterial hypertension":                        "meta_pulm_htn",
    "Pulmonary hypertension due to left heart disease":                 "meta_pulm_htn",
    "Pulmonary hypertension due to lung diseases and hypoxia":          "meta_pulm_htn",
    "Other secondary pulmonary hypertension":                           "meta_pulm_htn",
    "Chronic thromboembolic pulmonary hypertension":                    "meta_pulm_htn",
    "Cor pulmonale (chronic)":                                          "meta_pulm_htn",

    # ── Cardiomegaly / cardiomyopathy ────────────────────────────────────────
    "Cardiomegaly":                                                     "meta_cardiomegaly",
    "Dilated cardiomyopathy":                                           "meta_cardiomegaly",
    "Ischemic cardiomyopathy":                                          "meta_cardiomegaly",
    "Obstructive hypertrophic cardiomyopathy":                          "meta_cardiomegaly",
    "Other hypertrophic cardiomyopathy":                                "meta_cardiomegaly",
    "Other restrictive cardiomyopathy":                                 "meta_cardiomegaly",
    "Other primary cardiomyopathies":                                   "meta_cardiomegaly",
    "Cardiomyopathy, unspecified":                                      "meta_cardiomegaly",
    "Cardiomyopathy":                                                   "meta_cardiomegaly",
    "Alcoholic cardiomyopathy":                                         "meta_cardiomegaly",
    "Cardiomyopathy due to drug and external agent":                    "meta_cardiomegaly",
    "Cardiomyopathy in diseases classified elsewhere":                  "meta_cardiomegaly",
    "Viral cardiomyopathy":                                             "meta_cardiomegaly",
    "Hypertrophic obstructive cardiomyopathy":                          "meta_cardiomegaly",

    # ── Pulmonary oedema (cardiogenic) ───────────────────────────────────────
    "Acute pulmonary edema":                                            "meta_pulm_edema",
    "Acute edema of lung, unspecified":                                 "meta_pulm_edema",
    "Chronic pulmonary edema":                                          "meta_pulm_edema",

    # ── Cardiac arrhythmia ───────────────────────────────────────────────────
    "Atrial fibrillation":                                              "meta_arrhythmia",
    "Unspecified atrial fibrillation":                                  "meta_arrhythmia",
    "Paroxysmal atrial fibrillation":                                   "meta_arrhythmia",
    "Chronic atrial fibrillation, unspecified":                         "meta_arrhythmia",
    "Longstanding persistent atrial fibrillation":                      "meta_arrhythmia",
    "Other persistent atrial fibrillation":                             "meta_arrhythmia",
    "Permanent atrial fibrillation":                                    "meta_arrhythmia",
    "Atrial flutter":                                                   "meta_arrhythmia",
    "Unspecified atrial flutter":                                       "meta_arrhythmia",
    "Typical atrial flutter":                                           "meta_arrhythmia",
    "Atypical atrial flutter":                                          "meta_arrhythmia",
    "Ventricular tachycardia":                                          "meta_arrhythmia",
    "Ventricular fibrillation":                                         "meta_arrhythmia",
    "Ventricular premature depolarization":                             "meta_arrhythmia",
    "Atrial premature depolarization":                                  "meta_arrhythmia",
    "Atrioventricular block, complete":                                 "meta_arrhythmia",
    "Atrioventricular block, first degree":                             "meta_arrhythmia",
    "Atrioventricular block, second degree":                            "meta_arrhythmia",
    "Unspecified atrioventricular block":                               "meta_arrhythmia",
    "Other atrioventricular block":                                     "meta_arrhythmia",
    "Bradycardia, unspecified":                                         "meta_arrhythmia",
    "Cardiac arrhythmia, unspecified":                                  "meta_arrhythmia",
    "Cardiac dysrhythmia, unspecified":                                 "meta_arrhythmia",
    "Other specified cardiac arrhythmias":                              "meta_arrhythmia",
    "Other specified cardiac dysrhythmias":                             "meta_arrhythmia",
    "Supraventricular tachycardia":                                     "meta_arrhythmia",
    "Paroxysmal supraventricular tachycardia":                          "meta_arrhythmia",
    "Supraventricular premature beats":                                 "meta_arrhythmia",
    "Sinoatrial node dysfunction":                                      "meta_arrhythmia",

    # ── Coronary artery disease / ischaemic heart disease ────────────────────
    "Atherosclerotic heart disease of native coronary artery without angina pectoris": "meta_cad",
    "Atherosclerotic heart disease of native coronary artery with other forms of angina pectoris": "meta_cad",
    "Atherosclerotic heart disease of native coronary artery with unstable angina pectoris": "meta_cad",
    "Atherosclerotic heart disease of native coronary artery with unspecified angina pectoris": "meta_cad",
    "Atherosclerotic heart disease of native coronary artery with angina pectoris with documented spasm": "meta_cad",
    "Atherosclerosis of coronary artery bypass graft(s) without angina pectoris": "meta_cad",
    "Atherosclerosis of coronary artery bypass graft(s), unspecified, with other forms of angina pectoris": "meta_cad",
    "Coronary atherosclerosis of native coronary artery":               "meta_cad",
    "Coronary atherosclerosis due to calcified coronary lesion":        "meta_cad",
    "Coronary atherosclerosis due to lipid rich plaque":                "meta_cad",
    "Acute myocardial infarction, unspecified":                         "meta_cad",
    "Non-ST elevation (NSTEMI) myocardial infarction":                  "meta_cad",
    "ST elevation (STEMI) myocardial infarction involving left anterior descending coronary artery": "meta_cad",
    "ST elevation (STEMI) myocardial infarction involving other coronary artery of anterior wall": "meta_cad",
    "ST elevation (STEMI) myocardial infarction involving other coronary artery of inferior wall": "meta_cad",
    "ST elevation (STEMI) myocardial infarction involving other sites": "meta_cad",
    "ST elevation (STEMI) myocardial infarction involving right coronary artery": "meta_cad",
    "ST elevation (STEMI) myocardial infarction of unspecified site":   "meta_cad",
    "Old myocardial infarction":                                        "meta_cad",
    "Myocardial infarction type 2":                                     "meta_cad",
    "Chronic ischemic heart disease, unspecified":                      "meta_cad",
    "Acute ischemic heart disease, unspecified":                        "meta_cad",
    "Other forms of acute ischemic heart disease":                      "meta_cad",
    "Other specified forms of chronic ischemic heart disease":          "meta_cad",
    "Angina pectoris, unspecified":                                     "meta_cad",
    "Other and unspecified angina pectoris":                            "meta_cad",
    "Other forms of angina pectoris":                                   "meta_cad",
    "Acute coronary thrombosis not resulting in myocardial infarction": "meta_cad",
    "Chronic total occlusion of coronary artery":                       "meta_cad",

    # ── Valvular heart disease ───────────────────────────────────────────────
    "Nonrheumatic aortic (valve) insufficiency":                        "meta_valvular",
    "Nonrheumatic aortic (valve) stenosis":                             "meta_valvular",
    "Nonrheumatic aortic (valve) stenosis with insufficiency":          "meta_valvular",
    "Nonrheumatic aortic valve disorder, unspecified":                  "meta_valvular",
    "Other nonrheumatic aortic valve disorders":                        "meta_valvular",
    "Nonrheumatic mitral (valve) insufficiency":                        "meta_valvular",
    "Nonrheumatic mitral (valve) prolapse":                             "meta_valvular",
    "Nonrheumatic mitral (valve) stenosis":                             "meta_valvular",
    "Other nonrheumatic mitral valve disorders":                        "meta_valvular",
    "Nonrheumatic tricuspid (valve) insufficiency":                     "meta_valvular",
    "Nonrheumatic tricuspid (valve) stenosis":                          "meta_valvular",
    "Nonrheumatic tricuspid valve disorder, unspecified":               "meta_valvular",
    "Other nonrheumatic tricuspid valve disorders":                     "meta_valvular",
    "Nonrheumatic pulmonary valve insufficiency":                       "meta_valvular",
    "Nonrheumatic pulmonary valve stenosis":                            "meta_valvular",
    "Other nonrheumatic pulmonary valve disorders":                     "meta_valvular",
    "Rheumatic mitral insufficiency":                                   "meta_valvular",
    "Rheumatic mitral stenosis":                                        "meta_valvular",
    "Rheumatic mitral stenosis with insufficiency":                     "meta_valvular",
    "Rheumatic mitral valve disease, unspecified":                      "meta_valvular",
    "Other rheumatic mitral valve diseases":                            "meta_valvular",
    "Rheumatic aortic insufficiency":                                   "meta_valvular",
    "Rheumatic aortic stenosis":                                        "meta_valvular",
    "Rheumatic aortic stenosis with insufficiency":                     "meta_valvular",
    "Rheumatic tricuspid insufficiency":                                "meta_valvular",
    "Rheumatic tricuspid valve disease, unspecified":                   "meta_valvular",
    "Rheumatic disorders of both mitral and aortic valves":             "meta_valvular",
    "Rheumatic disorders of both aortic and tricuspid valves":          "meta_valvular",
    "Rheumatic disorders of both mitral and tricuspid valves":          "meta_valvular",
    "Combined rheumatic disorders of mitral, aortic and tricuspid valves": "meta_valvular",
    "Other rheumatic multiple valve diseases":                          "meta_valvular",
    "Endocarditis, valve unspecified":                                  "meta_valvular",
    "Acute and subacute infective endocarditis":                        "meta_valvular",
    "Endocarditis and heart valve disorders in diseases classified elsewhere": "meta_valvular",
    "Mitral valve disorders":                                           "meta_valvular",
    "Mitral stenosis":                                                  "meta_valvular",
    "Other and unspecified mitral valve diseases":                      "meta_valvular",
    "Aortic valve disorders":                                           "meta_valvular",
    "Diseases of tricuspid valve":                                      "meta_valvular",
    "Cardiac tamponade":                                                "meta_valvular",
    "Acute pericarditis, unspecified":                                  "meta_valvular",
    "Chronic adhesive pericarditis":                                    "meta_valvular",
    "Infective pericarditis":                                           "meta_valvular",
    "Disease of pericardium, unspecified":                              "meta_valvular",
    "Congenital insufficiency of aortic valve":                         "meta_valvular",
    "Congenital pulmonary valve stenosis":                              "meta_valvular",

    # ── Systemic hypertension ────────────────────────────────────────────────
    "Essential (primary) hypertension":                                 "meta_hypertension",
    "Unspecified essential hypertension":                               "meta_hypertension",
    "Benign essential hypertension":                                    "meta_hypertension",
    "Essential hypertension":                                           "meta_hypertension",
    "Hypertensive heart disease without heart failure":                 "meta_hypertension",
    "Hypertensive heart and chronic kidney disease without heart failure, with stage 1 through stage 4 chronic kidney disease, or unspecified chronic kidney disease": "meta_hypertension",
    "Hypertensive emergency":                                           "meta_hypertension",
    "Hypertensive urgency":                                             "meta_hypertension",
    "Other secondary hypertension":                                     "meta_hypertension",
    "Secondary hypertension, unspecified":                              "meta_hypertension",
    "Renovascular hypertension":                                        "meta_hypertension",

    # ── Diabetes mellitus ────────────────────────────────────────────────────
    "Diabetes mellitus":                                                "meta_diabetes",
    "Diabetes mellitus due to underlying condition without complications": "meta_diabetes",
    "Diabetes mellitus due to underlying condition with unspecified complications": "meta_diabetes",
    "Diabetes mellitus without mention of complication, type II or unspecified type, not stated as uncontrolled": "meta_diabetes",
    "Diabetes mellitus without mention of complication, type II or unspecified type, uncontrolled": "meta_diabetes",
    "Type 1 diabetes mellitus with hyperglycemia":                      "meta_diabetes",
    "Type 1 diabetes mellitus with ketoacidosis without coma":          "meta_diabetes",
    "Type 1 diabetes mellitus with diabetic chronic kidney disease":    "meta_diabetes",
    "Type 2 diabetes mellitus with hyperglycemia":                      "meta_diabetes",
    "Type 2 diabetes mellitus with diabetic chronic kidney disease":    "meta_diabetes",
    "Type 2 diabetes mellitus without complications":                   "meta_diabetes",
    "Type 2 diabetes mellitus with hyperosmolarity without nonketotic hyperglycemic-hyperosmolar coma (NKHHC)": "meta_diabetes",
    "Type 2 diabetes mellitus with ketoacidosis without coma":          "meta_diabetes",
    "Drug or chemical induced diabetes mellitus without complications":  "meta_diabetes",
    "Drug or chemical induced diabetes mellitus with hyperglycemia":    "meta_diabetes",

    # ── Chronic kidney disease / renal failure ───────────────────────────────
    "Chronic kidney disease (CKD)":                                     "meta_renal",
    "Chronic kidney disease, Stage II (mild)":                          "meta_renal",
    "Chronic kidney disease, Stage III (moderate)":                     "meta_renal",
    "Chronic kidney disease, Stage IV (severe)":                        "meta_renal",
    "Chronic kidney disease, Stage V":                                  "meta_renal",
    "Chronic kidney disease, stage 1":                                  "meta_renal",
    "Chronic kidney disease, stage 2 (mild)":                          "meta_renal",
    "Chronic kidney disease, stage 3 (moderate)":                      "meta_renal",
    "Chronic kidney disease, stage 3 unspecified":                      "meta_renal",
    "Chronic kidney disease, stage 3a":                                 "meta_renal",
    "Chronic kidney disease, stage 3b":                                 "meta_renal",
    "Chronic kidney disease, stage 4 (severe)":                        "meta_renal",
    "Chronic kidney disease, stage 5":                                  "meta_renal",
    "Chronic kidney disease, unspecified":                              "meta_renal",
    "Hypertensive chronic kidney disease with stage 1 through stage 4 chronic kidney disease, or unspecified chronic kidney disease": "meta_renal",
    "Hypertensive chronic kidney disease with stage 5 chronic kidney disease or end stage renal disease": "meta_renal",

    # ── Thoracic aortic disease (visible on CT) ──────────────────────────────
    "Thoracic aortic aneurysm, without rupture":                        "meta_aortic_disease",
    "Thoracic aortic aneurysm, ruptured":                               "meta_aortic_disease",
    "Thoracic aortic ectasia":                                          "meta_aortic_disease",
    "Dissection of thoracic aorta":                                     "meta_aortic_disease",
    "Dissection of thoracoabdominal aorta":                             "meta_aortic_disease",
    "Aortic aneurysm of unspecified site, without rupture":             "meta_aortic_disease",
    "Aortic aneurysm of unspecified site, ruptured":                    "meta_aortic_disease",
    "Aortic ectasia, unspecified site":                                 "meta_aortic_disease",

    # ── Autoimmune / connective tissue ───────────────────────────────────────
    # These drive ILD and pleural disease; useful as risk modifiers.
    "Systemic lupus erythematosus, unspecified":                        "meta_autoimmune",
    "Systemic lupus erythematosus, organ or system involvement unspecified": "meta_autoimmune",
    "Other forms of systemic lupus erythematosus":                      "meta_autoimmune",
    "Other organ or system involvement in systemic lupus erythematosus": "meta_autoimmune",
    "Drug-induced systemic lupus erythematosus":                        "meta_autoimmune",
    "Systemic sclerosis, unspecified":                                  "meta_autoimmune",
    "Progressive systemic sclerosis":                                   "meta_autoimmune",
    "Other systemic sclerosis":                                         "meta_autoimmune",
    "Sjogren syndrome, unspecified":                                    "meta_autoimmune",
    "Sjogren syndrome with keratoconjunctivitis":                       "meta_autoimmune",
    "Sjogren syndrome with inflammatory arthritis":                     "meta_autoimmune",
    "Sjogren syndrome with central nervous system involvement":         "meta_autoimmune",
    "Sjogren syndrome with peripheral nervous system involvement":      "meta_autoimmune",
    "Polymyositis with other organ involvement":                        "meta_autoimmune",
    "Polymyositis, organ involvement unspecified":                      "meta_autoimmune",
    "Other dermatomyositis with myopathy":                              "meta_autoimmune",
    "Other dermatomyositis with other organ involvement":               "meta_autoimmune",
    "Other dermatomyositis without myopathy":                           "meta_autoimmune",
    "Other dermatomyositis, organ involvement unspecified":             "meta_autoimmune",
    "Dermatopolymyositis, unspecified with other organ involvement":    "meta_autoimmune",
    "Dermatopolymyositis, unspecified, organ involvement unspecified":  "meta_autoimmune",
    "Systemic involvement of connective tissue, unspecified":           "meta_autoimmune",
    "Other specified systemic involvement of connective tissue":        "meta_autoimmune",
    "Wegener's granulomatosis without renal involvement":               "meta_autoimmune",
    "Wegener's granulomatosis with renal involvement":                  "meta_autoimmune",

    # ── Lung / heart transplant status ──────────────────────────────────────
    # Alters lung anatomy on CT; raises risk of opportunistic infection.
    "Lung transplant status":                                           "meta_transplant",
    "Lung transplant failure":                                          "meta_transplant",
    "Lung transplant rejection":                                        "meta_transplant",
    "Lung transplant infection":                                        "meta_transplant",
    "Other complications of lung transplant":                           "meta_transplant",
    "Complications of transplanted lung":                               "meta_transplant",
    "Heart transplant status":                                          "meta_transplant",
    "Heart transplant failure":                                         "meta_transplant",
    "Heart transplant rejection":                                       "meta_transplant",
    "Heart transplant infection":                                       "meta_transplant",
    "Other complications of heart transplant":                          "meta_transplant",
    "Heart-lung transplant failure":                                    "meta_transplant",
    "Other complications of heart-lung transplant":                     "meta_transplant",

    # ── TB / NTM (metadata — low primary label count in MIDRC) ──────────────
    # TB of lung (3x), respiratory TB (5x) too sparse for a primary label;
    # pulmonary NTM/MAC (190x + 13x DMAC) more common but kept as metadata.
    # If your enriched dataset has ≥300 confirmed TB cases, promote to primary.
    "Tuberculosis of lung":                                             "meta_tb_ntm",
    "Respiratory tuberculosis unspecified":                             "meta_tb_ntm",
    "Latent tuberculosis":                                              "meta_tb_ntm",
    "Pulmonary mycobacterial infection":                                "meta_tb_ntm",
    "Disseminated mycobacterium avium-intracellulare complex (DMAC)":  "meta_tb_ntm",
    "Mycobacterial infection, unspecified":                             "meta_tb_ntm",
    "Other mycobacterial infections":                                   "meta_tb_ntm",

    # ── Bronchiectasis (metadata — structural airway, not primary target) ────
    "Bronchiectasis, uncomplicated":                                    "meta_bronchiectasis",
    "Bronchiectasis with (acute) exacerbation":                         "meta_bronchiectasis",
    "Bronchiectasis with acute lower respiratory infection":            "meta_bronchiectasis",
}


PRIMARY_LABELS  = list(dict.fromkeys(CONDITION_PRIMARY_MAP.values()))
METADATA_LABELS = list(dict.fromkeys(CONDITION_METADATA_MAP.values()))

print(f"\nPrimary imaging labels ({len(PRIMARY_LABELS)}):")
for i, lbl in enumerate(PRIMARY_LABELS, 1):
    print(f"  {i:2d}. {lbl}")

print(f"\nMetadata comorbidity labels ({len(METADATA_LABELS)}):")
for lbl in METADATA_LABELS:
    print(f"      {lbl}")

# ══════════════════════════════════════════════════════════════════════════════
# 5. BUILD CASE-LEVEL LABEL TABLE
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("2. Building case-level label table …")
print("─" * 80)

ALL_CONDITION_MAP = {**CONDITION_PRIMARY_MAP, **CONDITION_METADATA_MAP}
ALL_LABEL_COLS    = PRIMARY_LABELS + METADATA_LABELS


def build_case_labels(df_cond_: pd.DataFrame) -> pd.DataFrame:
    df_ = df_cond_.copy()
    df_["case_ids_clean"] = df_["case_ids"].apply(clean_case_id)
    rows = []
    for case_id, grp in df_.groupby("case_ids_clean"):
        conditions = set(grp["condition_name"].dropna().tolist())
        row: dict = {"case_ids_clean": case_id}
        for label in ALL_LABEL_COLS:
            row[label] = int(any(ALL_CONDITION_MAP.get(c) == label for c in conditions))
        rows.append(row)
    return pd.DataFrame(rows)


df_case_labels = build_case_labels(df_cond)

print(f"✓ Labelled {len(df_case_labels):,} cases")
print("\nPrimary label distribution (case level):")
for lbl in sorted(PRIMARY_LABELS, key=lambda x: -df_case_labels[x].sum()):
    n = int(df_case_labels[lbl].sum())
    print(f"  {lbl:<30}: {n:5,}  ({100*n/len(df_case_labels):4.1f}%)")

# ══════════════════════════════════════════════════════════════════════════════
# 6. MERGE DEMOGRAPHICS
# ══════════════════════════════════════════════════════════════════════════════

# Ensure origin_project is preserved during your demographic assembly block
DEMO_COLS = ["submitter_id", "covid19_positive", "sex", "age_at_index", "race",
             "icu_indicator", "ventilator_indicator", "origin_project"]

df_cases_unique = df_cases.drop_duplicates("submitter_id")[DEMO_COLS].copy()

df_case_all = (
    df_cases_unique
    .merge(df_case_labels,
           left_on="submitter_id", right_on="case_ids_clean", how="left")
)

# Fill labels safely
for col in ALL_LABEL_COLS:
    df_case_all[col] = df_case_all.get(col, pd.Series(0, index=df_case_all.index)).fillna(0).astype(int)

# Reinforce COVID verification using cross-referencing flags
df_case_all["covid"] = (
    (df_case_all["covid"] == 1) |
    (df_case_all["covid19_positive"].fillna("").str.lower() == "yes")
).astype(int)

# Re-compute normal profiles across the merged master table
IMAGING_PRIMARIES = [l for l in PRIMARY_LABELS if l != "normal"]
df_case_all["normal"] = (df_case_all[IMAGING_PRIMARIES].sum(axis=1) == 0).astype(int)

print(f"\n✓ Cross-Project Case-Level Master Table Built: {len(df_case_all):,} rows")
# ══════════════════════════════════════════════════════════════════════════════
# 7. SERIES-LEVEL TABLES
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("3. Building series-level tables …")
print("─" * 80)


def build_series_df(df_series: pd.DataFrame, modality: str) -> pd.DataFrame:
    df = df_series.copy()
    df = df.merge(df_case_all, left_on="case_ids_clean", right_on="submitter_id",
                  how="left", suffixes=("_series", ""))
    df["modality"] = modality
    for col in ALL_LABEL_COLS + ["normal"]:
        if col not in df.columns:
            df[col] = 0
    return df


df_ct_merged  = build_series_df(df_chest_ct,  "CT")
df_cxr_merged = build_series_df(df_chest_cxr, "CXR")

print(f"  CT  merged: {len(df_ct_merged):,}")
print(f"  CXR merged: {len(df_cxr_merged):,}")

# ══════════════════════════════════════════════════════════════════════════════
# 8. BALANCED SAMPLING
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# 8. GENERALIZED / DYNAMIC SAMPLING
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("4. Generalized dynamic sampling …")
print("─" * 80)

def general_balanced_sample(
    df: pd.DataFrame,
    labels: list[str],
    id_col: str = "object_id",
    fraction: float = 1.0,  # Keep 1.0 to take everything available up to the dynamic cap
    target_per_class: int = None # Optional: Global cap if you want to limit total cohort size
) -> pd.DataFrame:
    """
    Dynamically samples from a multi-label dataframe. 
    If target_per_class is None, it adapts entirely to the maximum available 
    clean balance of the new dataset.
    """
    df_unique = df.drop_duplicates(id_col).copy()
    
    # Identify the rarest class in the current dataset to set a baseline if balancing
    class_counts = {lbl: int(df_unique[lbl].sum()) for lbl in labels if lbl in df_unique.columns}
    min_class = min(class_counts, key=class_counts.get)
    min_count = class_counts[min_class]
    
    print(f"    Dataset baseline (rarest class '{min_class}'): {min_count} available cases.")
    
    sampled_indices = set()
    
    # Sort labels by rarest first so multi-label rows are captured for tough classes first
    sorted_labels = sorted(class_counts.keys(), key=lambda x: class_counts[x])

    for label in sorted_labels:
        # Pool of assets having this label that haven't been picked yet
        pool = df_unique[df_unique[label] == 1]
        available_indices = pool.index.difference(list(sampled_indices))
        
        # Determine dynamic target: use target_per_class or scale with fraction
        if target_per_class:
            n_target = min(target_per_class, len(pool))
        else:
            # General approach: try to match at least the minority baseline, or take a fraction
            n_target = max(min_count, int(len(pool) * fraction))
            n_target = min(n_target, len(pool)) # Clamp to actual size
            
        # How many more do we need to pull specifically for this label?
        already_selected_with_label = df_unique.loc[list(sampled_indices), label].sum()
        needed = int(max(0, n_target - already_selected_with_label))
        
        if needed > 0 and len(available_indices) > 0:
            take = min(needed, len(available_indices))
            sampled_pool = df_unique.loc[available_indices].sample(n=take, random_state=RANDOM_SEED)
            sampled_indices.update(sampled_pool.index)
            
        final_count = df_unique.loc[list(sampled_indices), label].sum()
        print(f"    {label:<30}: {int(final_count):>4} total sampled (via {len(pool)} available)")

    return df_unique.loc[list(sampled_indices)].reset_index(drop=True)


# Automatically extract active classes (Primary + Normal)
ALL_TARGET_LABELS = IMAGING_PRIMARIES + ["normal"]
TARGET_MAX_PER_CLASS = 500

print("Executing Cross-Project Balanced Ingestion on CT Cohort:")
df_cohort_ct = general_balanced_sample(
    df_ct_merged, 
    ALL_TARGET_LABELS,
    target_per_class=TARGET_MAX_PER_CLASS
)

print("\nExecuting Cross-Project Balanced Ingestion on CXR Cohort:")
cxr_labels = [l for l in ALL_TARGET_LABELS if l != "pulm_embolism"]
df_cohort_cxr = general_balanced_sample(
    df_cxr_merged, 
    cxr_labels,
    target_per_class=TARGET_MAX_PER_CLASS
)

# ══════════════════════════════════════════════════════════════════════════════
# 9. MONAI PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("5. MONAI preprocessing …")
print("─" * 80)

if not MONAI_AVAILABLE:
    print("  ⚠ MONAI not available — skipping image preprocessing.")
    print("  Install: pip install monai[itk,nibabel,pillow]")
else:
    import torch

    # ── CT preprocessing pipeline ────────────────────────────────────────────
    ct_transforms = Compose([
        LoadImage(image_only=True, reader=ITKReader()),
        EnsureChannelFirst(),
        Orientation(axcodes="RAS"),
        Spacing(
            pixdim=CT_TARGET_SPACING,
            mode="bilinear",
        ),
        ScaleIntensityRangePercentiles(
            lower=0.5, upper=99.5, 
            b_min=0.0, b_max=1.0, 
            clip=True
        ),
        CropForeground(select_fn=lambda x: x > 0),
        Resize(spatial_size=CT_TARGET_SHAPE, mode="trilinear"), # Fixed for 3D volumes
        NormalizeIntensity(nonzero=True, channel_wise=True),
    ])

    # ── CXR preprocessing pipeline ───────────────────────────────────────────
    def _clahe(x: "torch.Tensor") -> "torch.Tensor":
        """Per-slice CLAHE using skimage safely."""
        try:
            from skimage.exposure import equalize_adapthist
            arr = x.detach().cpu().numpy() # Safe tensor-to-numpy conversion
            out = np.stack(
                [equalize_adapthist(arr[c], clip_limit=0.03) for c in range(arr.shape[0])],
                axis=0,
            )
            return torch.tensor(out, dtype=x.dtype)
        except ImportError:
            return x

    cxr_transforms = Compose([
        LoadImage(image_only=True, reader=ITKReader()),
        EnsureChannelFirst(),
        ScaleIntensityRangePercentiles(
            lower=0.5, upper=99.5, 
            b_min=0.0, b_max=1.0, 
            clip=True
        ),
        Lambda(func=_clahe),
        Resize(spatial_size=CXR_TARGET_SHAPE, mode="area"), # Area works great for 2D
        NormalizeIntensity(
            subtrahend=0.485,
            divisor=0.229,
            nonzero=False,
            channel_wise=True,
        ),
    ])

    def preprocess_series(
        df_cohort: pd.DataFrame,
        transforms,
        out_dir: Path,
        ext: str,
        modality: str,
        file_col: str = "file_name",
        id_col: str = "object_id",
    ) -> pd.DataFrame:
        src_root  = Path("images")
        out_paths = []
        skipped   = 0

        for _, row in df_cohort.iterrows():
            obj_id   = str(row.get(id_col, "unknown"))
            fname    = str(row.get(file_col, ""))
            src_path = src_root / obj_id / fname

            save_name = f"{obj_id}{ext}"
            save_path = out_dir / save_name

            if save_path.exists():
                out_paths.append(str(save_path))
                continue

            if not src_path.exists():
                log.warning(f"Source not found: {src_path} — skipping")
                out_paths.append("")
                skipped += 1
                continue

            try:
                tensor = transforms(str(src_path))
                arr    = tensor.numpy() if hasattr(tensor, "numpy") else np.array(tensor)
                if ext == ".nii.gz":
                    import nibabel as nib
                    # Preserving spatial scale factors using an affine mapping matching target spacing
                    affine = np.diag([*CT_TARGET_SPACING, 1.0])
                    nii = nib.Nifti1Image(arr[0], affine=affine)
                    nib.save(nii, str(save_path))
                else:
                    np.save(str(save_path).replace(ext, ".npy"), arr)
                    save_path = Path(str(save_path).replace(ext, ".npy"))
                out_paths.append(str(save_path))
            except Exception as exc:
                log.warning(f"Preprocessing failed for {obj_id}: {exc}")
                out_paths.append("")
                skipped += 1

        df_out = df_cohort.copy()
        df_out["preprocessed_path"] = out_paths
        log.info(
            f"{modality}: {len(df_cohort) - skipped} / {len(df_cohort)} "
            f"series preprocessed ({skipped} skipped)"
        )
        return df_out

    print("  Preprocessing CT series …")
    df_cohort_ct = preprocess_series(
        df_cohort_ct, ct_transforms, out_dir=PREP_DIR / "ct", ext=".nii.gz", modality="CT",
    )

    print("  Preprocessing CXR series …")
    df_cohort_cxr = preprocess_series(
        df_cohort_cxr, cxr_transforms, out_dir=PREP_DIR / "cxr", ext=".npy", modality="CXR",
    )

# ══════════════════════════════════════════════════════════════════════════════
# 10. DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("6. Final cohort statistics")
print("─" * 80)


def print_cohort_stats(df: pd.DataFrame, name: str) -> list[str]:
    lines: list[str] = []

    def log_line(msg: str):
        print(msg)
        lines.append(msg)

    log_line(f"\n{'='*70}")
    log_line(name)
    log_line(f"{'='*70}")
    log_line(f"Series total : {len(df):,}")
    log_line(f"Unique cases : {df['submitter_id'].nunique():,}")

    log_line(f"\n{'-'*70}")
    log_line("PRIMARY DISEASE LABELS:")
    log_line(f"{'-'*70}")
    for lbl in IMAGING_PRIMARIES + ["normal"]:
        if lbl in df.columns:
            n   = int(df[lbl].sum())
            pct = 100 * n / len(df)
            log_line(f"  {lbl:<30}: {n:5,}  ({pct:5.1f}%)")

    log_line(f"\n{'-'*70}")
    log_line("METADATA COMORBIDITY FLAGS:")
    log_line(f"{'-'*70}")
    for lbl in METADATA_LABELS:
        if lbl in df.columns:
            n   = int(df[lbl].sum())
            pct = 100 * n / len(df)
            log_line(f"  {lbl:<30}: {n:5,}  ({pct:5.1f}%)")

    log_line(f"\n{'-'*70}")
    log_line("DEMOGRAPHICS:")
    log_line(f"{'-'*70}")
    if "sex" in df.columns:
        for val in df["sex"].dropna().unique():
            n   = (df["sex"] == val).sum()
            pct = 100 * n / len(df)
            log_line(f"  {val:<20}: {n:5,}  ({pct:5.1f}%)")
    if "age_at_index" in df.columns:
        age = pd.to_numeric(df["age_at_index"], errors="coerce").dropna()
        if len(age) > 0:
            log_line(
                f"  Age: mean={age.mean():.1f}  median={age.median():.1f}  "
                f"range=[{age.min():.0f}, {age.max():.0f}]"
            )

    log_line(f"\n{'-'*70}")
    log_line("TOP-10 LABEL CO-OCCURRENCES (primary labels):")
    log_line(f"{'-'*70}")
    combos = df[IMAGING_PRIMARIES].apply(
        lambda row: tuple(c for c in IMAGING_PRIMARIES if row[c] == 1), axis=1
    )
    for combo, cnt in Counter(combos).most_common(10):
        label = combo if combo else ("normal",)
        log_line(f"  {str(label):<65}: {cnt:>4}")

    return lines


report_ct  = print_cohort_stats(df_cohort_ct,  "CT COHORT")
report_cxr = print_cohort_stats(df_cohort_cxr, "CXR COHORT")

# ══════════════════════════════════════════════════════════════════════════════
# 11. EXPORT
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 80)
print("7. Exporting …")
print("─" * 80)

EXPORT_COLS = (
    ["object_id", "submitter_id", "modality", "case_ids_clean"]
    + DEMO_COLS
    + IMAGING_PRIMARIES
    + METADATA_LABELS
    + ["normal"]
    + (["preprocessed_path"] if "preprocessed_path" in df_cohort_ct.columns else [])
)
EXPORT_COLS = [c for c in dict.fromkeys(EXPORT_COLS) if c in df_cohort_ct.columns]

df_cohort_ct[EXPORT_COLS].to_csv(OUTPUT_DIR / "cohort_ct.csv", index=False)
print(f"✓ {OUTPUT_DIR / 'cohort_ct.csv'}")

EXPORT_COLS_CXR = [c for c in EXPORT_COLS if c in df_cohort_cxr.columns]
df_cohort_cxr[EXPORT_COLS_CXR].to_csv(OUTPUT_DIR / "cohort_cxr.csv", index=False)
print(f"✓ {OUTPUT_DIR / 'cohort_cxr.csv'}")

# Gen3 manifests
def make_manifest(df: pd.DataFrame) -> list[dict]:
    return [{"object_id": oid} for oid in df["object_id"].dropna().unique()]

with open(OUTPUT_DIR / "manifest_ct.json", "w") as f:
    json.dump(make_manifest(df_cohort_ct), f, indent=2)
print(f"✓ {OUTPUT_DIR / 'manifest_ct.json'}  ({len(df_cohort_ct):,} objects)")

with open(OUTPUT_DIR / "manifest_cxr.json", "w") as f:
    json.dump(make_manifest(df_cohort_cxr), f, indent=2)
print(f"✓ {OUTPUT_DIR / 'manifest_cxr.json'} ({len(df_cohort_cxr):,} objects)")

# Label map
label_map = {
    "primary_labels": {
        "description": (
            "Multi-label binary classification targets derived from ICD-10 "
            "conditions in the MIDRC condition node. Each label is 1 if the "
            "case carries at least one mapped ICD-10 code. Labels are chosen "
            "to correspond to distinct CT/CXR imaging phenotypes."
        ),
        "labels": {
            "covid":               "COVID-19 / SARS-CoV-2 (GGO, crazy-paving, bilateral lower-lobe predominance)",
            "bacterial_pneumonia": "Bacterial pneumonia / consolidation (lobar, bronchopneumonia, aspiration)",
            "viral_pneumonia":     "Viral/atypical pneumonia excl. COVID (bilateral GGO, interstitial infiltrates; incl. fungal/opportunistic)",
            "lung_abscess":        "Lung abscess / necrotizing pneumonia / gangrene of lung (cavitary lesion)",
            "emphysema_copd":      "Emphysema (centrilobular/panlobular) and/or COPD (hyperinflation, air trapping)",
            "ild_fibrosis":        "ILD / pulmonary fibrosis incl. sarcoidosis, hypersensitivity pneumonitis, autoimmune-ILD (reticular, honeycombing, GGO)",
            "pleural_effusion":    "Pleural effusion / empyema / hemothorax / chylothorax (blunting, layering fluid)",
            "pneumothorax":        "Pneumothorax — all types (visceral pleural line, absent lung markings)",
            "atelectasis":         "Atelectasis / lobar collapse (linear, segmental, or lobar opacification)",
            "pulm_embolism":       "Pulmonary embolism (filling defect on CTPA; RV strain on CXR)",
            "ards":                "ARDS / acute hypoxic respiratory failure (bilateral diffuse alveolar damage)",
            "lung_malignancy":     "Primary or secondary thoracic malignancy (mass, nodule, pleural thickening)",
            "normal":              "No primary imaging label (derived flag — all primary labels = 0)",
        },
        "icd10_mapping": CONDITION_PRIMARY_MAP,
    },
    "metadata_labels": {
        "description": (
            "Binary tabular side-features from comorbidity conditions. "
            "NOT used as training targets for the image classification head; "
            "available as optional tabular metadata inputs or for stratification."
        ),
        "labels": {
            "meta_heart_failure":   "Heart failure (all types/severity — systolic/diastolic/combined/right)",
            "meta_pulm_htn":        "Pulmonary hypertension / cor pulmonale",
            "meta_cardiomegaly":    "Cardiomegaly / cardiomyopathy (dilated/hypertrophic/restrictive/ischaemic/viral)",
            "meta_pulm_edema":      "Cardiogenic pulmonary oedema (acute/chronic)",
            "meta_arrhythmia":      "Cardiac arrhythmia (AF all types, flutter, VT/VF, AV block, SVT, bradycardia)",
            "meta_cad":             "Coronary artery disease / MI / ischaemic heart disease",
            "meta_valvular":        "Valvular heart disease (all valves, rheumatic/non-rheumatic, endocarditis, pericarditis)",
            "meta_hypertension":    "Essential / secondary systemic hypertension",
            "meta_diabetes":        "Diabetes mellitus (type 1, type 2, drug-induced)",
            "meta_renal":           "Chronic kidney disease (all stages) / hypertensive nephropathy",
            "meta_aortic_disease":  "Thoracic aortic aneurysm / dissection / ectasia (visible on CT)",
            "meta_autoimmune":      "Systemic autoimmune disease (SLE, scleroderma, Wegener's/GPA, polymyositis, dermatomyositis, Sjogren's)",
            "meta_transplant":      "Lung or heart transplant status (alters anatomy; raises opportunistic infection risk)",
            "meta_tb_ntm":          "Tuberculosis (active/latent) or NTM/MAC pulmonary infection",
            "meta_bronchiectasis":  "Bronchiectasis / cystic fibrosis with pulmonary manifestations",
        },
        "icd10_mapping": CONDITION_METADATA_MAP,
    },
    "design_notes": {
        "covid_separate":         "COVID gets its own label (25k+ cases, distinct GGO/crazy-paving phenotype on CT)",
        "pneumonia_split":        "Pneumonia split into bacterial (consolidation) vs viral/atypical (bilateral GGO) for imaging phenotype alignment",
        "lung_abscess_separate":  "Lung abscess kept separate — cavitary lesion is a distinct CT pattern from consolidation",
        "sarcoidosis_in_ild":     "Sarcoidosis grouped under ild_fibrosis (perilymphatic nodules + hilar adenopathy = granulomatous-fibrotic pattern)",
        "ards_definition":        "ARDS label includes all acute respiratory failure codes — broad because non-cardiogenic bilateral alveolar damage is the shared imaging phenotype",
        "pleural_effusion_broad": "Pleural effusion includes pericardial effusion (enlarged cardiac silhouette on CXR is the same radiological sign)",
        "solitary_nodule_excluded": "Solitary pulmonary nodule NOT included in lung_malignancy — unconfirmed radiological sign, not a histological diagnosis",
        "tb_ntm_as_metadata":     "TB/NTM kept as metadata due to low MIDRC prevalence (TB of lung: 3x). Promote to primary label if your enriched dataset has ≥300 confirmed cases.",
        "subcutaneous_emphysema_excluded": "Subcutaneous/interstitial emphysema (procedure-related) excluded from emphysema_copd — no pulmonary parenchymal phenotype",
    },
    "preprocessing": {
        "ct": {
            "target_spacing_mm":    list(CT_TARGET_SPACING),
            "target_shape_voxels":  list(CT_TARGET_SHAPE),
            "hu_window":            [CT_HU_WIN_LOW, CT_HU_WIN_HIGH],
            "orientation":          "RAS",
            "normalization":        "z-score (nonzero voxels, channel-wise)",
            "output_format":        "NIfTI (.nii.gz)",
        },
        "cxr": {
            "target_shape_pixels":  list(CXR_TARGET_SHAPE),
            "contrast_enhancement": "CLAHE (clip_limit=0.03)",
            "normalization":        "ImageNet-style mean/std (0.485 / 0.229)",
            "output_format":        "NumPy (.npy)",
        },
    },
}

with open(OUTPUT_DIR / "label_map.json", "w") as f:
    json.dump(label_map, f, indent=2)
print(f"✓ {OUTPUT_DIR / 'label_map.json'}")

# Text report
report_text = "\n".join(report_ct) + "\n\n" + "\n".join(report_cxr)
with open(OUTPUT_DIR / "dataset_report.txt", "w") as f:
    f.write(report_text)
print(f"✓ {OUTPUT_DIR / 'dataset_report.txt'}")

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 80)
print("DATASET CONSTRUCTION COMPLETE")
print("=" * 80)
print(f"\nOutputs in {OUTPUT_DIR}/")
print(f"  cohort_ct.csv          — {len(df_cohort_ct):,} CT  series")
print(f"  cohort_cxr.csv         — {len(df_cohort_cxr):,} CXR series")
print(f"  manifest_ct.json       — {len(make_manifest(df_cohort_ct)):,} download objects")
print(f"  manifest_cxr.json      — {len(make_manifest(df_cohort_cxr)):,} download objects")
print(f"  label_map.json         — label definitions & ICD-10 mappings")
print(f"  dataset_report.txt     — statistics & co-occurrence report")
if MONAI_AVAILABLE:
    print(f"  preprocessed/ct/       — MONAI-processed CT volumes  (.nii.gz)")
    print(f"  preprocessed/cxr/      — MONAI-processed CXR arrays  (.npy)")
print(f"\nTotal series : {len(df_cohort_ct) + len(df_cohort_cxr):,}")
print(f"Primary labels: {len(IMAGING_PRIMARIES) + 1}  (incl. 'normal')")
print(f"Metadata flags: {len(METADATA_LABELS)}")