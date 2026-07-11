import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score  
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
    "architecture": "DualStream-ResNet50",
    "dataset": "NIH-MIDRC-Hybrid-PatientContext",
    "resolution": 224
}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))

# 2. NEW: Patient Context Multi-Image Dataset
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


# 3. NEW: Dual-Input Model Architecture 
class DualViewXRayNet(nn.Module):
    def __init__(self, num_classes=15):
        super(DualViewXRayNet, self).__init__()
        # Initialize two separate ResNet50 backbones
        self.frontal_backbone = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        self.context_backbone = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        
        # Extract features layers up until global pooling step
        self.frontal_features = nn.Sequential(*list(self.frontal_backbone.children())[:-1])
        self.context_features = nn.Sequential(*list(self.context_backbone.children())[:-1])
        
        # Fusion Classifier: Combine both feature spaces (2048 dimensions each)
        self.classifier = nn.Linear(2048 + 2048, num_classes)
        
    def forward(self, img_front, img_context):
        feat_front = self.frontal_features(img_front).squeeze(-1).squeeze(-1)
        feat_context = self.context_features(img_context).squeeze(-1).squeeze(-1)
        
        # Concatenate features horizontally
        combined_features = torch.cat((feat_front, feat_context), dim=1)
        return self.classifier(combined_features)


if __name__ == '__main__':
    # Initialize wandb experiment tracking
    wandb.init(project="hybrid-xray-covid", name="dual-view-experiment", config=config)

    # 4. Grouped Split by Patient ID
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

    # 5. Transformations and Updated DataLoaders
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

    train_loader = DataLoader(
        PatientContextMultiViewDataset(df_train, ALL_CLASSES, train_transforms), 
        batch_size=config["batch_size"], 
        shuffle=True,
        num_workers=4
    )
    val_loader = DataLoader(
        PatientContextMultiViewDataset(df_val, ALL_CLASSES, val_transforms), 
        batch_size=config["batch_size"], 
        shuffle=False,
        num_workers=4
    )

    # 6. Model Compilation
    model = DualViewXRayNet(num_classes=len(ALL_CLASSES))
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

    # 7. Hybrid Multi-Label Training Loop Execution
    for epoch in range(config["epochs"]):
        # ─── TRAINING PASS ──────────────────────────────────────────────────
        model.train()
        running_train_loss = 0.0
        
        train_progress = tqdm(train_loader, desc=f"Epoch {epoch+1}/{config['epochs']} [Train]", leave=True)
        # 🧠 Fixed: Unpack primary, context, and labels from data stream
        for images_primary, images_context, labels in train_progress:
            images_primary = images_primary.to(DEVICE)
            images_context = images_context.to(DEVICE)
            labels = labels.to(DEVICE)
            
            optimizer.zero_grad()
            # 🧠 Pass both views into our fusion network
            outputs = model(images_primary, images_context)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_train_loss += loss.item() * images_primary.size(0)
            train_progress.set_postfix(batch_loss=f"{loss.item():.4f}")
            
        epoch_train_loss = running_train_loss / len(train_loader.dataset)
        
        # ─── VALIDATION PASS ────────────────────────────────────────────────
        model.eval()
        running_val_loss = 0.0
        all_val_labels = []
        all_val_preds = []
        
        val_progress = tqdm(val_loader, desc=f"Epoch {epoch+1}/{config['epochs']} [Val]", leave=True)
        with torch.no_grad():
            for images_primary, images_context, labels in val_progress:
                images_primary = images_primary.to(DEVICE)
                images_context = images_context.to(DEVICE)
                labels = labels.to(DEVICE)
                
                # 🧠 Pass both views into our fusion network
                outputs = model(images_primary, images_context)
                loss = criterion(outputs, labels)
                running_val_loss += loss.item() * images_primary.size(0)
                
                probs = torch.sigmoid(outputs)
                all_val_labels.append(labels.cpu().numpy())
                all_val_preds.append(probs.cpu().numpy())
                
        epoch_val_loss = running_val_loss / len(val_loader.dataset)
        
        all_val_labels = np.vstack(all_val_labels)
        all_val_preds = np.vstack(all_val_preds)
        
        try:
            epoch_macro_auc = roc_auc_score(all_val_labels, all_val_preds, average="macro")
        except ValueError:
            epoch_macro_auc = 0.5

        print(f"\n🎉 Epoch {epoch+1} Complete!")
        print(f"Train Loss: {epoch_train_loss:.4f} | Val Loss: {epoch_val_loss:.4f} | Macro AUC: {epoch_macro_auc:.4f}\n")
        
        wandb.log({
            "epoch": epoch + 1,
            "train_loss": epoch_train_loss,
            "val_loss": epoch_val_loss,
            "val_macro_auc": epoch_macro_auc
        })

    wandb.finish()