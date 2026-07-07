
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
        ScaleIntensityRangePercentiles,
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
PROJECT   = "A1"  
OUTPUT_DIR = Path("data")
PREP_DIR   = OUTPUT_DIR / "preprocessed"
RANDOM_SEED = 42

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

# ══════════════════════════════════════════════════════════════════════════════
# NEW CONFIGURATION: 2D COVID EXTRACTION ONLY
# ══════════════════════════════════════════════════════════════════════════════
OUTPUT_DIR = Path("data_hybrid")
MIDRC_CXR_DIR = OUTPUT_DIR / "midrc_images"
OUTPUT_DIR.mkdir(exist_ok=True)
MIDRC_CXR_DIR.mkdir(parents=True, exist_ok=True)

# 1. Export standard nodes
cases_raw = sub.export_node(PROGRAM, PROJECT, "case", "tsv")
cr_raw    = sub.export_node(PROGRAM, PROJECT, "cr_series_file", "tsv")
df_cases  = pd.read_csv(io.StringIO(cases_raw), sep="\t")
df_cr     = pd.read_csv(io.StringIO(cr_raw), sep="\t", low_memory=False)

# Clean IDs
df_cr["case_ids_clean"] = df_cr["case_ids"].apply(lambda x: str(x).replace("[","").replace("]","").replace("'","").strip())

# 2. Isolate COVID cases using the explicit case-node flag
covid_cases = set(df_cases[df_cases["covid19_positive"].fillna("").str.lower() == "yes"]["submitter_id"])
df_covid_cxr = df_cr[df_cr["case_ids_clean"].isin(covid_cases)].copy().reset_index(drop=True)

# Limit to a manageable number of samples (e.g., 1000 cases) to keep it lightweight
df_covid_cxr = df_covid_cxr.sample(n=min(1000, len(df_covid_cxr)), random_state=42).reset_index(drop=True)

print(f"Targeting {len(df_covid_cxr)} MIDRC 2D CXR COVID-19 samples...")

# 3. Streamlined 2D Preprocessing (Exporting directly as standard PNG matching Kaggle)
if MONAI_AVAILABLE:
    import torchvision.transforms as T
    from PIL import Image

    # A simple pipeline to load the DICOM and write a standard grayscale PNG
    cxr_load = Compose([
        LoadImage(image_only=True, reader=ITKReader()),
        EnsureChannelFirst(),
        ScaleIntensityRangePercentiles(lower=0.5, upper=99.5, b_min=0.0, b_max=255.0, clip=True),
    ])

    src_root = Path("images")
    manifest_rows = []

    for _, row in df_covid_cxr.iterrows():
        obj_id = str(row["object_id"])
        fname = str(row["file_name"])
        src_path = src_root / obj_id / fname
        save_path = MIDRC_CXR_DIR / f"{obj_id}.png"

        if not src_path.exists():
            continue

        try:
            # Read DICOM using MONAI ITKReader
            tensor = cxr_load(str(src_path))
            arr = tensor.numpy()[0].astype(np.uint8) # Extract 2D matrix
            
            # Save as standard 8-bit grayscale PNG image
            img = Image.fromarray(arr, mode='L')
            img.save(save_path)
            
            manifest_rows.append({
                "file_name": f"{obj_id}.png",
                "patient_id": row["case_ids_clean"],
                "dataset_source": "midrc"
            })
        except Exception as e:
            print(f"Skipping {obj_id} due to error: {e}")

    # Save minimal tracking manifest
    pd.DataFrame(manifest_rows).to_csv(OUTPUT_DIR / "midrc_covid_manifest.csv", index=False)
    print("MIDRC COVID extraction complete.")