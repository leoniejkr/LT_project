#!/usr/bin/env python3
"""
scripts/preprocess.py  (v2 — handles MIDRC ZIP-wrapped DICOM series)
──────────────────────────────────────────────────────────────────────
MIDRC gen3-client download structure:
  images/{ct,cxr}/<submitter_id>/<study_uid>/<series_uid>.zip
    └── <series_uid>   (DICOM files inside the ZIP, no .dcm extension)

Pipeline per series:
  1. Find ZIP via submitter_id folder (not object_id)
  2. Extract ZIP to a temp dir
  3. Find DICOM files inside (by magic bytes, not extension)
  4. Run MONAI transforms on the DICOM series folder
  5. Save preprocessed tensor; clean up temp dir

CT  → unzip → MONAI(HU window → RAS → resample → crop → resize → z-score) → .nii.gz
CXR → unzip → MONAI(normalize → CLAHE → resize → ImageNet norm) → .npy

Usage:
    python scripts/preprocess.py \
        --cohort-ct  data/cohort_ct.csv \
        --cohort-cxr data/cohort_cxr.csv \
        --image-root images/ \
        --prep-dir   data/preprocessed/
"""

import argparse
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── MONAI ────────────────────────────────────────────────────────────────────
try:
    import torch
    from monai.transforms import (
        Compose, LoadImage, EnsureChannelFirst, Orientation,
        Spacing, ScaleIntensityRange, CropForeground,
        Resize, NormalizeIntensity, Lambda,
    )
except ImportError:
    raise SystemExit("Install MONAI: pip install 'monai[itk,nibabel,pillow]'")

