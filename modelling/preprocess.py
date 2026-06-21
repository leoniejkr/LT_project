#!/usr/bin/env python3
"""
scripts/preprocess.py
─────────────────────
Runs MONAI preprocessing on downloaded MIDRC images and writes
ready-to-train tensors into data/preprocessed/{ct,cxr}/.

CT  → HU windowing → RAS reorient → isotropic resampling → crop → resize → z-score → .nii.gz
CXR → 16-bit normalize → CLAHE → resize → ImageNet norm → .npy

Usage:
    python scripts/preprocess.py \
        --cohort-ct  data/cohort_ct.csv \
        --cohort-cxr data/cohort_cxr.csv \
        --image-root images/ \
        --prep-dir   data/preprocessed/ \
        --workers    4

Skips already-preprocessed files (safe to rerun after partial completion).
"""

import argparse
import logging
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
    from monai.data import ITKReader
except ImportError:
    raise SystemExit("Install MONAI: pip install monai[itk,nibabel,pillow]")

# ── Preprocessing parameters (must match config.yaml) ────────────────────────
CT_TARGET_SPACING = (1.5, 1.5, 2.0)
CT_TARGET_SHAPE   = (224, 224, 96)
CT_HU_LOW         = -1000
CT_HU_HIGH        = 400

CXR_TARGET_SHAPE  = (224, 224)


# ── Transform definitions ─────────────────────────────────────────────────────

def build_ct_transforms():
    return Compose([
        LoadImage(image_only=True, reader=ITKReader()),
        EnsureChannelFirst(),
        Orientation(axcodes="RAS"),
        Spacing(pixdim=CT_TARGET_SPACING, mode="bilinear"),
        ScaleIntensityRange(
            a_min=CT_HU_LOW, a_max=CT_HU_HIGH,
            b_min=0.0,        b_max=1.0, clip=True,
        ),
        CropForeground(source_key=None),
        Resize(spatial_size=CT_TARGET_SHAPE, mode="area"),
        NormalizeIntensity(nonzero=True, channel_wise=True),
    ])


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
        log.warning("skimage not found — skipping CLAHE. Install: pip install scikit-image")
        return x


def build_cxr_transforms():
    return Compose([
        LoadImage(image_only=True, reader=ITKReader()),
        EnsureChannelFirst(),
        ScaleIntensityRange(a_min=0, a_max=65535, b_min=0.0, b_max=1.0, clip=True),
        Lambda(func=_clahe),
        Resize(spatial_size=CXR_TARGET_SHAPE, mode="area"),
        NormalizeIntensity(
            subtrahend=0.485, divisor=0.229,
            nonzero=False, channel_wise=True,
        ),
    ])


# ── Per-series processor ──────────────────────────────────────────────────────

def preprocess_series(
    df: pd.DataFrame,
    transforms,
    image_root: Path,
    out_dir: Path,
    modality: str,
    ext: str,
) -> pd.DataFrame:
    import nibabel as nib

    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths = []
    skipped = processed = 0

    total = len(df)
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        obj_id = str(row.get("object_id", "unknown"))
        fname  = str(row.get("file_name", ""))

        # gen3-client saves to: <image_root>/<modality>/<object_id>/<filename>
        # Try both layouts (with and without modality subdir)
        candidates = [
            image_root / modality.lower() / obj_id / fname,
            image_root / obj_id / fname,
        ]
        src_path = next((p for p in candidates if p.exists()), None)

        save_path = out_dir / f"{obj_id}{ext}"

        if save_path.exists():
            out_paths.append(str(save_path))
            continue

        if src_path is None:
            log.warning(f"[{idx}/{total}] Not found: {obj_id}/{fname}")
            out_paths.append("")
            skipped += 1
            continue

        try:
            tensor = transforms(str(src_path))
            arr = tensor.numpy() if hasattr(tensor, "numpy") else np.array(tensor)

            if ext == ".nii.gz":
                nii = nib.Nifti1Image(arr[0], affine=np.eye(4))
                nib.save(nii, str(save_path))
            else:
                np.save(str(save_path), arr)
                save_path = Path(str(save_path))  # already .npy

            out_paths.append(str(save_path))
            processed += 1

            if idx % 50 == 0:
                log.info(f"  {idx}/{total} processed ({skipped} skipped so far)")

        except Exception as exc:
            log.warning(f"[{idx}/{total}] Failed {obj_id}: {exc}")
            out_paths.append("")
            skipped += 1

    log.info(
        f"{modality}: {processed} processed, {skipped} skipped, "
        f"{len(df) - processed - skipped} already cached"
    )

    df_out = df.copy()
    df_out["preprocessed_path"] = out_paths
    return df_out


# ── Main ─────────────────────────────────────────────────────────────────────

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

    ct_transforms  = build_ct_transforms()
    cxr_transforms = build_cxr_transforms()

    if not args.skip_ct:
        log.info("─" * 60)
        log.info("Preprocessing CT …")
        df_ct = pd.read_csv(args.cohort_ct, low_memory=False)
        df_ct = preprocess_series(
            df_ct, ct_transforms,
            image_root=image_root,
            out_dir=prep_dir / "ct",
            modality="CT",
            ext=".nii.gz",
        )
        df_ct.to_csv(args.cohort_ct.replace(".csv", "_preprocessed.csv"), index=False)
        log.info(f"Updated cohort saved → {args.cohort_ct.replace('.csv', '_preprocessed.csv')}")

    if not args.skip_cxr:
        log.info("─" * 60)
        log.info("Preprocessing CXR …")
        df_cxr = pd.read_csv(args.cohort_cxr, low_memory=False)
        df_cxr = preprocess_series(
            df_cxr, cxr_transforms,
            image_root=image_root,
            out_dir=prep_dir / "cxr",
            modality="CXR",
            ext=".npy",
        )
        df_cxr.to_csv(args.cohort_cxr.replace(".csv", "_preprocessed.csv"), index=False)
        log.info(f"Updated cohort saved → {args.cohort_cxr.replace('.csv', '_preprocessed.csv')}")

    log.info("\nDone. Next step: python scripts/train.py")


if __name__ == "__main__":
    main()
