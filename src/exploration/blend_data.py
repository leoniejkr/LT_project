import pandas as pd
import os

# Define the full 15-class multi-label taxonomy
NIH_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax']
ALL_CLASSES = NIH_CLASSES + ['Covid']

# 1. Read Kaggle NIH Metadata
nih_dir = "/Users/leoniejunkherr/.cache/kagglehub/datasets/nih-chest-xrays/data/versions/3" 
df_nih_raw = pd.read_csv(os.path.join(nih_dir, "Data_Entry_2017.csv"))

# Parse pipe-separated pathologies into binary columns
labels_dummies = df_nih_raw["Finding Labels"].str.get_dummies(sep="|")
df_nih = pd.concat([df_nih_raw, labels_dummies], axis=1)

# Build a fast lookup map of every image file inside the NIH directory
print("Scanning NIH cache directory for image locations (this may take a minute)...")
image_path_map = {}
for root, dirs, files in os.walk(nih_dir):
    for file in files:
        if file.endswith(".png"):
            image_path_map[file] = os.path.join(root, file)

print(f"Located {len(image_path_map)} total NIH images locally.")

# Map paths dynamically
df_nih_clean = pd.DataFrame()

# 🧠 Fix: Instead of assuming /images/, pull the path directly from our lookup map!
df_nih_clean['img_path'] = df_nih['Image Index'].map(image_path_map)
df_nih_clean['patient_id'] = df_nih['Patient ID'].astype(str)

# Drop any rows where the image file was missing from disk
initial_len = len(df_nih_clean)
df_nih_clean = df_nih_clean.dropna(subset=['img_path']).reset_index(drop=True)
print(f"Kept {len(df_nih_clean)} out of {initial_len} rows matching downloaded files.")

for cls in NIH_CLASSES:
    df_nih_clean[cls] = df_nih[cls] if cls in df_nih.columns else 0
df_nih_clean['Covid'] = 0

# 2. Read processed MIDRC COVID Manifest (Updated path & columns)
df_midrc = pd.read_csv("data_hybrid/midrc_processed_manifest.csv")

df_midrc_clean = pd.DataFrame()
# absolute path and the sanitized .png extension! Let's use it directly.
df_midrc_clean['img_path'] = df_midrc['img_path']
df_midrc_clean['patient_id'] = df_midrc['patient_id'].astype(str)

# Set all standard diseases to 0 (untracked), set COVID to 1
for cls in NIH_CLASSES:
    df_midrc_clean[cls] = 0
df_midrc_clean['Covid'] = 1


# 3. Concatenate and Split cleanly by Patient ID to avoid data leaks
df_master = pd.concat([df_nih_clean, df_midrc_clean], axis=0).reset_index(drop=True)

# Double check that everything looks good
print(f"Total Combined Master Rows: {len(df_master)}")
print(f"NIH Class Breakdown:\n{df_master[NIH_CLASSES].sum()}")
print(f"Covid Total Case Distribution: {df_master['Covid'].sum()}")

df_master.to_csv("data_hybrid/combined_master.csv", index=False)