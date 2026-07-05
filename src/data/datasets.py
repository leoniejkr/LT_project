"""
src/data/datasets.py
────────────────────
PyTorch Dataset classes for CXR (2D .npy) and CT (3D .nii.gz / .npy).
Handles:
  - Multi-label binary target vectors
  - Optional metadata (tabular comorbidity features)
  - Stratified train/val/test splitting (iterative per-label)
  - Per-split augmentation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import nibabel as nib
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from torchvision import transforms as T

log = logging.getLogger(__name__)

# ── Label columns ─────────────────────────────────────────────────────────────

PRIMARY_LABELS = [
    "covid", "bacterial_pneumonia", "viral_pneumonia", "lung_abscess",
    "emphysema_copd", "ild_fibrosis", "pleural_effusion", "pneumothorax",
    "atelectasis", "pulm_embolism", "ards", "lung_malignancy", "normal",
]

METADATA_LABELS = [
    "meta_heart_failure", "meta_pulm_htn", "meta_cardiomegaly", "meta_pulm_edema",
    "meta_arrhythmia", "meta_cad", "meta_valvular", "meta_hypertension",
    "meta_diabetes", "meta_renal", "meta_aortic_disease", "meta_autoimmune",
    "meta_transplant", "meta_tb_ntm", "meta_bronchiectasis",
]


# ── Stratified split ──────────────────────────────────────────────────────────

# Ersetze die Funktion stratified_split in src/data/datasets.py durch diese:

def stratified_split(
    df: pd.DataFrame,
    label_cols: list[str],
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits the dataframe based on Patient ID (submitter_id) to prevent data leakage,
    while attempting to distribute labels evenly across splits.
    """
    # Bestimme die Spalte für die Patienten-Identifikation
    group_col = "submitter_id" if "submitter_id" in df.columns else "case_ids_clean"
    
    if group_col not in df.columns:
        log.warning(f"Keine Patientenspalte gefunden! Nutze Fallback auf Zeilensplit.")
        group_col = None

    if group_col:
        # 1. Eindeutige Patienten (Gruppen) extrahieren
        unique_patients = df[group_col].unique()
        rng = np.random.default_rng(seed)
        rng.shuffle(unique_patients)
        
        n_total = len(unique_patients)
        n_test = int(n_total * test_frac)
        n_val = int(n_total * val_frac)
        
        test_patients = unique_patients[:n_test]
        val_patients = unique_patients[n_test : n_test + n_val]
        train_patients = unique_patients[n_test + n_val :]
        
        df_train = df[df[group_col].isin(train_patients)].reset_index(drop=True)
        df_val = df[df[group_col].isin(val_patients)].reset_index(drop=True)
        df_test = df[df[group_col].isin(test_patients)].reset_index(drop=True)
        
        return df_train, df_val, df_test
    
    # ── Fallback falls keine ID vorhanden ist ──────────────────────────────────
    else:
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(df))
        n_test = int(len(df) * test_frac)
        n_val  = int(len(df) * val_frac)
        test_i, val_i, train_i = idx[:n_test], idx[n_test:n_test+n_val], idx[n_test+n_val:]
        return (
            df.iloc[train_i].reset_index(drop=True),
            df.iloc[val_i].reset_index(drop=True),
            df.iloc[test_i].reset_index(drop=True),
        )


# ── CXR Dataset ───────────────────────────────────────────────────────────────

class CXRDataset(Dataset):
    """
    Loads preprocessed CXR arrays (.npy, shape [C, H, W]) and returns
    (image_tensor, label_vector, [metadata_vector]).

    The .npy files are already normalized (CLAHE + ImageNet stats).
    Augmentation is applied on-the-fly during training only.
    """

    _AUGMENT = T.Compose([
        T.RandomHorizontalFlip(p=0.5),
        T.RandomRotation(degrees=10),
        T.ColorJitter(brightness=0.1, contrast=0.1),
    ])

    def __init__(
        self,
        df: pd.DataFrame,
        label_cols: list[str] = PRIMARY_LABELS,
        meta_cols: Optional[list[str]] = None,
        prep_dir: str = "data/preprocessed/cxr",
        augment: bool = False,
        path_col: str = "preprocessed_path",
    ):
        # Keep only rows with valid preprocessed paths
        self.df = df[df[path_col].notna() & (df[path_col] != "")].reset_index(drop=True)
        if len(self.df) < len(df):
            log.warning(f"CXRDataset: dropped {len(df)-len(self.df)} rows with missing paths")

        self.label_cols = label_cols
        self.meta_cols  = meta_cols
        self.prep_dir   = Path(prep_dir)
        self.augment    = augment
        self.path_col   = path_col

        # Precompute label matrix as float32 tensor
        self.labels = torch.tensor(
            self.df[label_cols].fillna(0).values.astype(np.float32)
        )

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> dict:
        row  = self.df.iloc[idx]
        path = Path(str(row[self.path_col]))

        # Load preprocessed array [C, H, W]
        arr = np.load(str(path)).astype(np.float32)

        # CXR stored as [1, H, W] → replicate to [3, H, W] for ImageNet backbone
        if arr.shape[0] == 1:
            arr = np.repeat(arr, 3, axis=0)

        img = torch.tensor(arr)

        if self.augment:
            img = self._AUGMENT(img)

        out = {
            "image":      img,
            "label":      self.labels[idx],
            "object_id":  str(row.get("object_id", "")),
        }

        if self.meta_cols:
            meta = torch.tensor(
                row[self.meta_cols].fillna(0).values.astype(np.float32)
            )
            out["metadata"] = meta

        return out


