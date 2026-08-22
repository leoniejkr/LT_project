import os
import numpy as np
import pandas as pd

# Define the full 15-class multi-label taxonomy
NIH_CLASSES = [
    'Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion',
    'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule',
    'Pleural_Thickening', 'Pneumonia', 'Pneumothorax'
]
ALL_CLASSES = NIH_CLASSES + ['Covid']

# ── MIXING CONFIGURATION ───────────────────────────────────────────────────
# Set ratio of NIH (non-COVID) to MIDRC (COVID) images.
# Example: 2.0 = 2 NIH images for every 1 MIDRC image (33% COVID overall).
# Set to 1.0 for an exact 50/50 balance.
RATIO_NIH_TO_MIDRC = 2.0
RANDOM_SEED = 42

# 1. Read Kaggle NIH Metadata
nih_dir = "/Users/leoniejunkherr/.cache/kagglehub/datasets/nih-chest-xrays/data/versions/3"
df_nih_raw = pd.read_csv(os.path.join(nih_dir, "Data_Entry_2017.csv"))

# Parse pipe-separated pathologies into binary columns
labels_dummies = df_nih_raw["Finding Labels"].str.get_dummies(sep="|")
df_nih = pd.concat([df_nih_raw, labels_dummies], axis=1)

# Build lookup map of image file locations
print("Scanning NIH cache directory for image locations...")
image_path_map = {}
for root, dirs, files in os.walk(nih_dir):
    for file in files:
        if file.endswith(".png"):
            image_path_map[file] = os.path.join(root, file)

print(f"Located {len(image_path_map)} total NIH images locally.")

# Clean and map NIH dataframe
df_nih_clean = pd.DataFrame()
df_nih_clean['img_path'] = df_nih['Image Index'].map(image_path_map)
df_nih_clean['patient_id'] = df_nih['Patient ID'].astype(str)
df_nih_clean['view_position'] = df_nih['View Position'].astype(str)

# Keep downloaded files only
df_nih_clean = df_nih_clean.dropna(subset=['img_path']).reset_index(drop=True)

# Quality filter: keep front-facing views only (PA / AP) to align with MIDRC
df_nih_clean = df_nih_clean[
    df_nih_clean['view_position'].str.upper().isin(['PA', 'AP'])
].reset_index(drop=True)

for cls in NIH_CLASSES:
    df_nih_clean[cls] = df_nih[cls] if cls in df_nih.columns else 0
df_nih_clean['Covid'] = 0


# 2. Read processed MIDRC COVID Manifest
df_midrc = pd.read_csv("data_hybrid/midrc_processed_manifest.csv")

df_midrc_clean = pd.DataFrame()
df_midrc_clean['img_path'] = df_midrc['img_path']
df_midrc_clean['patient_id'] = df_midrc['patient_id'].astype(str)
df_midrc_clean['view_position'] = df_midrc.get('view_position', 'AP')

for cls in NIH_CLASSES:
    df_midrc_clean[cls] = 0
df_midrc_clean['Covid'] = 1


# 3. Patient-Level Stratified Mixing
num_midrc_imgs = len(df_midrc_clean)
print(f"\nMIDRC COVID Images Loaded: {num_midrc_imgs}")

if RATIO_NIH_TO_MIDRC is not None:
    target_nih_count = int(num_midrc_imgs * RATIO_NIH_TO_MIDRC)
    
    # Randomly select NIH patients (not isolated images) to prevent patient leakage
    unique_nih_patients = df_nih_clean['patient_id'].unique()
    np.random.seed(RANDOM_SEED)
    shuffled_patients = np.random.permutation(unique_nih_patients)
    
    selected_patients = []
    accumulated_count = 0
    for pid in shuffled_patients:
        selected_patients.append(pid)
        accumulated_count += (df_nih_clean['patient_id'] == pid).sum()
        if accumulated_count >= target_nih_count:
            break

    df_nih_balanced = df_nih_clean[
        df_nih_clean['patient_id'].isin(selected_patients)
    ].reset_index(drop=True)
    print(f"Balanced NIH Subsample: {len(df_nih_balanced)} images across {len(selected_patients)} patients.")
else:
    df_nih_balanced = df_nih_clean


# 4. Concatenate and Export
df_master = pd.concat([df_nih_balanced, df_midrc_clean], axis=0).reset_index(drop=True)

print("\n" + "=" * 50)
print("COMBINED DATASET SUMMARY")
print("=" * 50)
print(f"Total Combined Master Rows: {len(df_master)}")
print(f"COVID (MIDRC) Cases:       {df_master['Covid'].sum()} ({df_master['Covid'].mean():.1%})")
print(f"Non-COVID (NIH) Cases:     {(df_master['Covid'] == 0).sum()} ({(1 - df_master['Covid'].mean()):.1%})")
print("\nPathology Distribution:")
print(df_master[ALL_CLASSES].sum())

df_master.to_csv("data_hybrid/combined_master.csv", index=False)
print("\nSaved balanced dataset to: data_hybrid/combined_master.csv")