CT_TARGET_SPACING = (1.5, 1.5, 2.0)
CT_TARGET_SHAPE   = (224, 224, 96)
CT_HU_LOW, CT_HU_HIGH = -1000, 400
CXR_TARGET_SHAPE  = (224, 224)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_dicom(path: Path) -> bool:
    """Check DICOM magic bytes (offset 128, 'DICM')."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except Exception:
        return False


def extract_zip_to_temp(zip_path: Path) -> Path | None:
    """Extract ZIP to a fresh temp dir. Returns the temp dir path."""
    tmp = Path(tempfile.mkdtemp(prefix="midrc_"))
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)
        return tmp
    except zipfile.BadZipFile as e:
        log.warning(f"Bad ZIP {zip_path.name}: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return None


def find_dicom_dir(extracted_root: Path) -> Path | None:
    """
    After extraction the layout can be:
      <tmp>/<series_uid>/<slice_files>   (most common)
      <tmp>/<slice_files>                (flat)
    Returns the directory that contains DICOM files, or None.
    """
    # Try depth-1 subdirs first
    for sub in sorted(extracted_root.iterdir()):
        if sub.is_dir():
            dcm_files = [f for f in sub.iterdir() if f.is_file() and is_dicom(f)]
            if dcm_files:
                return sub
    # Flat layout
    dcm_files = [f for f in extracted_root.iterdir() if f.is_file() and is_dicom(f)]
    if dcm_files:
        return extracted_root
    return None


def find_zip_for_series(image_root: Path, modality: str, submitter_id: str) -> Path | None:
    """
    Walks images/<modality>/<submitter_id>/**/*.zip and returns the first ZIP.
    MIDRC layout: <submitter_id>/<study_uid>/<series_uid>.zip
    """
    base = image_root / modality.lower() / submitter_id
    if not base.exists():
        return None
    zips = list(base.rglob("*.zip"))
    if not zips:
        return None
    # If multiple ZIPs (multi-series patient), take the largest (most slices)
    return max(zips, key=lambda p: p.stat().st_size)


# ── MONAI transform builders ──────────────────────────────────────────────────

def build_ct_transforms():
    return Compose([
        LoadImage(image_only=True),          # reads DICOM series directory
        EnsureChannelFirst(),
        Orientation(axcodes="RAS"),
        Spacing(pixdim=CT_TARGET_SPACING, mode="bilinear"),
        ScaleIntensityRange(
            a_min=CT_HU_LOW, a_max=CT_HU_HIGH,
            b_min=0.0, b_max=1.0, clip=True,
        ),
        CropForeground(source_key=None),
        Resize(spatial_size=CT_TARGET_SHAPE, mode="area"),
        NormalizeIntensity(nonzero=True, channel_wise=True),
    ])


def _squeeze_z(x: "torch.Tensor") -> "torch.Tensor":
    """
    MONAI LoadImage on a single-slice DICOM returns [C, H, W, 1].
    Squeeze the trailing Z-dim so downstream 2D transforms get [C, H, W].
    Also handles [C, H, W] (already 2D) and [C, 1, H, W] edge cases.
    """
    if x.ndim == 4 and x.shape[-1] == 1:
        return x[..., 0]          # [C, H, W, 1] → [C, H, W]
    if x.ndim == 4 and x.shape[1] == 1:
        return x[:, 0, :, :]     # [C, 1, H, W] → [C, H, W]
    return x                      # already [C, H, W]


def _clahe(x: "torch.Tensor") -> "torch.Tensor":
    try:
        from skimage.exposure import equalize_adapthist
        arr = x.numpy()
        out = np.stack(
            [equalize_adapthist(arr[c], clip_limit=0.03) for c in range(arr.shape[0])],
            axis=0,
        )
        return torch.tensor(out, dtype=x.dtype)
    except ImportError:
        log.warning("scikit-image not found — skipping CLAHE")
        return x


def build_cxr_transforms():
    return Compose([
        LoadImage(image_only=True),
        EnsureChannelFirst(),
        Lambda(func=_squeeze_z),                         # [C,H,W,1] → [C,H,W]
        ScaleIntensityRange(                             # pixel range from debug: 0–14363
            a_min=0, a_max=16383, b_min=0.0, b_max=1.0, clip=True,
        ),
        Lambda(func=_clahe),
        Resize(spatial_size=CXR_TARGET_SHAPE, mode="area"),
        NormalizeIntensity(
            subtrahend=[0.485], divisor=[0.229],
            nonzero=False, channel_wise=True,
        ),
    ])


# ── Core processing function ──────────────────────────────────────────────────

def process_one(
    submitter_id: str,
    object_id: str,
    transforms,
    image_root: Path,
    out_dir: Path,
    modality: str,
    ext: str,
) -> str:
    """
    Returns the output path string, or "" on failure.
    """
    import nibabel as nib

    safe_id = object_id.replace("dg.MD1R/", "").replace("/", "_")
    out_path = out_dir / f"{safe_id}{ext}"

    if out_path.exists():
        return str(out_path)

    # ── 1. Find the ZIP ───────────────────────────────────────────────────────
    zip_path = find_zip_for_series(image_root, modality, submitter_id)
    if zip_path is None:
        return ""

    # ── 2. Extract ────────────────────────────────────────────────────────────
    tmp_dir = extract_zip_to_temp(zip_path)
    if tmp_dir is None:
        return ""

    try:
        # ── 3. Find DICOM directory inside extracted content ──────────────────
        dicom_dir = find_dicom_dir(tmp_dir)
        if dicom_dir is None:
            log.warning(f"No DICOM files found in ZIP: {zip_path.name}")
            return ""

        # ── 4. MONAI transform ────────────────────────────────────────────────
        # LoadImage on a directory reads the whole DICOM series
        tensor = transforms(str(dicom_dir))
        arr = tensor.numpy() if hasattr(tensor, "numpy") else np.array(tensor)

        # ── 5. Save ───────────────────────────────────────────────────────────
        out_dir.mkdir(parents=True, exist_ok=True)
        if ext == ".nii.gz":
            nii = nib.Nifti1Image(arr[0], affine=np.eye(4))
            nib.save(nii, str(out_path))
        else:
            np.save(str(out_path), arr)
            out_path = out_path.with_suffix(".npy") if ext != ".npy" else out_path

        return str(out_path)

    except Exception as exc:
        log.warning(f"Transform failed [{submitter_id}]: {exc}")
        return ""

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Batch processor ───────────────────────────────────────────────────────────

def preprocess_cohort(
    df: pd.DataFrame,
    transforms,
    image_root: Path,
    out_dir: Path,
    modality: str,
    ext: str,
) -> pd.DataFrame:
    out_paths = []
    found = skipped = cached = 0
    total = len(df)

    for idx, (_, row) in enumerate(df.iterrows(), 1):
        submitter_id = str(row.get("submitter_id", ""))
        object_id    = str(row.get("object_id", ""))

        result = process_one(
            submitter_id=submitter_id,
            object_id=object_id,
            transforms=transforms,
            image_root=image_root,
            out_dir=out_dir,
            modality=modality,
            ext=ext,
        )

        if result == "":
            # Distinguish "ZIP not downloaded" from "processing failed"
            zip_exists = find_zip_for_series(image_root, modality, submitter_id) is not None
            if not zip_exists:
                skipped += 1
            else:
                skipped += 1  # processing failure — also skipped
        elif result and Path(result).stat().st_size > 0:
            # Check if it was already there before this run
            found += 1

        out_paths.append(result)

        if idx % 25 == 0 or idx == total:
            log.info(f"  [{idx}/{total}] processed={found}  skipped={skipped}")

    df_out = df.copy()
    df_out["preprocessed_path"] = out_paths

    downloaded  = sum(1 for r in out_paths if r != "")
    not_on_disk = total - sum(
        1 for (_, row) in df.iterrows()
        if find_zip_for_series(image_root, modality, str(row.get("submitter_id",""))) is not None
    )
    log.info(
        f"\n{modality} summary:\n"
        f"  Total in cohort : {total}\n"
        f"  Not downloaded  : {not_on_disk}  ← run gen3-client again for these\n"
        f"  Preprocessed OK : {downloaded}\n"
        f"  Failed/skipped  : {skipped - (total - downloaded)}"
    )
    return df_out


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--cohort-ct",  default="data/cohort_ct.csv")
    p.add_argument("--cohort-cxr", default="data/cohort_cxr.csv")
    p.add_argument("--image-root", default="images/")
    p.add_argument("--prep-dir",   default="data/preprocessed/")
    p.add_argument("--skip-ct",    action="store_true")
    p.add_argument("--skip-cxr",   action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    image_root = Path(args.image_root)
    prep_dir   = Path(args.prep_dir)

    if not args.skip_ct:
        log.info("─" * 60)
        log.info("Preprocessing CT …")
        df_ct = pd.read_csv(args.cohort_ct, low_memory=False)
        log.info(f"  Loaded {len(df_ct):,} CT series from {args.cohort_ct}")
        df_ct = preprocess_cohort(
            df_ct,
            transforms=build_ct_transforms(),
            image_root=image_root,
            out_dir=prep_dir / "ct",
            modality="CT",
            ext=".nii.gz",
        )
        out_csv = args.cohort_ct.replace(".csv", "_preprocessed.csv")
        df_ct.to_csv(out_csv, index=False)
        log.info(f"  Saved → {out_csv}")

    if not args.skip_cxr:
        log.info("─" * 60)
        log.info("Preprocessing CXR …")
        df_cxr = pd.read_csv(args.cohort_cxr, low_memory=False)
        log.info(f"  Loaded {len(df_cxr):,} CXR series from {args.cohort_cxr}")
        df_cxr = preprocess_cohort(
            df_cxr,
            transforms=build_cxr_transforms(),
            image_root=image_root,
            out_dir=prep_dir / "cxr",
            modality="CXR",
            ext=".npy",
        )
        out_csv = args.cohort_cxr.replace(".csv", "_preprocessed.csv")
        df_cxr.to_csv(out_csv, index=False)
        log.info(f"  Saved → {out_csv}")

    log.info("\nDone. Next: python scripts/train.py")


if __name__ == "__main__":
    main()