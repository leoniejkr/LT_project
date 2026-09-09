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


# ── POST-HOC CHEST SANITY CHECK ─────────────────────────────────────────
# Even after the manifest was built, an individual DICOM may not be a chest
# X-ray (hand, foot, abdomen, ... leaked into earlier downloads). We verify
# each extracted DICOM against the standard DICOM body-part / view tags and
# drop anything that is clearly not a chest scan. This happens AFTER
# loading the image so we only need the MONAI meta dict (no extra dep).
CHEST_BODY_TERMS = ("CHEST", "THORAX", "THORACIC")
NON_CHEST_BODY_TERMS = ("HAND", "FOOT", "WRIST", "ANKLE", "KNEE", "ELBOW",
                        "SHOULDER", "HIP", "ABDOMEN", "HEAD", "SKULL", "SPINE",
                        "LUMBAR", "CERVICAL", "PELVIS", "FEMUR", "TIBIA", "FIBULA",
                        "HUMERUS", "RADIUS", "ULNA", "FINGER", "TOE", "HEEL")
CHEST_VIEW_TERMS = ("PA", "AP", "LATERAL", "LAT", "ANTEROPOSTERIOR",
                    "POSTEROANTERIOR", "SAGITTAL", "CORONAL")
NON_CHEST_VIEW_TERMS = ("LL", "LAT OB", "OBLIQUE", "LATERAL", "TANGENTIAL")


def _meta_str(meta, tag) -> str:
    """Read a DICOM tag from a MONAI meta dict (keys like '0018|0015')."""
    for candidate in (tag, tag.replace("|", "")):
        if candidate in meta:
            val = meta[candidate]
            if isinstance(val, (list, tuple)) and val:
                val = val[0]
            return str(val).upper()
    return ""


def is_chest_dicom(meta) -> tuple[bool, str]:
    """Return (keep, reason). keep=False means the DICOM is NOT a chest scan.

    Uses BodyPartExamined (0018,0015), ViewPosition (0018,5101) and Modality
    (0008,0060). If we cannot positively determine it is non-chest, we keep it
    (defensive: never reject a scan we can't inspect).
    """
    body = _meta_str(meta, "0018|0015")
    view = _meta_str(meta, "0018|5101")
    modality = _meta_str(meta, "0008|0060")

    # Modality must be a projection radiograph if present.
    if modality and modality not in ("CR", "DX", "RF", ""):
        return False, f"non-radiograph modality {modality}"

    if body:
        if any(t in body for t in NON_CHEST_BODY_TERMS) or body in ("CHEST W/O",):
            return False, f"body part '{body}'"
        if any(t in body for t in CHEST_BODY_TERMS):
            # Confirmed chest via body part. Lateral chest views are still chest.
            return True, f"body part '{body}' matches chest"
        # Body part present but not recognised as chest -> drop (never risk it).
        return False, f"body part '{body}' not recognised as chest"

    # No body-part tag: fall back to view position.
    if view:
        # Lateral chest is fine, but "LL"/limb obliques etc. are not recognised.
        if any(t in view for t in CHEST_VIEW_TERMS) and not any(
            t in view for t in ("WRIST", "HAND", "FOOT", "ANKLE", "KNEE")
        ):
            return True, f"view '{view}' consistent with chest"
        # View present but not a recognised chest view -> drop.
        return False, f"view '{view}' not recognised as chest"

    # No usable tags at all: keep (cannot prove non-chest).
    return True, "no body-part/view tags present (kept defensively)"


def _patient_orientation_hint(patient_orientation) -> tuple[bool | None, bool | None]:
    """Translate a DICOM PatientOrientation (0018,5100) into anatomy hints.

    Returns (head_up, heart_right) where None = unknown/unreliable.

    DICOM standard: the first value is the patient direction the image ROWS
    map to, the second value the direction the image COLUMNS map to.
        * 'F' (foot) as the column direction  -> the top row is the head  -> head up.
        * 'H' (head) as the column direction  -> the top row is the foot  -> head down.
        * 'L' (left)  as the row direction    -> patient-left on viewer-right -> heart right.
        * 'R' (right) as the row direction    -> patient-left on viewer-left  -> heart left.

    NOTE: on this MIDRC collection the tag is frequently a legacy default
    (mostly ['L','F']) and only ~69% consistent with the actual pixel content,
    so it is used ONLY to resolve content-ambiguous cases, never to override
    strong content evidence (see orient_chest_xray).
    """
    if not patient_orientation:
        return None, None
    vals = [str(v).strip().upper()[:1] for v in patient_orientation]
    if len(vals) < 1:
        return None, None

    row_dir, col_dir = vals[0], (vals[1] if len(vals) > 1 else "")

    head_up = None
    if col_dir == "F":
        head_up = True
    elif col_dir == "H":
        head_up = False

    heart_right = None
    if row_dir == "L":
        heart_right = True
    elif row_dir == "R":
        heart_right = False

    return head_up, heart_right


