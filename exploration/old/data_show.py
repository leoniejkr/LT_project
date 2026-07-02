import pydicom
import matplotlib.pyplot as plt
import pandas as pd
import os
from collections import defaultdict

LABEL_COLS = [
    'covid', 'effusion', 'pneumonia', 'fibrosis', 'emphysema',
    'atelectasis', 'opacity', 'normal'
]

# ── Metadaten laden ────────────────────────────────────────────
df_meta = pd.read_csv("data/cohort_multilabel.csv")
for col in LABEL_COLS:
    if col in df_meta.columns:
        df_meta[col] = df_meta[col].fillna(0).astype(int)

# ── Debug: PatientID vs case_ids_clean ────────────────────────
sample_dcm = next(
    os.path.join(r, f)
    for r, _, files in os.walk("dicom_data")
    for f in files if f.endswith(".dcm")
)
ds = pydicom.dcmread(sample_dcm, stop_before_pixels=True)
print("PatientID in DICOM:          ", ds.get("PatientID"))
print("case_ids_clean sample in CSV:", df_meta["case_ids_clean"].head(3).tolist())
print("object_id sample in CSV:     ", df_meta["object_id"].head(3).tolist())



# ── DCMs gruppieren ────────────────────────────────────────────
dcm_by_object = defaultdict(list)

dcm_by_case = defaultdict(list)
for root, dirs, files in os.walk("dicom_data"):
    for f in files:
        if f.endswith(".dcm"):
            path = os.path.join(root, f).replace("\\", "/")
            parts = path.split("/")
            case_id = parts[1]  # dicom_data/<case_id>/...
            dcm_by_case[case_id].append(path)

print(f"Serien gefunden: {len(dcm_by_case)}")
print(f"Beispiel case_id: {list(dcm_by_case.keys())[0]}")

# ── Lookup by case_ids_clean (matched via PatientID in DICOM) ─
meta_lookup = {str(row["case_ids_clean"]): row for _, row in df_meta.iterrows()}

for case_id, dcm_files in dcm_by_case.items():
    row = meta_lookup.get(case_id)  # direct match, no DICOM read needed

    if row is not None:
        sex           = row.get("sex", "?")
        age           = int(row["age_at_index"]) if pd.notna(row.get("age_at_index")) else "?"
        active_labels = [col for col in LABEL_COLS if row.get(col, 0) == 1]
        label_str     = "+".join(active_labels) if active_labels else "unlabeled"
    else:
        sex, age, label_str = "anon", "?", "unknown"
        print(f"  ⚠ Kein Match für case_id='{case_id}'")

    dcm_files_sorted = sorted(dcm_files)
    batch_size = 6
    n_batches  = (len(dcm_files_sorted) + batch_size - 1) // batch_size

    safe_label = label_str.replace("/", "-")[:80]
    person_dir = f"dicom_previews/{case_id}_{safe_label}_{sex}_{age}y"
    os.makedirs(person_dir, exist_ok=True)

    for batch_idx in range(n_batches):
        batch = dcm_files_sorted[batch_idx * batch_size : (batch_idx + 1) * batch_size]

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()

        for i, dcm_path in enumerate(batch):
            try:
                ds  = pydicom.dcmread(dcm_path)
                img = ds.pixel_array.astype(float)
                img = (img - img.min()) / (img.max() - img.min() + 1e-8)
                axes[i].imshow(img, cmap="gray")
                axes[i].set_title(ds.get("SeriesDescription", "?"), fontsize=7)
            except Exception as e:
                axes[i].set_title(f"Fehler: {e}", fontsize=6)
            axes[i].axis("off")

        for j in range(len(batch), batch_size):
            axes[j].axis("off")

        plt.suptitle(
            f"{case_id} | {sex} | {age}y | {label_str}  [{batch_idx+1}/{n_batches}]",
            fontsize=9
        )
        plt.tight_layout()
        plt.savefig(f"{person_dir}/slices_{batch_idx+1:03d}.png", dpi=100)
        plt.close()

    print(f"✓ {case_id} | {label_str} | {len(dcm_files)} Slices → {n_batches} PNGs")

print("\n✓ Fertig!")