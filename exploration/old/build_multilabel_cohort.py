import pandas as pd
import io, json
from collections import Counter
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api  = "https://data.midrc.org"
auth = Gen3Auth(api, refresh_file="credentials.json")
sub  = Gen3Submission(api, auth)

# ── Daten laden ────────────────────────────────────────────────
cases_raw = sub.export_node("Open", "A1", "case",           "tsv")
ct_raw    = sub.export_node("Open", "A1", "ct_series_file", "tsv")
cr_raw    = sub.export_node("Open", "A1", "cr_series_file", "tsv")
study_raw = sub.export_node("Open", "A1", "imaging_study",  "tsv")
cond_raw  = sub.export_node("Open", "A1", "condition",      "tsv")
annot_raw = sub.export_node("Open", "A1", "annotation",     "tsv")

df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")
df_ct    = pd.read_csv(io.StringIO(ct_raw),    sep="\t", low_memory=False)
df_cr    = pd.read_csv(io.StringIO(cr_raw),    sep="\t", low_memory=False)
df_study = pd.read_csv(io.StringIO(study_raw), sep="\t", low_memory=False)
df_cond  = pd.read_csv(io.StringIO(cond_raw),  sep="\t")
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)

# ── Hilfsfunktion ──────────────────────────────────────────────
def clean_case_id(s):
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

# ── CT auf Chest filtern ───────────────────────────────────────
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

df_study["case_ids_clean"] = df_study["case_ids"].apply(clean_case_id)
df_study_chest = df_study[df_study["loinc_long_common_name"].isin(CT_CHEST_LOINC)]
chest_study_ids = set(df_study_chest["case_ids_clean"])

df_ct["case_ids_clean"] = df_ct["case_ids"].apply(clean_case_id)
df_chest = df_ct[df_ct["case_ids_clean"].isin(chest_study_ids)].copy().reset_index(drop=True)

print(f"CT Chest Serien: {len(df_chest)}")


GROUP_LABEL_MAP = {
    "Infectious_Lung": ["covid", "pneumonia"],
    "Airspace_Disease": ["pneumonia", "ards", "pulm_edema"],
    "Pleural_Disease": ["effusion", "pneumothorax"],
    "Parenchymal_Lung": ["atelectasis", "fibrosis", "emphysema"],
    "Vascular_Lung": ["pulm_embolism"],
}

def apply_groups(df, group_map):
    for group, labels in group_map.items():
        df[group] = df[labels].sum(axis=1).clip(upper=1)
    return df

