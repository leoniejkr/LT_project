"""
Cohort Processor for Medical Imaging ML Pipeline
================================================

Handles:
  • General Processing: balancing, missing values, train/val/test splits
  • Image Processing: MONAI transforms (normalization, resizing, augmentation)
  • DataLoader creation: tensor conversion, batching, augmentation chains

Usage:
    processor = CohortProcessor(
        ct_cohort_path="data/cohort_ct.csv",
        cxr_cohort_path="data/cohort_cxr.csv",
        dicom_dir="dicom_data/",
        label_map_path="data/label_map.json"
    )
    
    train_loader, val_loader, test_loader = processor.get_dataloaders(
        modality="CT",
        batch_size=32,
        image_size=(512, 512),
        num_workers=4
    )
"""

import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, List, Dict, Optional
from sklearn.model_selection import train_test_split
from collections import Counter

import torch
from torch.utils.data import Dataset, DataLoader

import monai
from monai.transforms import (
    Compose,
    LoadImage,
    EnsureChannelFirst,
    Resize,
    NormalizeIntensity,
    RandRotate90,
    RandFlip,
    RandAffine,
    RandGaussianNoise,
    RandGaussianSmooth,
    EnsureType,
)
from monai.data import list_data_collate


# ──────────────────────────────────────────────────────────────────────────────
# 1. MONAI DATASET
# ──────────────────────────────────────────────────────────────────────────────

