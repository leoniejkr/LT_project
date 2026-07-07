import pandas as pd
import os

# Define the full 15-class multi-label taxonomy
NIH_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax']
ALL_CLASSES = NIH_CLASSES + ['Covid']

# 1. Read Kaggle NIH Metadata
# Note: Adjust path to where kagglehub saves your data
nih_dir = "path/to/kagglehub/nih-chest-xrays/data" 
df_nih_raw = pd.read_csv(os.path.join(nih_dir, "Data_Entry_2017.csv"))

# Parse pipe-separated pathologies into binary columns
labels_dummies = df_nih_raw["Finding Labels"].str.get_dummies(sep="|")
df_nih = pd.concat([df_nih_raw, labels_dummies], axis=1)

# Keep standard format
df_nih_clean = pd.DataFrame()
df_nih_clean['img_path'] = df_nih['Image Index'].apply(lambda x: os.path.join(nih_dir, "images", x)) # Check folder structure inside your Kaggle download
df_nih_clean['patient_id'] = df_nih['Patient ID'].astype(str)

for cls in NIH_CLASSES:
    df_nih_clean[cls] = df_nih[cls] if cls in df_nih.columns else 0
df_nih_clean['Covid'] = 0


# 2. Read processed MIDRC COVID Manifest
df_midrc = pd.read_csv("data_hybrid/midrc_covid_manifest.csv")

df_midrc_clean = pd.DataFrame()
df_midrc_clean['img_path'] = df_midrc['file_name'].apply(lambda x: os.path.join("data_hybrid/midrc_images", x))
df_midrc_clean['patient_id'] = df_midrc['patient_id'].astype(str)

# Set all standard diseases to 0 (untracked), set COVID to 1
for cls in NIH_CLASSES:
    df_midrc_clean[cls] = 0
df_midrc_clean['Covid'] = 1


# 3. Concatenate and Split cleanly by Patient ID to avoid data leaks
df_master = pd.concat([df_nih_clean, df_midrc_clean], axis=0).reset_index(drop=True)
df_master.to_csv("data_hybrid/combined_master.csv", index=False)