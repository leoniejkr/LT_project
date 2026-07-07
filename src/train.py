#!/usr/bin/env python3
"""
scripts/train.py
─────────────────
Builds a unified dataframe combining Kaggle hub (NIH) + Preprocessed MIDRC (Covid),
splits safely by Patient ID, and handles the multi-label 2D training sequence.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from torchvision import transforms
import torchvision.models as models

import lightning as L
from lightning.pytorch.callbacks import ModelCheckpoint, LearningRateMonitor

# Adjust paths to allow module discovery
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.lightning_module import MultiLabelModule, tune_thresholds

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

NIH_CLASSES = [
    'Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
    'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
    'Pleural_Thickening', 'Pneumonia', 'Pneumothorax'
]
ALL_CLASSES = NIH_CLASSES + ['Covid']


class Hybrid2DChestDataset(Dataset):
    """Loads a unified 2D image coordinate and converts it to a standard 3-channel input."""
    def __init__(self, dataframe, class_list, transform=None):
        self.df = dataframe
        self.class_list = class_list
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # Always convert to RGB (3-channel) because ImageNet backbones expect 3 input channels!
        image = Image.open(row['img_path']).convert('RGB')
        targets = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
        if self.transform:
            image = self.transform(image)
            
        return image, targets


def build_master_dataframe(nih_root: str, midrc_manifest: str) -> pd.DataFrame:
    """Reads both metadata sheets and creates a harmonized tracking file."""
    log.info("Constructing consolidated master dataset tracker...")

    # 1. Parse NIH (Kaggle)
    nih_csv = os.path.join(nih_root, "Data_Entry_2017.csv")
    df_nih_raw = pd.read_csv(nih_csv)
    
    labels_dummies = df_nih_raw["Finding Labels"].str.get_dummies(sep="|")
    df_nih = pd.concat([df_nih_raw, labels_dummies], axis=1)

    df_nih_clean = pd.DataFrame()
    # Ensure correct mapping down into the unpacked Kaggle folder structure
    df_nih_clean['img_path'] = df_nih['Image Index'].apply(lambda x: os.path.join(nih_root, "images", x))
    df_nih_clean['patient_id'] = "nih_" + df_nih['Patient ID'].astype(str)

    for cls in NIH_CLASSES:
        df_nih_clean[cls] = df_nih[cls] if cls in df_nih.columns else 0
    df_nih_clean['Covid'] = 0

    # 2. Parse Preprocessed MIDRC COVID targets
    if os.path.exists(midrc_manifest):
        df_midrc = pd.read_csv(midrc_manifest)
        df_midrc_clean = pd.DataFrame()
        df_midrc_clean['img_path'] = df_midrc['img_path']
        df_midrc_clean['patient_id'] = "midrc_" + df_midrc['patient_id'].astype(str)
        
        for cls in NIH_CLASSES:
            df_midrc_clean[cls] = 0
        df_midrc_clean['Covid'] = 1
        
        # Combine them
        df_master = pd.concat([df_nih_clean, df_midrc_clean], axis=0).reset_index(drop=True)
    else:
        log.warning(f"MIDRC manifest not found at {midrc_manifest}. Running NIH only.")
        df_master = df_nih_clean

    return df_master


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nih-dir", required=True, help="Path to kagglehub downloaded dataset directory")
    p.add_argument("--midrc-manifest", default="data_hybrid/midrc_processed_manifest.csv")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    args = p.parse_args()

    # 1. Prepare master layout
    df_master = build_master_dataframe(args.nih_dir, args.midrc_manifest)

    # 2. PATIENT-SAFE SPLIT (Crucial step to avoid data-leakage across subsets)
    unique_patients = df_master["patient_id"].unique()
    train_p, val_p = train_test_split(unique_patients, test_size=0.15, random_state=42)
    
    df_train = df_master[df_master["patient_id"].isin(train_p)].copy().reset_index(drop=True)
    df_val = df_master[df_master["patient_id"].isin(val_p)].copy().reset_index(drop=True)
    log.info(f"Splits complete: Train items={len(df_train):,}, Val items={len(df_val):,}")

    # 3. Transform setups
    train_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 4. DataLoaders
    train_ds = Hybrid2DChestDataset(df_train, class_list=ALL_CLASSES, transform=train_transforms)
    val_ds = Hybrid2DChestDataset(df_val, class_list=ALL_CLASSES, transform=val_transforms)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=4, pin_memory=True)

    # 5. Model initialization using standard torchvision ResNet50
    # Change num_classes out of the classification head from 1000 (ImageNet) to 15
    base_model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    base_model.fc = nn.Linear(base_model.fc.in_features, len(ALL_CLASSES))

    # Initialize Multi Label Pipeline Module
    module = MultiLabelModule(
        model=base_model,
        label_names=ALL_CLASSES,
        loss_fn=nn.BCEWithLogitsLoss(), # BCE is required since classifications are non-exclusive
        lr=args.lr,
        max_epochs=args.epochs
    )

    # 6. Callbacks and training sequence
    ckpt_cb = ModelCheckpoint(monitor="val_auc", mode="max", save_top_k=1, filename="best_hybrid_model")
    lr_cb = LearningRateMonitor(logging_interval="epoch")

    trainer = L.Trainer(
        max_epochs=args.epochs,
        accelerator="auto",
        devices=1,
        callbacks=[ckpt_cb, lr_cb]
    )

    log.info("Starting training engine run...")
    trainer.fit(module, train_loader, val_loader)

    # 7. Post-training inference calibration
    log.info("Starting post-training validation threshold tuning...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    best_thresholds = tune_thresholds(module, val_loader, ALL_CLASSES, device)


if __name__ == "__main__":
    main()