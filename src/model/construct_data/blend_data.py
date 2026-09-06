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
NORMAL_LABEL = 'No Finding'

# ── BALANCING CONFIGURATION ───────────────────────────────────────────────
# Maximale Anzahl Bilder pro Bedingung. Häufigere Klassen werden auf dieses
# Limit subsampled; seltenere Klassen (z.B. Hernia) bleiben vollständig
# erhalten und werden später über Class-Weights im Training ausbalanciert.
# Siehe get_midrc_data.py --max-covid (gleicher N-Wert für den MIDRC-Download).
TARGET_N = int(os.environ.get("BALANCE_N", "7000"))
RANDOM_SEED = 42

# ── PATHS ───────────────────────────────────────────────────────────────────
# NIH data lives in the Kaggle cache. Run get_nih_data.py first to create the pointer.
NIH_POINTER = os.path.join("data_hybrid", "nih_images", "path.txt")
with open(NIH_POINTER) as f:
    NIH_DIR = f.read().strip()
print(f"NIH data directory: {NIH_DIR}")


def subsample_per_condition(df: pd.DataFrame, classes: list, n: int, seed: int) -> pd.DataFrame:
    """Cap every positive condition to `n` images (multi-label aware).

    NIH images are multi-label, so a single image can contribute to several
    conditions. Naively capping each condition independently and taking the
    union lets a condition exceed `n` through secondary labels. Instead we
    greedily drop rows until every condition's positive count is <= n, always
    preferring to drop rows that touch many over-limit conditions and that do
    NOT co-occur with rare (under-limit) classes, to waste as little data as
    possible. Rare classes are protected until forcing a drop is unavoidable.
    """
    import numpy as np

    rng = np.random.RandomState(seed)
    X = df[classes].to_numpy().astype(bool)
    cond_idx = {cls: i for i, cls in enumerate(classes)}
    drop = np.zeros(X.shape[0], dtype=bool)

    while True:
        counts = X[~drop].sum(axis=0)
        over = [i for i, c in enumerate(classes) if counts[i] > n]
        if not over:
            break
        over_set = set(over)
        under_list = [i for i, c in enumerate(classes) if i not in over_set]

        # candidate rows: not yet dropped and positive for at least one over-limit condition
        cand = ~drop & X[:, over].any(axis=1)
        if not cand.any():
            break

        over_n = X[:, over].sum(axis=1)
        touches_rare = np.zeros(X.shape[0], dtype=bool)
        if under_list:
            touches_rare = X[:, under_list].any(axis=1)

        best = -1
        # prefer non-rare-touching rows (keep rare data), then highest over-count
        non_rare = cand & ~touches_rare
        pool = non_rare if non_rare.any() else cand
        if pool.any():
            cand_idx = np.flatnonzero(pool)
            # tie-break randomly among equal over-n to avoid systematic bias
            over_n_pool = over_n[pool]
            max_in_pool = over_n_pool.max()
            ties = cand_idx[over_n_pool == max_in_pool]
            best = int(rng.choice(ties))

        drop[best] = True

    keep = np.flatnonzero(~drop)
    return df.loc[keep].copy().reset_index(drop=True)


# 1. Read Kaggle NIH Metadata
df_nih_raw = pd.read_csv(os.path.join(NIH_DIR, "Data_Entry_2017.csv"))

# Parse pipe-separated pathologies into binary columns
labels_dummies = df_nih_raw["Finding Labels"].str.get_dummies(sep="|")
df_nih_raw = pd.concat([df_nih_raw, labels_dummies], axis=1)

# Build lookup map of image file locations
print("Scanning NIH directory for image locations...")
image_path_map = {}
for root, dirs, files in os.walk(NIH_DIR):
    for file in files:
        if file.endswith(".png"):
            image_path_map[file] = os.path.join(root, file)

print(f"Located {len(image_path_map)} total NIH images locally.")

# Clean and map NIH dataframe
df_nih_clean = pd.DataFrame()
df_nih_clean['img_path'] = df_nih_raw['Image Index'].map(image_path_map)
df_nih_clean['patient_id'] = df_nih_raw['Patient ID'].astype(str)
df_nih_clean['view_position'] = df_nih_raw['View Position'].astype(str)

# Keep downloaded files only
df_nih_clean = df_nih_clean.dropna(subset=['img_path']).reset_index(drop=True)

# Quality filter: keep front-facing views only (PA / AP) to align with MIDRC
df_nih_clean = df_nih_clean[
    df_nih_clean['view_position'].str.upper().isin(['PA', 'AP'])
].reset_index(drop=True)