def orient_chest_xray(img_arr: np.ndarray, patient_orientation=None) -> np.ndarray:
    """Normalize a chest X-ray to the standard display convention:
    portrait, head-up, cardiac silhouette on the viewer's RIGHT
    (matches the NIH reference dataset).

    These MIDRC DICOMs carry NO ImageOrientationPatient tag (verified on the
    whole batch), so SimpleITK DICOMOrient/RAS cannot be used — there is no
    orientation matrix to rotate to. Instead we use stable anatomical content
    signals (after photometric normalization to MONOCHROME2 style):

        * vertical:   lungs (dark) on TOP, diaphragm/liver/abdomen (bright) on
                      the BOTTOM -> flip upside-down if the top is brighter.
        * horizontal: the cardiac silhouette makes the right hemithorax slightly
                      denser in standard display -> mirror if the LEFT is denser.

    Both are content-based (self-consistent to ~100% on the real batch). The
    DICOM PatientOrientation tag is used only to break content ties.
    """
    arr = np.asarray(img_arr)
    if arr.ndim == 3:
        arr = arr[..., 0]  # keep a single channel

    head_hint, heart_hint = _patient_orientation_hint(patient_orientation)

    # 1. Portrait normalization: rows should be >= cols (taller than wide).
    h, w = arr.shape
    if w > h:
        arr = np.rot90(arr, k=1)

    def _content_axis(half_a, half_b):
        """Return 'a' if a is clearly denser than b, 'b', or None if tied."""
        ma, mb = float(half_a.mean()), float(half_b.mean())
        denom = max(ma, mb, 1e-3)
        if abs(ma - mb) > 0.02 * denom:  # >2% relative decisiveness
            return "a" if ma > mb else "b"
        return None

    # 2. Vertical: head up (bottom denser than top).
    h, w = arr.shape
    top_half, bottom_half = arr[: h // 2], arr[h // 2 :]
    v = _content_axis(bottom_half, top_half)
    if v == "b":                       # top denser -> upside down
        arr = np.flipud(arr)
    elif v is None and head_hint is False:
        arr = np.flipud(arr)           # content tie, tag says head-down

    # 3. Horizontal: cardiac silhouette denser on the RIGHT.
    h, w = arr.shape
    left_half, right_half = arr[:, : w // 2], arr[:, w // 2 :]
    hz = _content_axis(right_half, left_half)
    if hz == "b":                      # left denser -> mirrored
        arr = np.fliplr(arr)
    elif hz is None and heart_hint is False:
        arr = np.fliplr(arr)           # content tie, tag says heart-left

    return arr


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="data_hybrid/midrc_download_manifest.json")
    p.add_argument("--image-root", default="data_hybrid/midrc_dicoms")
    p.add_argument("--output-dir", default="data_hybrid/midrc_images")
    p.add_argument("--force-reprocess", action="store_true",
                   help="Delete existing processed PNGs and manifest so every "
                        "image is re-verified (incl. chest check) from source DICOMs.")
    args = p.parse_args()

    manifest_json = Path(args.manifest)
    image_root = Path(args.image_root)
    out_dir = Path(args.output_dir)
    
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.force_reprocess:
        removed = 0
        for p in out_dir.glob("*.png"):
            p.unlink()
            removed += 1
        manifest_out = Path("data_hybrid/midrc_processed_manifest.csv")
        if manifest_out.exists():
            manifest_out.unlink()
        log.info(f"Force reprocess: removed {removed} existing PNGs and stale manifest.")

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

                # Post-hoc chest sanity check (metadata level).
                keep, reason = is_chest_dicom(meta_dict)
                if not keep:
                    log.warning(f"Skipping {obj_id} — not a chest scan ({reason}).")
                    continue

                po = meta_dict.get("0018|5100") or meta_dict.get("00185100")

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

                    # Post-hoc chest sanity check on the fallback meta dict.
                    keep, reason = is_chest_dicom(raw_tensor.meta)
                    if not keep:
                        log.warning(f"Skipping {obj_id} — not a chest scan ({reason}).")
                        continue

                    po = raw_tensor.meta.get("0018|5100") or raw_tensor.meta.get("00185100")

                except Exception as fallback_err:
                    log.warning(f"Skipping file {obj_id} — MONAI error: {monai_err} | Fallback error: {fallback_err}")
                    continue

            # Apply final contrast matching and export as standard 2D Grayscale PNG
            img_arr = orient_chest_xray(img_arr, patient_orientation=po)
            final_img_arr = apply_clahe_contrast(img_arr)
            img = Image.fromarray(final_img_arr, mode='L')

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