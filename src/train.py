import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from sklearn.model_selection import GroupShuffleSplit
from PIL import Image
import torchvision.models as models
import wandb
from tqdm import tqdm

# 1. Classes & Global Configurations
ALL_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'Covid']

config = {
    "batch_size": 32,
    "epochs": 10,
    "learning_rate": 1e-4,
    "architecture": "ResNet50",
    "dataset": "NIH-MIDRC-Hybrid",
    "resolution": 224
}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))

class HybridXRayDataset(Dataset):
    def __init__(self, dataframe, transform=None):
        self.df = dataframe
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        image = Image.open(row['img_path']).convert('RGB')
        labels = torch.tensor(row[ALL_CLASSES].values.astype(np.float32))
        if self.transform:
            image = self.transform(image)
        return image, labels


# ALL EXECUTION CODE MUST BE INSIDE THIS GUARD:
if __name__ == '__main__':
    # Initialize wandb experiment tracking
    wandb.init(project="hybrid-xray-covid", name="experiment-1",config=config)

    # 2. Grouped Split by Patient ID
    df = pd.read_csv("data_hybrid/combined_master.csv", low_memory=False)
    df['patient_id'] = df['patient_id'].astype(str)

    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.1, random_state=42)
    train_val_idx, test_idx = next(gss1.split(df, groups=df['patient_id']))
    df_train_val = df.iloc[train_val_idx].reset_index(drop=True)
    df_test = df.iloc[test_idx].reset_index(drop=True)

    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.111, random_state=42)
    train_idx, val_idx = next(gss2.split(df_train_val, groups=df_train_val['patient_id']))
    df_train = df_train_val.iloc[train_idx].reset_index(drop=True)
    df_val = df_train_val.iloc[val_idx].reset_index(drop=True)

    # 4. Transformations and DataLoaders
    train_transforms = transforms.Compose([
        transforms.Resize((config["resolution"], config["resolution"])),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transforms = transforms.Compose([
        transforms.Resize((config["resolution"], config["resolution"])),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Fixed: Added num_workers=4, dropped unsupported pin_memory
    train_loader = DataLoader(
        HybridXRayDataset(df_train, train_transforms), 
        batch_size=config["batch_size"], 
        shuffle=True,
        num_workers=4
    )
    val_loader = DataLoader(
        HybridXRayDataset(df_val, val_transforms), 
        batch_size=config["batch_size"], 
        shuffle=False,
        num_workers=4
    )

    # 5. Model Compilation
    model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, len(ALL_CLASSES))
    model = model.to(DEVICE)

    wandb.watch(model, log="all", log_freq=100)

    # Positional weights for extreme class imbalance handling
    total_samples = 113120
    class_counts = np.array([11559, 2776, 4667, 2303, 13317, 2516, 1686, 227, 19894, 5782, 6331, 3385, 1431, 5302, 1000])
    neg_counts = total_samples - class_counts
    pos_weights = neg_counts / class_counts
    pos_weights_tensor = torch.tensor(pos_weights, dtype=torch.float32).to(DEVICE)

    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights_tensor)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])

    # 6. Hybrid Multi-Label Training Loop Execution
    for epoch in range(config["epochs"]):
        model.train()
        running_loss = 0.0
        
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{config['epochs']}", leave=True)
        
        for images, labels in progress_bar:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * images.size(0)
            progress_bar.set_postfix(batch_loss=f"{loss.item():.4f}")
            
        epoch_loss = running_loss / len(train_loader.dataset)
        print(f"\n🎉 Epoch {epoch+1} Complete. Average Training Loss: {epoch_loss:.4f}")
        
        wandb.log({
            "epoch": epoch + 1,
            "train_loss": epoch_loss
        })

    wandb.finish()