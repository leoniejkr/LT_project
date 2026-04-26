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
study_raw = sub.export_node("Open", "A1", "imaging_study",  "tsv")
cond_raw  = sub.export_node("Open", "A1", "condition",      "tsv")
annot_raw = sub.export_node("Open", "A1", "annotation",     "tsv")

df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")
df_ct    = pd.read_csv(io.StringIO(ct_raw),    sep="\t", low_memory=False)
df_study = pd.read_csv(io.StringIO(study_raw), sep="\t", low_memory=False)
df_cond  = pd.read_csv(io.StringIO(cond_raw),  sep="\t")
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)

# ── Hilfsfunktion ──────────────────────────────────────────────
def clean_case_id(s):
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

# ── CT auf Chest filtern (per LOINC, nicht per regex) ──────────
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

# ── Labels aus condition node ──────────────────────────────────
CONDITION_LABEL_MAP = {
    # effusion
    "Pleural effusion, not elsewhere classified":                "effusion",
    "Pleural effusion":                                          "effusion",
    # pneumonia
    "Pneumonia due to coronavirus disease 2019":                 "pneumonia",
    "Pneumonia, unspecified organism":                           "pneumonia",
    "Viral pneumonia, unspecified":                              "pneumonia",
    "Pneumonia, unspecified":                                    "pneumonia",
    # fibrosis
    "Pulmonary fibrosis, unspecified":                           "fibrosis",
    "Other pulmonary fibrosis":                                  "fibrosis",
    # emphysema
    "Emphysema, unspecified":                                    "emphysema",
    "Pulmonary emphysema":                                       "emphysema",
    # atelectasis
    "Atelectasis":                                               "atelectasis",
    # opacity / ARDS
    "Acute respiratory distress syndrome":                       "opacity",
    "Other nonspecific abnormal finding of lung field":          "opacity",
    "Acute respiratory failure with hypoxia":                    "opacity",
    "Acute respiratory failure, unspecified":                    "opacity",
    # covid
    "COVID-19":                                                  "covid",
    "Emergency use of U07.1 | COVID-19":                        "covid",
    "Pneumonia due to coronavirus disease 2019":                 "covid",
    "Post COVID-19 condition, unspecified":                      "covid",
}

LABEL_COLS = list(dict.fromkeys(CONDITION_LABEL_MAP.values()))  # ordered, no dupes

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
print(df_case_labels[LABEL_COLS].sum().sort_values(ascending=False))
print(f"Cases mit mind. 1 Label: {(df_case_labels[LABEL_COLS].sum(axis=1) > 0).sum()}")

# ── Annotation node: COVID pneumonia + mRALE ───────────────────
# ct_series_files.submitter_id verknüpft direkt mit df_ct.submitter_id
df_annot_ct = df_annot[df_annot["ct_series_files.submitter_id"].notna()].copy()
df_annot_ct = df_annot_ct[["ct_series_files.submitter_id",
                            "class_covid19_pneumonia",
                            "airspace_disease_grading",
                            "midrc_mRALE_score"]].drop_duplicates("ct_series_files.submitter_id")

print(f"\nAnnotationen für CT-Serien: {len(df_annot_ct)}")
print(df_annot_ct["class_covid19_pneumonia"].value_counts())
print(df_annot_ct["airspace_disease_grading"].value_counts())

# ── Alles mergen ───────────────────────────────────────────────
# ── Alles mergen ───────────────────────────────────────────────
# 1) Case-Demographie
df_cases_unique = df_cases.drop_duplicates("submitter_id")
df_chest = df_chest.merge(
    df_cases_unique[["submitter_id","covid19_positive","sex","age_at_index","race",
                     "icu_indicator","ventilator_indicator"]],
    left_on="case_ids_clean", right_on="submitter_id", how="left",
    suffixes=("", "_case")
)

# 2) Condition-Labels
df_chest = df_chest.merge(df_case_labels, on="case_ids_clean", how="left")

# 3) Annotation direkt auf Serie-Ebene
df_chest = df_chest.merge(
    df_annot_ct,
    left_on="submitter_id", right_on="ct_series_files.submitter_id", how="left"
)

# Fehlende Labels als 0
for col in LABEL_COLS:
    df_chest[col] = df_chest[col].fillna(0).astype(int)

# covid auch aus covid19_positive absichern
df_chest["covid"] = (
    (df_chest["covid"] == 1) |
    (df_chest["covid19_positive"].str.lower() == "yes")
).astype(int)

# normal: kein einziges Label gesetzt
df_chest["normal"] = (df_chest[LABEL_COLS].sum(axis=1) == 0).astype(int)

ALL_LABEL_COLS = LABEL_COLS + ["normal"]

print("\n=== Label-Verteilung (Serie-Ebene, alle CT Chest) ===")
print(df_chest[ALL_LABEL_COLS].sum().sort_values(ascending=False))
print(f"\nSerien gesamt: {len(df_chest)}")

# ── Kohorte balancieren ────────────────────────────────────────
N_PER_LABEL = 150

df_unique = df_chest.drop_duplicates("object_id").copy().reset_index(drop=True)
anomaly_list = LABEL_COLS  # alles außer "normal"

balanced_frames = []
for anomaly_type in anomaly_list:
    pool = df_unique[df_unique[anomaly_type] == 1]
    n = min(N_PER_LABEL, len(pool))
    if n > 0:
        balanced_frames.append(pool.sample(n=n, random_state=42))
        print(f"{anomaly_type:<20}: {n} aus Pool ({len(pool)} verfügbar)")
    else:
        print(f"{anomaly_type:<20}: KEINE Samples!")

# Normal dazu
normal_pool = df_unique[df_unique["normal"] == 1]
n_normal = min(N_PER_LABEL, len(normal_pool))
if n_normal > 0:
    balanced_frames.append(normal_pool.sample(n=n_normal, random_state=42))
    print(f"{'normal':<20}: {n_normal} aus Pool ({len(normal_pool)} verfügbar)")

df_cohort = pd.concat(balanced_frames).drop_duplicates("object_id").reset_index(drop=True)
df_cohort["n_anomalies"] = df_cohort[anomaly_list].sum(axis=1)

print(f"\n=== Finale Kohorte ===")
print(f"Serien gesamt: {len(df_cohort)}")
print("\n=== Ground-Truth Label-Verteilung ===")
for col in ALL_LABEL_COLS:
    count = int(df_cohort[col].sum())
    pct   = 100 * count / len(df_cohort)
    print(f"{col:<20}: {count:4d} ({pct:5.1f}%)")

print("\n=== Top 10 Label-Kombinationen ===")
combos = df_cohort[anomaly_list].apply(
    lambda x: tuple(col for col in anomaly_list if x[col] == 1), axis=1
)
for combo, count in Counter(combos).most_common(10):
    label = combo if combo else ("normal",)
    print(f"  {label}: {count}")

# ── Export ─────────────────────────────────────────────────────
manifest = [{"object_id": oid} for oid in df_cohort["object_id"].dropna()]
with open("data/manifest_multilabel.json", "w") as f:
    json.dump(manifest, f, indent=2)
df_cohort.to_csv("data/cohort_multilabel.csv", index=False)

print(f"\n✓ {len(manifest)} Serien exportiert")
print("✓ cohort_multilabel.csv gespeichert")