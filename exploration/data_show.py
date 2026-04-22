import pydicom
import matplotlib.pyplot as plt
import pandas as pd
import os
from collections import defaultdict

df_meta = pd.read_csv("data/cohort_balanced.csv")
meta_lookup = {row["case_ids_clean"]: row for _, row in df_meta.iterrows()}

# Alle DCMs nach case_id gruppieren
dcm_by_case = defaultdict(list)
for root, dirs, files in os.walk("dicom_data"):
    for f in files:
        if f.endswith(".dcm"):
            path = os.path.join(root, f)
            case_id = path.split("/")[1]
            dcm_by_case[case_id].append(path)

print(f"Personen: {len(dcm_by_case)}")

os.makedirs("dicom_previews", exist_ok=True)

for case_id, dcm_files in dcm_by_case.items():
    row = meta_lookup.get(case_id)
    if row is not None:
        sex   = row["sex"]
        age = int(row["age_at_index"]) if pd.notna(row["age_at_index"]) else "?"
        covid = row["covid19_positive"]
    else:
        sex, age, covid = "anon", "?", "?"

    # Pro Person: alle Slices in 6er-Grids
    batch_size = 6
    n_batches = (len(dcm_files) + batch_size - 1) // batch_size

    person_dir = f"dicom_previews/{case_id}_COVID-{covid}_{sex}_{age}y"
    os.makedirs(person_dir, exist_ok=True)

    for batch_idx in range(n_batches):
        batch = dcm_files[batch_idx * batch_size : (batch_idx + 1) * batch_size]

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()

        for i, dcm_path in enumerate(batch):
            try:
                ds = pydicom.dcmread(dcm_path)
                img = ds.pixel_array.astype(float)
                img = (img - img.min()) / (img.max() - img.min())
                series = ds.get("SeriesDescription", "?")
                axes[i].imshow(img, cmap="gray")
                axes[i].set_title(f"{series}", fontsize=7)
            except Exception as e:
                axes[i].set_title(f"Fehler", fontsize=7)
            axes[i].axis("off")

        for j in range(len(batch), batch_size):
            axes[j].axis("off")

        plt.suptitle(f"{case_id} | {sex} | {age}y | COVID: {covid}  [{batch_idx+1}/{n_batches}]", fontsize=9)
        plt.tight_layout()
        plt.savefig(f"{person_dir}/slices_{batch_idx+1:03d}.png", dpi=100)
        plt.close()

    print(f"✓ {case_id}: {len(dcm_files)} Slices → {n_batches} PNGs")

print("\n✓ Fertig!")