class MedicalImagingDataset(Dataset):
    """
    PyTorch Dataset for medical imaging with MONAI transforms.
    
    Args:
        df: DataFrame with columns [image_path, ...label_cols]
        label_cols: List of label column names (for multi-label classification)
        image_col: Column name containing image file paths
        transforms: MONAI Compose object with transforms
        image_size: Tuple (height, width) for resizing
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        label_cols: List[str],
        image_col: str = "image_path",
        transforms: Optional[Compose] = None,
        image_size: Tuple[int, int] = (512, 512),
    ):
        self.df = df.reset_index(drop=True)
        self.label_cols = label_cols
        self.image_col = image_col
        self.transforms = transforms
        self.image_size = image_size
        
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx: int) -> Dict:
        row = self.df.iloc[idx]
        
        # Load image
        image_path = row[self.image_col]
        image = monai.transforms.LoadImage(image_only=True)(image_path)
        
        # Ensure channel-first format (C, H, W)
        if image.ndim == 2:  # Grayscale: H x W
            image = np.expand_dims(image, axis=0)  # → 1 x H x W
        
        # Apply transforms if provided
        if self.transforms:
            data = {"image": image}
            data = self.transforms(data)
            image = data["image"]
        
        # Extract labels
        labels = torch.tensor(
            [int(row[col]) for col in self.label_cols],
            dtype=torch.float32
        )
        
        # Metadata (for debugging / analysis)
        metadata = {
            "image_path": image_path,
            "case_id": row.get("submitter_id", "unknown"),
        }
        
        return {
            "image": image,
            "labels": labels,
            "metadata": metadata,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 2. COHORT PROCESSOR
# ──────────────────────────────────────────────────────────────────────────────

class CohortProcessor:
    """
    End-to-end cohort processing: load → balance → split → create dataloaders
    """
    
    def __init__(
        self,
        ct_cohort_path: str,
        cxr_cohort_path: str,
        dicom_dir: str,
        label_map_path: str,
        random_state: int = 42,
    ):
        """
        Args:
            ct_cohort_path: Path to cohort_ct.csv
            cxr_cohort_path: Path to cohort_cxr.csv
            dicom_dir: Root directory containing DICOM files
            label_map_path: Path to label_map.json
            random_state: For reproducibility
        """
        self.random_state = random_state
        self.dicom_dir = Path(dicom_dir)
        
        # Load cohorts
        print("Loading cohorts...")
        self.df_ct = pd.read_csv(ct_cohort_path)
        self.df_cxr = pd.read_csv(cxr_cohort_path)
        
        # Load label map
        with open(label_map_path, "r") as f:
            self.label_map = json.load(f)
        
        self.imaging_labels = self.label_map["imaging_labels"]
        self.all_label_cols = self.label_map["all_label_cols"]
        
        print(f"  CT cohort:  {len(self.df_ct)} series")
        print(f"  CXR cohort: {len(self.df_cxr)} series")
        print(f"  Label columns ({len(self.imaging_labels)}): {self.imaging_labels}")
    
    
    def _locate_dicom_files(self, df: pd.DataFrame, modality: str) -> pd.DataFrame:
        """
        Map object_id → actual DICOM file path.
        
        Assumes DICOM structure:
          dicom_data/{case_id}/[IM_*.dcm or similar]
        
        Returns updated DataFrame with 'image_path' column.
        """
        print(f"\nLocating DICOM files ({modality})...")
        
        image_paths = []
        found_count = 0
        
        for idx, row in df.iterrows():
            object_id = row.get("object_id")
            case_id = row.get("case_ids_clean") or row.get("submitter_id")
            
            # Try to find DICOM file in case directory
            case_dir = self.dicom_dir / str(case_id)
            
            if not case_dir.exists():
                image_paths.append(None)
                continue
            
            # Look for .dcm files
            dcm_files = list(case_dir.glob("*.dcm"))
            
            if dcm_files:
                # For now, take first .dcm file
                # In production, might need series-specific selection
                image_paths.append(str(dcm_files[0]))
                found_count += 1
            else:
                image_paths.append(None)
        
        df = df.copy()
        df["image_path"] = image_paths
        
        # Remove rows without valid image paths
        df = df[df["image_path"].notna()].reset_index(drop=True)
        
        print(f"  Found {found_count}/{len(image_paths)} DICOM files")
        print(f"  Final cohort size: {len(df)}")
        
        return df
    
    
    def _fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fill missing values in label columns.
        
        Strategy:
          • Labels (imaging): fill with 0 (assumed negative if not annotated)
          • Risk features: forward fill, backward fill, then median
        """
        print("\nFilling missing values...")
        
        df = df.copy()
        
        # Fill label columns with 0
        for col in self.all_label_cols:
            if col in df.columns:
                before_missing = df[col].isna().sum()
                df[col] = df[col].fillna(0).astype(int)
                if before_missing > 0:
                    print(f"  {col}: filled {before_missing} missing")
        
        # Fill risk features with median (numeric columns only)
        risk_cols = [c for c in df.columns if c.startswith(("risk_", "mrale_", "airspace_"))]
        for col in risk_cols:
            if col in df.columns and df[col].dtype in ["float64", "float32"]:
                before_missing = df[col].isna().sum()
                df[col] = df[col].fillna(df[col].median())
                if before_missing > 0:
                    print(f"  {col}: filled {before_missing} with median")
        
        return df
    
    
    def _balance_classes(self, df: pd.DataFrame, balance_strategy: str = "undersample") -> pd.DataFrame:
        """
        Balance label distribution.
        
        Args:
            balance_strategy: "undersample" (remove majority) or "oversample" (duplicate minority)
        
        Note: For multi-label data, balancing is approximate. We balance on
        the most frequent label and keep all examples.
        """
        print(f"\nBalancing classes ({balance_strategy})...")
        
        df = df.copy()
        
        # Compute label distribution
        label_counts = df[self.imaging_labels].sum().sort_values(ascending=False)
        print(f"  Before balancing:")
        for label, count in label_counts.items():
            pct = 100 * count / len(df)
            print(f"    {label:<20}: {int(count):>4}  ({pct:5.1f}%)")
        
        # For demonstration: simple undersample to max class size
        # In practice, consider: stratified split, weighted sampling, etc.
        if balance_strategy == "undersample":
            target_size = int(label_counts.min() * 1.5)  # 1.5x smallest class
            target_size = min(target_size, len(df))
            
            df = df.sample(n=target_size, random_state=self.random_state)
            df = df.reset_index(drop=True)
        
        print(f"  After balancing: {len(df)} samples")
        return df
    
    
    def _train_val_test_split(
        self,
        df: pd.DataFrame,
        train_size: float = 0.7,
        val_size: float = 0.15,
        test_size: float = 0.15,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Stratified split on primary label (COVID status).
        
        Returns: (train_df, val_df, test_df)
        """
        print(f"\nTrain/Val/Test split ({train_size}/{val_size}/{test_size})...")
        
        # Use 'covid' as stratification if available, else use risk_tier
        stratify_col = "covid" if "covid" in df.columns else "risk_tier"
        stratify = df[stratify_col] if stratify_col in df.columns else None
        
        # First split: train vs (val+test)
        df_train, df_temp = train_test_split(
            df,
            train_size=train_size,
            test_size=(val_size + test_size),
            random_state=self.random_state,
            stratify=stratify,
        )
        
        # Second split: val vs test (from temp)
        val_frac = val_size / (val_size + test_size)
        df_val, df_test = train_test_split(
            df_temp,
            train_size=val_frac,
            random_state=self.random_state,
            stratify=df_temp[stratify_col] if stratify_col in df_temp.columns else None,
        )
        
        print(f"  Train: {len(df_train)} ({100*len(df_train)/len(df):.1f}%)")
        print(f"  Val:   {len(df_val)} ({100*len(df_val)/len(df):.1f}%)")
        print(f"  Test:  {len(df_test)} ({100*len(df_test)/len(df):.1f}%)")
        
        return df_train, df_val, df_test
    
    
    def _create_transforms(
        self,
        image_size: Tuple[int, int] = (512, 512),
        augment: bool = True,
    ) -> Tuple[Compose, Compose]:
        """
        Create MONAI transform pipelines.
        
        Returns: (train_transforms, val_test_transforms)
        """
        
        # Shared preprocessing (normalization, resizing)
        base_transforms = [
            LoadImage(image_only=True),
            EnsureChannelFirst(),
            Resize(spatial_size=image_size),
            NormalizeIntensity(subtrahend=128, divisor=255, nonzero=True),  # Normalize to ~[-1, 1]
            EnsureType(dtype=torch.float32),
        ]
        
        # Training: add augmentation
        train_transforms = base_transforms.copy()
        if augment:
            train_transforms.extend([
                RandRotate90(prob=0.3, spatial_axes=(0, 1)),
                RandFlip(prob=0.3, spatial_axis=0),
                RandFlip(prob=0.3, spatial_axis=1),
                RandAffine(
                    prob=0.3,
                    translate_range=(10, 10),
                    rotate_range=(np.pi / 12, np.pi / 12),
                    scale_range=(0.1, 0.1),
                ),
                RandGaussianNoise(prob=0.2, std=0.05),
                RandGaussianSmooth(prob=0.2, sigma_x=(0.5, 1.5)),
            ])
        
        train_transforms = Compose(train_transforms)
        val_test_transforms = Compose(base_transforms)
        
        return train_transforms, val_test_transforms
    
    
    def process(
        self,
        modality: str = "CT",
        balance: bool = True,
        balance_strategy: str = "undersample",
        train_size: float = 0.7,
        val_size: float = 0.15,
        test_size: float = 0.15,
    ) -> Dict[str, pd.DataFrame]:
        """
        Main processing pipeline.
        
        Args:
            modality: "CT" or "CXR"
            balance: Whether to balance class distribution
            balance_strategy: "undersample" or "oversample"
            train_size, val_size, test_size: Split ratios
        
        Returns:
            Dict with keys: train_df, val_df, test_df
        """
        
        # Select cohort
        df = self.df_ct.copy() if modality.upper() == "CT" else self.df_cxr.copy()
        print(f"\n{'='*70}")
        print(f"  Processing {modality} Cohort")
        print(f"{'='*70}")
        print(f"Initial size: {len(df)}")
        
        # Locate DICOM files
        df = self._locate_dicom_files(df, modality)
        
        # Fill missing values
        df = self._fill_missing_values(df)
        
        # Balance (optional)
        if balance:
            df = self._balance_classes(df, balance_strategy)
        
        # Split
        df_train, df_val, df_test = self._train_val_test_split(
            df, train_size=train_size, val_size=val_size, test_size=test_size
        )
        
        return {
            "train_df": df_train,
            "val_df": df_val,
            "test_df": df_test,
        }
    
    
    def get_dataloaders(
        self,
        modality: str = "CT",
        batch_size: int = 32,
        image_size: Tuple[int, int] = (512, 512),
        num_workers: int = 4,
        augment: bool = True,
        balance: bool = True,
        **split_kwargs,
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        End-to-end: process cohort → create datasets → wrap in dataloaders.
        
        Returns: (train_loader, val_loader, test_loader)
        """
        
        # Process cohort
        splits = self.process(modality=modality, balance=balance, **split_kwargs)
        
        # Create transforms
        train_transforms, val_test_transforms = self._create_transforms(
            image_size=image_size, augment=augment
        )
        
        # Create datasets
        print(f"\nCreating datasets...")
        train_dataset = MedicalImagingDataset(
            df=splits["train_df"],
            label_cols=self.imaging_labels,
            transforms=train_transforms,
            image_size=image_size,
        )
        val_dataset = MedicalImagingDataset(
            df=splits["val_df"],
            label_cols=self.imaging_labels,
            transforms=val_test_transforms,
            image_size=image_size,
        )
        test_dataset = MedicalImagingDataset(
            df=splits["test_df"],
            label_cols=self.imaging_labels,
            transforms=val_test_transforms,
            image_size=image_size,
        )
        
        # Create dataloaders
        print(f"\nCreating dataloaders...")
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers,
            collate_fn=list_data_collate,
            pin_memory=True,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            collate_fn=list_data_collate,
            pin_memory=True,
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            collate_fn=list_data_collate,
            pin_memory=True,
        )
        
        print(f"  Train loader: {len(train_loader)} batches of {batch_size}")
        print(f"  Val loader:   {len(val_loader)} batches of {batch_size}")
        print(f"  Test loader:  {len(test_loader)} batches of {batch_size}")
        
        return train_loader, val_loader, test_loader


# ──────────────────────────────────────────────────────────────────────────────
# 3. EXAMPLE USAGE
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    processor = CohortProcessor(
        ct_cohort_path="../data/cohort_ct.csv",
        cxr_cohort_path="../data/cohort_cxr.csv",
        dicom_dir="../dicom_data/",
        label_map_path="../data/label_map.json",
    )
    
    # Get dataloaders for CT
    train_loader, val_loader, test_loader = processor.get_dataloaders(
        modality="CT",
        batch_size=16,
        image_size=(512, 512),
        num_workers=4,
        augment=True,
        balance=True,
    )
    
    # Inspect a single batch
    print("\n" + "="*70)
    print("Sample batch inspection:")
    print("="*70)
    batch = next(iter(train_loader))
    print(f"\nBatch keys: {batch.keys()}")
    print(f"Image shape: {batch['image'].shape}")  # (batch, channels, H, W)
    print(f"Labels shape: {batch['labels'].shape}")  # (batch, num_labels)
    print(f"Sample labels: {batch['labels'][0]}")
    print(f"Sample metadata: {batch['metadata'][0]}")