# ══════════════════════════════════════════════════════════════════
# UPDATED CONDITION LABEL MAP — synonym-aware, based on real counts
# ══════════════════════════════════════════════════════════════════
#
# Changes vs. v1:
#   fibrosis  — now includes interstitial lung disease umbrella codes
#               (+954 ILD unspec, +612 ILD w/ fibrosis, +360 other ILD)
#               Combined pool ~2,600 → well above training threshold
#   effusion  — added malignant pleural effusion + pleural effusion in
#               other conditions (adds ~430 records)
#   pneumonia — added all organism-specific pneumonia codes, lobar pneumonia,
#               hypersensitivity pneumonitis, cryptogenic organizing pneumonia
#   emphysema — added all subtypes (centrilobular, panlobular, other)
#   covid     — now captures all 4 COVID ICD-10 code variants including
#               the emergency U07.1 code
#   pneumothorax — good CT signature, ~1,000 records across codes
#   pulm_embolism — strong CTA finding, ~2,000+ records
#   ards 
#   resp_failure — Clinical labels (metadata)
#
CONDITION_LABEL_MAP = {

    # ── COVID (all synonym codes) ──────────────────────────────
    "COVID-19":                                                  "covid",
    "Emergency use of U07.1 | COVID-19":                        "covid",
    "Pneumonia due to coronavirus disease 2019":                 "covid",
    "Post COVID-19 condition, unspecified":                      "covid",
    "SARS-associated coronavirus as the cause of diseases classified elsewhere": "covid",

    # ── Effusion (all pleural effusion codes) ─────────────────
    "Pleural effusion, not elsewhere classified":                "effusion",
    "Pleural effusion":                                          "effusion",
    "Pleural effusion in other conditions classified elsewhere": "effusion",
    "Malignant pleural effusion":                                "effusion",
    "Chylous effusion":                                          "effusion",
    "Unspecified pleural effusion":                              "effusion",
    "Hemothorax":                                                "effusion",   # blood in pleural space — same compartment
    "Pyothorax without fistula":                                 "effusion",   # pus in pleural space
    "Pyothorax with fistula":                                    "effusion",
    "Other specified pleural conditions":                        "effusion",
    "Pericardial effusion (noninflammatory)":                    "effusion",

    # ── Pneumonia (organism-specific + generic codes) ──────────
    "Pneumonia, unspecified organism":                           "pneumonia",
    "Pneumonia, unspecified":                                    "pneumonia",
    "Viral pneumonia, unspecified":                              "pneumonia",
    "Other viral pneumonia":                                     "pneumonia",
    "Lobar pneumonia, unspecified organism":                     "pneumonia",
    "Unspecified bacterial pneumonia":                           "pneumonia",
    "Pneumonia due to Pseudomonas":                              "pneumonia",
    "Pneumonia due to Klebsiella pneumoniae":                    "pneumonia",
    "Pneumonia due to Methicillin susceptible Staphylococcus aureus": "pneumonia",
    "Pneumonia due to Methicillin resistant Staphylococcus aureus":   "pneumonia",
    "Pneumonia due to other Gram-negative bacteria":             "pneumonia",
    "Pneumonia due to Escherichia coli":                         "pneumonia",
    "Pneumonia due to Hemophilus influenzae":                    "pneumonia",
    "Pneumonia due to Streptococcus pneumoniae":                 "pneumonia",
    "Pneumonia due to other streptococci":                       "pneumonia",
    "Pneumonia due to other specified bacteria":                 "pneumonia",
    "Pneumonia due to other specified infectious organisms":     "pneumonia",
    "Ventilator associated pneumonia":                           "pneumonia",
    "Pneumonitis due to inhalation of food and vomit":           "pneumonia",
    "Pneumonitis due to inhalation of food or vomitus":          "pneumonia",
    "Other pneumonia, unspecified organism":                     "pneumonia",
    "Pneumonia in diseases classified elsewhere":                "pneumonia",
    "Hypostatic pneumonia, unspecified organism":                "pneumonia",
    "Bronchopneumonia, unspecified organism":                    "pneumonia",
    "Respiratory syncytial virus pneumonia":                     "pneumonia",
    "Human metapneumovirus pneumonia":                           "pneumonia",
    "Cryptogenic organizing pneumonia":                          "pneumonia",
    "Hypersensitivity pneumonitis due to unspecified organic dust": "pneumonia",
    "Acute interstitial pneumonitis":                            "pneumonia",
    "Idiopathic non-specific interstitial pneumonitis":          "pneumonia",
    "Respiratory bronchiolitis interstitial lung disease":       "pneumonia",
    "Lymphoid interstitial pneumonia":                           "pneumonia",
    "Pneumonia due to SARS-associated coronavirus":              "pneumonia",

    # ── Fibrosis (EXPANDED — now includes ILD umbrella codes) ──
    # v1 only had 2 codes (~550 records). v2 adds ILD codes → ~2,600 total.
    "Pulmonary fibrosis, unspecified":                           "fibrosis",
    "Other pulmonary fibrosis":                                  "fibrosis",
    "Idiopathic pulmonary fibrosis":                             "fibrosis",
    "Interstitial pulmonary disease, unspecified":               "fibrosis",   # +954
    "Other interstitial pulmonary diseases with fibrosis in diseases classified elsewhere": "fibrosis",  # +612
    "Other specified interstitial pulmonary diseases":           "fibrosis",   # +360
    "Postinflammatory pulmonary fibrosis":                       "fibrosis",
    "Chronic drug-induced interstitial lung disorders":          "fibrosis",
    "Drug-induced interstitial lung disorders, unspecified":     "fibrosis",
    "Interstitial lung disease with progressive fibrotic phenotype in diseases classified elsewhere": "fibrosis",
    "Other interstitial lung diseases of childhood":             "fibrosis",
    "Sarcoidosis of lung":                                       "fibrosis",   # granulomatous ILD
    "Sarcoidosis, unspecified":                                  "fibrosis",
    "Sarcoidosis of lung with sarcoidosis of lymph nodes":       "fibrosis",
    "Sarcoidosis of other sites":                                "fibrosis",
    "Wegener's granulomatosis without renal involvement":        "fibrosis",
    "Wegener's granulomatosis with renal involvement":           "fibrosis",
    "Pulmonary alveolar microlithiasis":                         "fibrosis",
    "Asbestosis":                                                "fibrosis",
    "Pneumoconiosis due to asbestos and other mineral fibers":   "fibrosis",
    "Unspecified pneumoconiosis":                                "fibrosis",
    "Pulmonary mycobacterial infection":                         "fibrosis",   # often causes ILD pattern

    # ── Emphysema (all subtypes) ───────────────────────────────
    "Emphysema, unspecified":                                    "emphysema",
    "Pulmonary emphysema":                                       "emphysema",
    "Centrilobular emphysema":                                   "emphysema",
    "Panlobular emphysema":                                      "emphysema",
    "Other emphysema":                                           "emphysema",
    "Interstitial emphysema":                                    "emphysema",
    "Unilateral pulmonary emphysema [MacLeod's syndrome]":       "emphysema",

    # ── Atelectasis ────────────────────────────────────────────
    "Atelectasis":                                               "atelectasis",
    "Other pulmonary collapse":                                  "atelectasis",
    "Pulmonary collapse":                                        "atelectasis",

    # ── Respiratory failure (clinical state) ────────────────────.  
    # Note: not a specific CT finding, but often present in severe cases + important clinical outcome !!!
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
    "Acute respiratory failure":                                 "resp_failure",

    # --strong imaging pattern, but rare + noisy labels MAYBE --> ignore for now, or move to separate "ARDS" label?
    "Acute respiratory distress syndrome" : "ards",
    "Acute respiratory distress" : "ards",


    # ── NEW: Pneumothorax (~1,000 records combined) ────────────
    "Pneumothorax, unspecified":                                 "pneumothorax",
    "Other pneumothorax":                                        "pneumothorax",
    "Spontaneous tension pneumothorax":                          "pneumothorax",
    "Primary spontaneous pneumothorax":                          "pneumothorax",
    "Secondary spontaneous pneumothorax":                        "pneumothorax",
    "Postprocedural pneumothorax":                               "pneumothorax",
    "Chronic pneumothorax":                                      "pneumothorax",
    "Other air leak":                                            "pneumothorax",
    "Other pneumothorax and air leak":                           "pneumothorax",
    "Postprocedural air leak":                                   "pneumothorax",

    # ── NEW: Pulmonary embolism (~2,000+ records) ──────────────
    "Other pulmonary embolism without acute cor pulmonale":      "pulm_embolism",
    "Other pulmonary embolism with acute cor pulmonale":         "pulm_embolism",
    "Single subsegmental pulmonary embolism without acute cor pulmonale": "pulm_embolism",
    "Multiple subsegmental pulmonary emboli without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery without acute cor pulmonale": "pulm_embolism",
    "Saddle embolus of pulmonary artery with acute cor pulmonale": "pulm_embolism",
    "Chronic pulmonary embolism":                                "pulm_embolism",
    "Septic pulmonary embolism without acute cor pulmonale":     "pulm_embolism",
    "Septic pulmonary embolism with acute cor pulmonale":        "pulm_embolism",
    "Other pulmonary embolism and infarction":                   "pulm_embolism",

    # # ── NEW: Pulmonary hypertension (~1,200 records) ───────────       Invisible, useless
    #       NOPE, bc not visible on CT scan
    # "Pulmonary hypertension, unspecified":                       "pulm_hypertension",
    # "Primary pulmonary hypertension":                            "pulm_hypertension",
    # "Secondary pulmonary arterial hypertension":                 "pulm_hypertension",
    # "Pulmonary hypertension due to lung diseases and hypoxia":   "pulm_hypertension",
    # "Pulmonary hypertension due to left heart disease":          "pulm_hypertension",
    # "Secondary pulmonary hypertension":                          "pulm_hypertension",
    # "Other secondary pulmonary hypertension":                    "pulm_hypertension",
    # "Chronic thromboembolic pulmonary hypertension":             "pulm_hypertension",
    # "Cor pulmonale (chronic)":                                   "pulm_hypertension",
    # "Other diseases of pulmonary vessels":                       "pulm_hypertension",

    # ── Pulmonary edema (new standalone label) ─────────────────
    "Chronic pulmonary edema":                                   "pulm_edema",
    "Acute pulmonary edema":                                     "pulm_edema",
}

