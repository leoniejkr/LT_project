#!/usr/bin/env python3
"""
scripts/preprocess.py
──────────────────────────────────────────────────────────────────────
Trimming the pipeline down: 
1. Ignore 3D CT entirely.
2. Locate downloaded MIDRC CXR ZIPs for COVID-19 cases.
3. Extract, read via MONAI, and save as 2D PNGs (matching Kaggle format).
"""

import argparse
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

try:
    import torch
    from monai.transforms import (
        Compose, LoadImage, EnsureChannelFirst, ScaleIntensityRangePercentiles
    )
    from monai.data import ITKReader
    MONAI_AVAILABLE = True
except ImportError:
    MONAI_AVAILABLE = False


def extract_zip_and_find_dicoms(zip_path: Path, temp_dir: Path) -> Path | None:
    """Extracts zip file and returns the folder containing raw DICOM files."""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    # MIDRC layout: usually extracts into a subfolder named after the series uid
    for p in temp_dir.rglob("*"):
        if p.is_dir() and not list(p.iterdir()) == []:
            # Check if files inside look like DICOM (or have no extension but are data files)
            first_file = next(p.iterdir(), None)
            if first_file and first_file.is_file():
                return p
    return None


def preprocess_midrc_covid(cohort_cxr_path: str, image_root: Path, out_dir: Path):
    """Processes only the explicit MIDRC CXR cases and outputs standard 2D PNGs."""
    if not MONAI_AVAILABLE:
        log.error("MONAI/Torch not found. Cannot process DICOMs.")
        return

    df = pd.read_csv(cohort_cxr_path, low_memory=False)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 2D Normalization pipeline: reads DICOM, rescales intensity to 0-255 uint8 range
    cxr_transform = Compose([
        LoadImage(image_only=True, reader=ITKReader()),
        EnsureChannelFirst(),
        ScaleIntensityRangePercentiles(lower=0.5, upper=99.5, b_min=0.0, b_max=255.0, clip=True),
    ])

    manifest_rows = []
    processed_count = 0

    log.info(f"Processing {len(df)} CXR targets from manifest...")
    for idx, row in df.iterrows():
        submitter_id = str(row["submitter_id"])
        study_uid = str(row["study_uid"])
        series_uid = str(row["series_uid"])
        obj_id = str(row["object_id"])
        
        # Match original file layout: images/cxr/<submitter_id>/<study_uid>/<series_uid>.zip
        zip_path = image_root / "cxr" / submitter_id / study_uid / f"{series_uid}.zip"
        
        if not zip_path.exists():
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            dicom_dir = extract_zip_and_find_dicoms(zip_path, Path(tmpdir))
            if not dicom_dir:
                continue
                
            try:
                # Load the DICOM directory using MONAI
                tensor = cxr_transform(str(dicom_dir))
                arr = tensor.numpy()[0].astype(np.uint8) # Extract 2D matrix
                
                # Save out cleanly as a standard 8-bit Grayscale PNG image
                save_path = out_dir / f"{obj_id}.png"
                img = Image.fromarray(arr, mode='L')
                img.save(save_path)
                
                manifest_rows.append({
                    "img_path": str(save_path),
                    "patient_id": submitter_id,
                    "Covid": 1  # Tag explicitly as COVID-19 positive
                })
                processed_count += 1
            except Exception as e:
                log.warning(f"Failed to process series {series_uid}: {e}")

    # Output tracking sheet
    pd.DataFrame(manifest_rows).to_csv("data_hybrid/midrc_processed_manifest.csv", index=False)
    log.info(f"Successfully converted {processed_count} MIDRC DICOM volumes into standard 2D PNGs.")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--cohort-cxr", default="data/cohort_cxr.csv", help="Filtered MIDRC COVID manifest CSV")
    p.add_argument("--image-root", default="images/", help="Path containing downloaded ZIP entries")
    p.add_argument("--prep-dir",   default="data_hybrid/midrc_images", help="Target output folder for PNGs")
    return p.parse_args()


def main():
    args = parse_args()
    preprocess_midrc_covid(args.cohort_cxr, Path(args.image_root), Path(args.prep_dir))


if __name__ == "__main__":
    main()