for cls in NIH_CLASSES:
    df_nih_clean[cls] = df_nih_raw[cls] if cls in df_nih_raw.columns else 0
df_nih_clean[NORMAL_LABEL] = df_nih_raw[NORMAL_LABEL] if NORMAL_LABEL in df_nih_raw.columns else 0
df_nih_clean['Covid'] = 0

# Cap each pathological condition to TARGET_N. Normals (No Finding) are kept in
# full as the negative backbone; their majority is handled by class weighting
# during training rather than by discarding data.
print(f"\nNIH images before balancing: {len(df_nih_clean)}")
df_nih_balanced = subsample_per_condition(df_nih_clean, NIH_CLASSES, TARGET_N, RANDOM_SEED)
print(f"NIH images after per-condition cap ({TARGET_N}): {len(df_nih_balanced)}")
print("Per-condition counts after balancing:")
for cls in NIH_CLASSES + [NORMAL_LABEL]:
    print(f"  {cls:20s} {int(df_nih_balanced[cls].sum())}")


# 2. Read processed MIDRC COVID Manifest
df_midrc = pd.read_csv("data_hybrid/midrc_processed_manifest.csv")

# ── MIDRC ORIENTATION FIX ───────────────────────────────────────────────
# Use ONLY the orientation-corrected copies. These live in midrc_fixed_images/
# as full-res PNGs (up to ~4400px); resize_midrc.py pre-downscales them to
# midrc_fixed_1024/ so the training DataLoader never re-decodes 48 GB of
# full-res X-rays every epoch (that thrashed the 24 GB machine into swap).
# Manifest rows without a fixed (and downscaled) copy are dropped.
MIDRC_FIXED_DIR = os.path.join("data_hybrid", "midrc_fixed_1024")


def remap_to_fixed(path: str):
    fixed_path = os.path.join(MIDRC_FIXED_DIR, os.path.basename(path))
    if os.path.exists(fixed_path):
        return fixed_path
    return None


orig_rows = len(df_midrc)
df_midrc['img_path'] = df_midrc['img_path'].apply(remap_to_fixed)
df_midrc = df_midrc.dropna(subset=['img_path']).reset_index(drop=True)
n_fixed = len(df_midrc)
print(f"MIDRC images with fixed orientation: {n_fixed} / {orig_rows} "
      f"({orig_rows - n_fixed} dropped, not yet orientation-fixed)")

if len(df_midrc) == 0:
    raise SystemExit("No MIDRC images have fixed orientations yet. "
                     "Run fix_midrc_orientation.py first.")

df_midrc_clean = pd.DataFrame()
df_midrc_clean['img_path'] = df_midrc['img_path']
df_midrc_clean['patient_id'] = df_midrc['patient_id'].astype(str)
df_midrc_clean['view_position'] = df_midrc.get('view_position', 'AP')

for cls in NIH_CLASSES:
    df_midrc_clean[cls] = 0
df_midrc_clean['Covid'] = 1

# Cap MIDRC COVID to TARGET_N as well (keeps all if fewer than TARGET_N).
print(f"\nMIDRC COVID images before balancing: {len(df_midrc_clean)}")
if len(df_midrc_clean) > TARGET_N:
    rng = np.random.RandomState(RANDOM_SEED)
    df_midrc_clean = df_midrc_clean.sample(n=TARGET_N, random_state=RANDOM_SEED).reset_index(drop=True)
print(f"MIDRC COVID after cap ({TARGET_N}): {len(df_midrc_clean)}")


# 3. Concatenate and Export
df_master = pd.concat([df_nih_balanced, df_midrc_clean], axis=0).reset_index(drop=True)

print("\n" + "=" * 50)
print("COMBINED DATASET SUMMARY")
print("=" * 50)
print(f"Total Combined Master Rows: {len(df_master)}")
print(f"COVID (MIDRC) Cases:       {df_master['Covid'].sum()} ({df_master['Covid'].mean():.1%})")
print(f"Non-COVID (NIH) Cases:     {(df_master['Covid'] == 0).sum()} ({(1 - df_master['Covid'].mean()):.1%})")
print("\nPathology Distribution:")
print(df_master[ALL_CLASSES].sum())

# Drop helper columns not part of the taxonomy
df_master = df_master[['img_path', 'patient_id', 'view_position'] + ALL_CLASSES]

df_master.to_csv("data_hybrid/combined_master.csv", index=False)
print("\nSaved balanced dataset to: data_hybrid/combined_master.csv")