LABEL_COLS = list(dict.fromkeys(CONDITION_LABEL_MAP.values()))  # ordered, no dupes
print(f"\nLabels ({len(LABEL_COLS)}): {LABEL_COLS}")

# ── Labels aus condition node bauen ───────────────────────────
def build_condition_labels(df_cond, label_map):
    label_set = list(dict.fromkeys(label_map.values()))
    df_cond = df_cond.copy()
    df_cond["case_ids_clean"] = df_cond["case_ids"].apply(clean_case_id)

    rows = []
    for case_id, grp in df_cond.groupby("case_ids_clean"):
        conditions = set(grp["condition_name"].tolist())
        row = {"case_ids_clean": case_id}
        for label in label_set:
            row[label] = int(any(label_map.get(c) == label for c in conditions))
        rows.append(row)

    return pd.DataFrame(rows)

df_case_labels = build_condition_labels(df_cond, CONDITION_LABEL_MAP)

print("\n=== Label-Verteilung (Case-Ebene) ===")
print(df_case_labels[LABEL_COLS].sum().sort_values(ascending=False).to_string())
print(f"\nCases mit mind. 1 Label: {(df_case_labels[LABEL_COLS].sum(axis=1) > 0).sum()}")

# ── Annotation node: COVID pneumonia + mRALE ───────────────────
df_annot_ct = df_annot[df_annot["ct_series_files.submitter_id"].notna()].copy()
df_annot_ct = df_annot_ct[[
    "ct_series_files.submitter_id",
    "class_covid19_pneumonia",
    "airspace_disease_grading",
    "midrc_mRALE_score"
]].drop_duplicates("ct_series_files.submitter_id")