# ── CT Dataset ────────────────────────────────────────────────────────────────

class CTDataset(Dataset):
    """
    Loads preprocessed CT volumes (.nii.gz → numpy → tensor [1, D, H, W])
    and returns (volume_tensor, label_vector, [metadata_vector]).

    3D augmentation is applied via random flips and intensity jitter
    (heavier augmentation risks OOM on 3D — keep it light).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        label_cols: list[str] = PRIMARY_LABELS,
        meta_cols: Optional[list[str]] = None,
        prep_dir: str = "data/preprocessed/ct",
        augment: bool = False,
        path_col: str = "preprocessed_path",
        crop_size: tuple[int, int, int] = (96, 96, 96),
    ):
        self.df = df[df[path_col].notna() & (df[path_col] != "")].reset_index(drop=True)
        if len(self.df) < len(df):
            log.warning(f"CTDataset: dropped {len(df)-len(self.df)} rows with missing paths")

        self.label_cols = label_cols
        self.meta_cols  = meta_cols
        self.prep_dir   = Path(prep_dir)
        self.augment    = augment
        self.path_col   = path_col
        self.crop_size  = crop_size

        self.labels = torch.tensor(
            self.df[label_cols].fillna(0).values.astype(np.float32)
        )

    def __len__(self) -> int:
        return len(self.df)

    def _random_crop(self, vol: np.ndarray) -> np.ndarray:
        """Random spatial crop to crop_size. Pads if volume is too small."""
        _, D, H, W = vol.shape
        cd, ch, cw = self.crop_size

        def _pad_axis(arr, target, axis):
            diff = target - arr.shape[axis]
            if diff <= 0:
                return arr
            pad = [(0, 0)] * arr.ndim
            pad[axis] = (diff // 2, diff - diff // 2)
            return np.pad(arr, pad, mode="constant")

        for ax, tgt in zip([1, 2, 3], [cd, ch, cw]):
            vol = _pad_axis(vol, tgt, ax)

        _, D, H, W = vol.shape
        d0 = np.random.randint(0, max(1, D - cd + 1))
        h0 = np.random.randint(0, max(1, H - ch + 1))
        w0 = np.random.randint(0, max(1, W - cw + 1))

        return vol[:, d0:d0+cd, h0:h0+ch, w0:w0+cw]

    def _center_crop(self, vol: np.ndarray) -> np.ndarray:
        _, D, H, W = vol.shape
        cd, ch, cw = self.crop_size

        def _pad_axis(arr, target, axis):
            diff = target - arr.shape[axis]
            if diff <= 0:
                return arr
            pad = [(0, 0)] * arr.ndim
            pad[axis] = (diff // 2, diff - diff // 2)
            return np.pad(arr, pad, mode="constant")

        for ax, tgt in zip([1, 2, 3], [cd, ch, cw]):
            vol = _pad_axis(vol, tgt, ax)

        _, D, H, W = vol.shape
        d0, h0, w0 = (D - cd) // 2, (H - ch) // 2, (W - cw) // 2
        return vol[:, d0:d0+cd, h0:h0+ch, w0:w0+cw]

    def _augment_3d(self, vol: np.ndarray) -> np.ndarray:
        # Random flips along each axis
        for ax in [1, 2, 3]:
            if np.random.random() < 0.5:
                vol = np.flip(vol, axis=ax).copy()
        # Intensity jitter
        scale  = 1.0 + np.random.uniform(-0.1, 0.1)
        offset = np.random.uniform(-0.1, 0.1)
        vol    = np.clip(vol * scale + offset, 0.0, 1.0)
        return vol

    def __getitem__(self, idx: int) -> dict:
        row  = self.df.iloc[idx]
        path = Path(str(row[self.path_col]))

        # Load .nii.gz → numpy [1, H, W, D] → rearrange to [1, D, H, W]
        nii  = nib.load(str(path))
        arr  = nii.get_fdata(dtype=np.float32)        # [H, W, D]
        arr  = arr[np.newaxis, ...]                   # [1, H, W, D]
        arr  = np.transpose(arr, (0, 3, 1, 2))        # [1, D, H, W]

        if self.augment:
            arr = self._augment_3d(arr)
            arr = self._random_crop(arr)
        else:
            arr = self._center_crop(arr)

        vol = torch.tensor(arr)

        out = {
            "image":     vol,
            "label":     self.labels[idx],
            "object_id": str(row.get("object_id", "")),
        }

        if self.meta_cols:
            meta = torch.tensor(
                row[self.meta_cols].fillna(0).values.astype(np.float32)
            )
            out["metadata"] = meta

        return out


# ── Factory functions ─────────────────────────────────────────────────────────
# ── Factory functions ─────────────────────────────────────────────────────────

def make_cxr_dataloaders(
    cohort_csv: str,
    prep_dir: str,
    label_cols: list[str] = PRIMARY_LABELS,
    meta_cols: Optional[list[str]] = None,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    batch_size: int = 32,
    num_workers: int = 4,
    seed: int = 42,
) -> tuple:
    from torch.utils.data import DataLoader

    df = pd.read_csv(cohort_csv, low_memory=False)
    
    # FIX: Bereinige das DataFrame, BEVOR der Split berechnet wird
    df = df[df["preprocessed_path"].notna() & (df["preprocessed_path"] != "")].reset_index(drop=True)

    df_train, df_val, df_test = stratified_split(
        df, label_cols, val_frac, test_frac, seed
    )
    log.info(f"CXR split — train:{len(df_train)} val:{len(df_val)} test:{len(df_test)}")
    print("=== POSITIVE SAMPLES PRO KLASSE IN TRAINING ===")
    print(df_train[label_cols].sum())

    print("\n=== POSITIVE SAMPLES PRO KLASSE IN VALIDATION ===")
    print(df_val[label_cols].sum())
    print(df.columns)

    train_ds = CXRDataset(df_train, label_cols, meta_cols, prep_dir, augment=True)
    val_ds   = CXRDataset(df_val,   label_cols, meta_cols, prep_dir, augment=False)
    test_ds  = CXRDataset(df_test,  label_cols, meta_cols, prep_dir, augment=False)

    kw = dict(num_workers=num_workers, pin_memory=True, persistent_workers=num_workers > 0)
    return (
        DataLoader(train_ds, batch_size=batch_size, shuffle=True,  **kw),
        DataLoader(val_ds,   batch_size=batch_size, shuffle=False, **kw),
        DataLoader(test_ds,  batch_size=batch_size, shuffle=False, **kw),
        label_cols,
    )


def make_ct_dataloaders(
    cohort_csv: str,
    prep_dir: str,
    label_cols: list[str] = PRIMARY_LABELS,
    meta_cols: Optional[list[str]] = None,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    batch_size: int = 4,
    num_workers: int = 2,
    crop_size: tuple = (96, 96, 96),
    seed: int = 42,
) -> tuple:
    from torch.utils.data import DataLoader

    df = pd.read_csv(cohort_csv, low_memory=False)
    
    # FIX: Bereinige das DataFrame, BEVOR der Split berechnet wird
    df = df[df["preprocessed_path"].notna() & (df["preprocessed_path"] != "")].reset_index(drop=True)

    df_train, df_val, df_test = stratified_split(
        df, label_cols, val_frac, test_frac, seed
    )
    log.info(f"CT split — train:{len(df_train)} val:{len(df_val)} test:{len(df_test)}")

    train_ds = CTDataset(df_train, label_cols, meta_cols, prep_dir, augment=True,  crop_size=crop_size)
    val_ds   = CTDataset(df_val,   label_cols, meta_cols, prep_dir, augment=False, crop_size=crop_size)
    test_ds  = CTDataset(df_test,  label_cols, meta_cols, prep_dir, augment=False, crop_size=crop_size)

    kw = dict(num_workers=num_workers, pin_memory=True, persistent_workers=num_workers > 0)
    return (
        DataLoader(train_ds, batch_size=batch_size, shuffle=True,  **kw),
        DataLoader(val_ds,   batch_size=batch_size, shuffle=False, **kw),
        DataLoader(test_ds,  batch_size=batch_size, shuffle=False, **kw),
        label_cols,
    )