#!/usr/bin/env python3
"""
scripts/process_dicoms_to_nih.py
──────────────────────────────────────────────────────────────────────
Processes raw MIDRC DICOM zips using MONAI to precisely match the 
visual characteristics, contrast, and layout of the NIH dataset.
Fixed: Resolves fallback parsing bugs to ensure high-yield extraction.
"""

import argparse
import json
import logging
import sys
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
    import skimage.exposure as exposure
    from monai.transforms import (
        Compose, LoadImage, EnsureChannelFirst, ScaleIntensityRangePercentiles, Resize
    )
    from monai.data import ITKReader
    MONAI_AVAILABLE = True
except ImportError:
    log.error("Missing required scientific packages. Please install them:")
    log.error("pip install monai[itk,pillow] scikit-image torch")
    sys.exit(1)


def extract_zip_and_find_valid_dicom(zip_path: Path, temp_dir: Path) -> Path | None:
    """Extracts zip file and returns the path to the main raw DICOM payload file."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
    except zipfile.BadZipFile:
        return None
    
    candidates = []
    for p in temp_dir.rglob("*"):
        if p.is_file() and not p.name.startswith(".") and "MACOSX" not in p.parts:
            if p.suffix.lower() not in [".txt", ".json", ".xml", ".csv"]:
                candidates.append(p)
                
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        candidates.sort(key=lambda x: x.stat().st_size, reverse=True)
        return candidates[0]
        
    return None


def apply_clahe_contrast(img_array: np.ndarray) -> np.ndarray:
    """Applies Adaptive Histogram Equalization (CLAHE) to match the NIH look."""
    img_float = img_array.astype(np.float32) / 255.0
    if img_float.max() == img_float.min():
        return (img_float * 255.0).astype(np.uint8)
    img_equalized = exposure.equalize_adapthist(img_float, clip_limit=0.02)
    return (img_equalized * 255.0).astype(np.uint8)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="data_hybrid/midrc_download_manifest.json")
    p.add_argument("--image-root", default="data_hybrid/midrc_dicoms")
    p.add_argument("--output-dir", default="data_hybrid/midrc_images")
    args = p.parse_args()

    manifest_json = Path(args.manifest)
    image_root = Path(args.image_root)
    out_dir = Path(args.output_dir)
    
    out_dir.mkdir(parents=True, exist_ok=True)

    if not manifest_json.exists():
        log.error(f"Manifest not found at {manifest_json}. Please generate it first.")
        return

    with open(manifest_json, "r") as f:
        manifest_data = json.load(f)

    # Clean MONAI pipeline setup
    monai_pipeline = Compose([
        LoadImage(image_only=False, reader=ITKReader()), 
        EnsureChannelFirst(channel_dim='no_channel'), 
        ScaleIntensityRangePercentiles(lower=0.5, upper=99.5, b_min=0.0, b_max=255.0, clip=True),
        Resize(spatial_size=(512, 512), mode="bilinear")
    ])

    processed_rows = []
    success_count = 0

    log.info(f"Processing downloaded files matching manifest criteria...")
    
    for item in manifest_data:
        obj_id = item["object_id"]
        fname = item["file_name"]
        
        zip_path = None
        zip_candidates = [
            image_root / fname,
            image_root / obj_id / fname,
            image_root / "cxr" / fname
        ]
        
        for candidate in zip_candidates:
            if candidate.exists() and candidate.is_file():
                zip_path = candidate
                break
                
        if not zip_path:
            found_paths = list(image_root.rglob(f"*{obj_id}*.zip")) + list(image_root.rglob(f"*{fname}*"))
            if found_paths and found_paths[0].is_file():
                zip_path = found_paths[0]

        if not zip_path:
            continue

        safe_obj_id = obj_id.replace("/", "_")
        save_path = out_dir / f"{safe_obj_id}.png"

        # Skip if PNG already exists
        if save_path.exists():
            processed_rows.append({
                "img_path": str(save_path.absolute()),
                "patient_id": obj_id,
                "Covid": 1
            })
            success_count += 1
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            dicom_file = extract_zip_and_find_valid_dicom(zip_path, Path(tmpdir))
            if not dicom_file:
                continue

            try:
                # ── STRATEGY A: Standard MONAI Processing ─────────────────────
                monai_output, meta_dict = monai_pipeline(str(dicom_file))
                img_arr = monai_output.detach().cpu().numpy()[0].astype(np.uint8)

                photometric = meta_dict.get("0028|0004", "")
                if "MONOCHROME1" in str(photometric).upper():
                    img_arr = 255 - img_arr

            except Exception as monai_err:
                # ── STRATEGY B: Cleaned-up Recovery Fallback ──────────────────
                try:
                    # Load without strict spatial headers
                    raw_loader = LoadImage(image_only=True)
                    raw_tensor = raw_loader(str(dicom_file))
                    raw_arr = raw_tensor.detach().cpu().numpy().astype(np.float32)
                    
                    # Flatten dimensions down to a basic 2D matrix
                    if len(raw_arr.shape) > 2:
                        raw_arr = raw_arr.squeeze()
                        if len(raw_arr.shape) > 2: 
                            raw_arr = raw_arr[..., 0]
                    
                    # Normalize safely between 0 and 255
                    amin, amax = raw_arr.min(), raw_arr.max()
                    if amax - amin > 0:
                        img_arr = ((raw_arr - amin) / (amax - amin) * 255.0).astype(np.uint8)
                    else:
                        img_arr = np.zeros_like(raw_arr, dtype=np.uint8)

                    # Check photometric orientation manually on fallback
                    if "MONOCHROME1" in str(raw_tensor.meta.get("photometric_interpretation", "")):
                        img_arr = 255 - img_arr
                except Exception as fallback_err:
                    log.warning(f"Skipping file {obj_id} — MONAI error: {monai_err} | Fallback error: {fallback_err}")
                    continue

            # Apply final contrast matching and export as standard 2D Grayscale PNG
            final_img_arr = apply_clahe_contrast(img_arr)
            img = Image.fromarray(final_img_arr, mode='L')

            # Auto-rotate landscape images to portrait (chest X-rays should be taller than wide)
            if img.width > img.height:
                img = img.transpose(Image.ROTATE_90)

            img.save(save_path)

            processed_rows.append({
                "img_path": str(save_path.absolute()),
                "patient_id": obj_id,
                "Covid": 1
            })
            success_count += 1

    if len(processed_rows) > 0:
        csv_path = Path("data_hybrid/midrc_processed_manifest.csv")
        pd.DataFrame(processed_rows).to_csv(csv_path, index=False)
        log.info(f"lignment finished! Successfully processed {success_count} PNGs.")
        log.info(f"Manifest saved to: {csv_path}")
    else:
        log.error("No images could be converted. Verify your files are fully downloaded.")


if __name__ == "__main__":
    main()