import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score  
from PIL import Image
import torchvision.models as models
from model.train.models.multilabel_models import MultiLabelChestModel
import wandb
from tqdm import tqdm

# 1. Classes & Global Configurations
ALL_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'Covid']

config = {
    "batch_size": 32,
    "epochs": 5,
    "backbone_lr": 1e-5,        # Conservative LR for pre-trained weights
    "classifier_lr": 1e-4,      # Aggressive LR for head convergence
    "architecture": "DualStream-ResNet50",
    "dataset": "NIH-MIDRC-Hybrid-PatientContext",
    "resolution": 224
}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))


# 2. Patient Context Multi-Image Dataset
class PatientContextMultiViewDataset(Dataset):
    def __init__(self, dataframe, class_list, transform=None):
        self.df = dataframe.reset_index(drop=True)
        self.class_list = class_list
        self.transform = transform
        
        # Fast Lookup: Group paths by patient_id so we can find pairs instantly
        self.patient_image_groups = self.df.groupby('patient_id')['img_path'].apply(list).to_dict()

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        pid = str(row['patient_id'])
        primary_path = row['img_path']
        
        # Load primary target image
        img_primary = Image.open(primary_path).convert('RGB')
        
        # Search patient history for alternative image context
        all_patient_images = self.patient_image_groups.get(pid, [primary_path])
        alternative_images = [path for path in all_patient_images if path != primary_path]
        
        if len(alternative_images) > 0:
            context_path = alternative_images[0]
            img_context = Image.open(context_path).convert('RGB')
        else:
            # Fallback: Create a black placeholder image matching the size
            img_context = Image.new('RGB', img_primary.size, (0, 0, 0))
            
        labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
        if self.transform:
            img_primary = self.transform(img_primary)
            img_context = self.transform(img_context)
            
        return img_primary, img_context, labels

# 2. Simplified Single-View Dataset
class SingleViewXRayDataset(Dataset):
    def __init__(self, dataframe, class_list, transform=None):
        self.df = dataframe.reset_index(drop=True)
        self.class_list = class_list
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # Open only the target image
        img = Image.open(row['img_path']).convert('RGB')
        labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
        if self.transform:
            img = self.transform(img)
            
        return img, labels