print(f"\nAnnotationen für CT-Serien: {len(df_annot_ct)}")
print(df_annot_ct["class_covid19_pneumonia"].value_counts())
print(df_annot_ct["airspace_disease_grading"].value_counts())

# ── Alles mergen ───────────────────────────────────────────────
df_cases_unique = df_cases.drop_duplicates("submitter_id")
df_chest = df_chest.merge(
    df_cases_unique[[
        "submitter_id", "covid19_positive", "sex", "age_at_index", "race",
        "icu_indicator", "ventilator_indicator"
    ]],
    left_on="case_ids_clean", right_on="submitter_id", how="left",
    suffixes=("", "_case")
)

df_chest = df_chest.merge(df_case_labels, on="case_ids_clean", how="left")

df_chest = apply_groups(df_chest, groups)

df_chest = df_chest.merge(
    df_annot_ct,
    left_on="submitter_id", right_on="ct_series_files.submitter_id", how="left"
)

for col in LABEL_COLS:
    df_chest[col] = df_chest[col].fillna(0).astype(int)

# covid auch aus covid19_positive absichern
df_chest["covid"] = (
    (df_chest["covid"] == 1) |
    (df_chest["covid19_positive"].fillna("").str.lower() == "yes")
).astype(int)

# normal: kein einziges Label gesetzt
IMAGING_LABELS = [l for l in LABEL_COLS if l not in {"resp_failure"}]

df_chest["normal"] = (df_chest[IMAGING_LABELS].sum(axis=1) == 0).astype(int)

ALL_LABEL_COLS = LABEL_COLS + ["normal"]

print("\n=== Label-Verteilung (Serie-Ebene, alle CT Chest) ===")
print(df_chest[ALL_LABEL_COLS].sum().sort_values(ascending=False).to_string())
print(f"\nSerien gesamt: {len(df_chest)}")