if __name__ == '__main__':
    # Initialize wandb experiment tracking
    os.environ["WANDB_RETRY_MAX_TIMEOUT"] = "7200"
    
    # Initialize wandb experiment tracking
    # settings=wandb.Settings(start_method="fork") handles background process stability
    wandb.init(
        project="hybrid-xray-covid", 
        name="single-view-densenet-experiment", 
        config=config,
        settings=wandb.Settings(start_method="fork")
    )
    # 4. STRATEGY 1: Stratified Patient Splitting (No Data Leaks)
    df = pd.read_csv("data_hybrid/combined_master.csv", low_memory=False)
    df['patient_id'] = df['patient_id'].astype(str)

    # Generate a compound balancing key across critical target labels for robust stratification
    df['stratify_key'] = df['Covid'].astype(str) + "_" + df['Effusion'].astype(str)
    patient_labels = df.groupby('patient_id')['stratify_key'].first()

    # Split patient IDs securely while maintaining identical class distributions across splits
    train_val_patients, test_patients = train_test_split(
        patient_labels.index, test_size=0.1, random_state=42, stratify=patient_labels.values
    )
    train_patients, val_patients = train_test_split(
        train_val_patients, test_size=0.111, random_state=42, stratify=patient_labels[train_val_patients].values
    )

    df_train = df[df['patient_id'].isin(train_patients)].reset_index(drop=True)
    df_val = df[df['patient_id'].isin(val_patients)].reset_index(drop=True)
    df_test = df[df['patient_id'].isin(test_patients)].reset_index(drop=True)

    # 5. STRATEGY 2: Medical-Grade Augmentation Space
    train_transforms = transforms.Compose([
        transforms.Resize((config["resolution"], config["resolution"])),
        transforms.RandomHorizontalFlip(),          # Natural horizontal mirroring
        transforms.RandomRotation(5),               # Subtle rotation keeps anatomical correctness
        transforms.RandomAffine(                    # Compensates for breathing/position variations
            degrees=0, 
            translate=(0.1, 0.05), 
            scale=(0.85, 1.15), 
            shear=5
        ),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transforms = transforms.Compose([
        transforms.Resize((config["resolution"], config["resolution"])),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    train_loader = DataLoader(
        SingleViewXRayDataset(df_train, ALL_CLASSES, train_transforms), 
        batch_size=config["batch_size"], 
        shuffle=True,
        num_workers=4
    )
    val_loader = DataLoader(
        SingleViewXRayDataset(df_val, ALL_CLASSES, val_transforms), 
        batch_size=config["batch_size"], 
        shuffle=False,
        num_workers=4
    )

    # 6. Model Compilation
    model = MultiLabelChestModel(num_classes=len(ALL_CLASSES))
    model = model.to(DEVICE)

    wandb.watch(model, log="all", log_freq=100)

    # Positional weights for extreme class imbalance handling
    total_samples = 113120
    class_counts = np.array([11559, 2776, 4667, 2303, 13317, 2516, 1686, 227, 19894, 5782, 6331, 3385, 1431, 5302, 1000])
    neg_counts = total_samples - class_counts
    pos_weights = neg_counts / class_counts
    pos_weights_tensor = torch.tensor(pos_weights, dtype=torch.float32).to(DEVICE)

    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights_tensor)

    # ─── FIXED STRATEGY 3 ───────────────────────────────────────────────
    # Call configure_optimizers cleanly without invalid extra arguments
    optimizer_config = model.configure_optimizers()

    # Extract the raw PyTorch optimizer from the Lightning dictionary
    optimizer = optimizer_config["optimizer"]

    # Extract the pre-configured scheduler from the Lightning dictionary
    scheduler = optimizer_config["lr_scheduler"]["scheduler"]

    # 7. Hybrid Multi-Label Training Loop Execution
    for epoch in range(0, config["epochs"]+1):
        # ─── TRAINING PASS ──────────────────────────────────────────────────
        if epoch == 0:
            print("Running baseline validation pass prior to weight optimization adjustments...")
            epoch_train_loss = 0.0
        else: 
            model.train()
            running_train_loss = 0.0
            
            train_progress = tqdm(train_loader, desc=f"Epoch {epoch}/{config['epochs']} [Train]", leave=True)
            for images, labels in train_progress:
                images = images.to(DEVICE)
                labels = labels.to(DEVICE)
                
                optimizer.zero_grad()
                outputs = model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                
                running_train_loss += loss.item() * images.size(0)
                train_progress.set_postfix(batch_loss=f"{loss.item():.4f}")
                
            epoch_train_loss = running_train_loss / len(train_loader.dataset)
        
        # ─── VALIDATION PASS ────────────────────────────────────────────────
        model.eval()
        running_val_loss = 0.0
        all_val_labels = []
        all_val_preds = []
        
        val_progress = tqdm(val_loader, desc=f"Epoch {epoch}/{config['epochs']} [Val]", leave=True)
        with torch.no_grad():
            for images, labels in val_progress:
                images = images.to(DEVICE)
                labels = labels.to(DEVICE)
                
                outputs = model(images)
                loss = criterion(outputs, labels)
                running_val_loss += loss.item() * images.size(0)
                
                probs = torch.sigmoid(outputs)
                all_val_labels.append(labels.cpu().numpy())
                all_val_preds.append(probs.cpu().numpy())
                
        epoch_val_loss = running_val_loss / len(val_loader.dataset)
        
        # Only step the scheduler during actual training epochs (Epoch > 0)
        if epoch > 0:
            scheduler.step(epoch_val_loss)
        
        all_val_labels = np.vstack(all_val_labels)
        all_val_preds = np.vstack(all_val_preds)
        
        # Compute macro and per-class metrics securely
        try:
            epoch_macro_auc = roc_auc_score(all_val_labels, all_val_preds, average="macro")
        except ValueError:
            epoch_macro_auc = 0.5

        # Build a dictionary to track metrics dynamically
        metrics_to_log = {
            "epoch": epoch,
            "train_loss": epoch_train_loss if epoch > 0 else 0.0,
            "val_loss": epoch_val_loss,
            "val_macro_auc": epoch_macro_auc
        }

        print(f"\n🎉 Epoch {epoch} Performance Summary:")
        print(f"Val Loss: {epoch_val_loss:.4f} | Macro AUC: {epoch_macro_auc:.4f}")
        
        # Extract per-class AUC scores cleanly
        for i, class_name in enumerate(ALL_CLASSES):
            try:
                class_auc = roc_auc_score(all_val_labels[:, i], all_val_preds[:, i])
                metrics_to_log[f"val_auc_class/{class_name}"] = class_auc
                print(f" -> {class_name}: AUC = {class_auc:.4f}")
            except ValueError:
                metrics_to_log[f"val_auc_class/{class_name}"] = 0.5
                print(f" -> {class_name}: AUC = 0.5000 (Insufficient class instances)")

        # Extract current learning rates for log transparency
        if epoch > 0:
            current_lrs = [param_group['lr'] for param_group in optimizer.param_groups]
            metrics_to_log["backbone_lr"] = current_lrs[0]      # Features learning rate
            metrics_to_log["classifier_lr"] = current_lrs[1]    # Classification head learning rate (Changed from 2 to 1)
            torch.save(model.state_dict(), "dual_view_checkpoint.pth")


        print("\n")
        
        # Defensive logging: Prevent network connection exceptions from killing your local training run
        try:
            wandb.log(metrics_to_log)
        except Exception as e:
            print(f"[WandB Warning] Failed to log metrics due to network issue: {e}")
            print("Training will continue locally; wandb will attempt background reconnection.")

    torch.save(model.state_dict(), "checkpoint.pth")
    print("Model weights successfully saved locally to checkpoint.pth!")

    wandb.finish()