# ── Kohorte balancieren ────────────────────────────────────────
# Tiered N: more common labels get capped lower to keep balance
TIER_N = {
    "covid":            200,
    "pneumonia":        200,
    "effusion":         200,
    "atelectasis":      175,
    "fibrosis":         175,   # larger pool now → can afford more
    "pulm_embolism":    150,
    "emphysema":        100,   # smaller pool, use what we have
    "pneumothorax":     150,
    "pulm_edema":       100,
    "normal":           200,
    "ards":             100,    # maybe expcude bc very rare and noisy , but strong imaging pattern when present
}

NON_IMAGING_LABELS = {"resp_failure"}

ANOMALY_LABELS = [l for l in LABEL_COLS if l not in NON_IMAGING_LABELS] # still keep resp_failure in dataset, but don’t train on it
df_unique = df_chest.drop_duplicates("object_id").copy().reset_index(drop=True)

balanced_frames = []
print("\n=== Sampling ===")
for label in ANOMALY_LABELS:
    pool = df_unique[df_unique[label] == 1]
    n = min(TIER_N.get(label, 150), len(pool))
    if n > 0:
        balanced_frames.append(pool.sample(n=n, random_state=42))
        print(f"  {label:<20}: {n:>3} sampled  (pool: {len(pool)})")
    else:
        print(f"  {label:<20}: KEINE Samples!")

normal_pool = df_unique[df_unique["normal"] == 1]
n_normal = min(TIER_N.get("normal", 200), len(normal_pool))
if n_normal > 0:
    balanced_frames.append(normal_pool.sample(n=n_normal, random_state=42))
    print(f"  {'normal':<20}: {n_normal:>3} sampled  (pool: {len(normal_pool)})")

df_cohort = pd.concat(balanced_frames).drop_duplicates("object_id").reset_index(drop=True)
df_cohort["n_labels"] = df_cohort[ANOMALY_LABELS].sum(axis=1)

print(f"\n=== Finale Kohorte ===")
print(f"Serien gesamt: {len(df_cohort)}")

print("\n=== Ground-Truth Label-Verteilung ===")
for col in ALL_LABEL_COLS:
    count = int(df_cohort[col].sum())
    pct   = 100 * count / len(df_cohort)
    print(f"  {col:<22}: {count:4d} ({pct:5.1f}%)")

print("\n=== Top 10 Label-Kombinationen ===")
combos = df_cohort[ANOMALY_LABELS].apply(
    lambda x: tuple(col for col in ANOMALY_LABELS if x[col] == 1), axis=1
)
for combo, count in Counter(combos).most_common(10):
    label = combo if combo else ("normal",)
    print(f"  {label}: {count}")

# ── Synonym-Analyse: zeige welche condition_name Codes gefunden wurden ────
print("\n=== Condition codes gefunden pro Label ===")
df_cond_clean = df_cond.copy()
df_cond_clean["case_ids_clean"] = df_cond_clean["case_ids"].apply(clean_case_id)
cohort_cases = set(df_cohort["case_ids_clean"].dropna())
df_cond_cohort = df_cond_clean[df_cond_clean["case_ids_clean"].isin(cohort_cases)]

for label in LABEL_COLS:
    codes_for_label = {k for k, v in CONDITION_LABEL_MAP.items() if v == label}
    found = df_cond_cohort[df_cond_cohort["condition_name"].isin(codes_for_label)]["condition_name"].value_counts()
    if len(found) > 0:
        print(f"\n  [{label}]")
        for code, cnt in found.items():
            print(f"    {cnt:>5}x  {code}")

# ── Export ─────────────────────────────────────────────────────
import os
os.makedirs("data", exist_ok=True)

manifest = [{"object_id": oid} for oid in df_cohort["object_id"].dropna()]
with open("data/manifest_multilabel_v2.json", "w") as f:
    json.dump(manifest, f, indent=2)

df_cohort.to_csv("data/cohort_multilabel_v2.csv", index=False)

# Label map als JSON exportieren (nützlich für spätere Inference)
with open("data/label_map_v2.json", "w") as f:
    json.dump({
        "condition_label_map": CONDITION_LABEL_MAP,
        "label_cols": LABEL_COLS,
        "all_label_cols": ALL_LABEL_COLS,
    }, f, indent=2)

print(f"\n✓ {len(manifest)} Serien exportiert")
print("✓ data/cohort_multilabel_v2.csv")
print("✓ data/manifest_multilabel_v2.json")
print("✓ data/label_map_v2.json")