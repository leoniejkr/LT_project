import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'src.*' imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import torch
import numpy as np
import cv2
import matplotlib.pyplot as plt
from PIL import Image
from torchvision import transforms
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image
import torchvision.models as models
import torch.nn as nn
import pytorch_lightning as pl
from src.train.models.multilabel_models import MultiLabelChestModel

# 1. Classes Setup (15 classes in structural order)
ALL_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'Covid']

# 2. Initialization and Loading Weights
DEVICE = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
model = MultiLabelChestModel(num_classes=15)

# Update to wherever your new single-view checkpoint is saved
CHECKPOINT_PATH = "checkpoints/dual_view_checkpoint.pth" 
checkpoint = torch.load(CHECKPOINT_PATH, map_location=DEVICE)
# If checkpoint is a dict containing 'state_dict', extract it:
state_dict = checkpoint.get("state_dict", checkpoint)
model.load_state_dict(state_dict, strict=False)

model.to(DEVICE)
model.eval()

# 3. Target Layers for DenseNet121
target_layers = [model.backbone.features]

# 4. Target Sample Path
PRIMARY_IMG_PATH = "data_hybrid/midrc_images/dg.MD1R_0a5a69ee-291b-4d7a-83ac-7703356d5669.png" 
#PRIMARY_IMG_PATH = "/Users/leoniejunkherr/.cache/kagglehub/datasets/nih-chest-xrays/data/versions/3/images_001/images/00000092_001.png" 


preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

# Prepare base RGB canvas elements for visualization
pil_img = Image.open(PRIMARY_IMG_PATH).convert('RGB')
rgb_img_np = np.float32(pil_img.resize((224, 224))) / 255.0

# Prepare normalized input tensor
input_tensor = normalize(preprocess(pil_img)).unsqueeze(0).to(DEVICE)

# Extract Model Diagnosis Probabilities
with torch.no_grad():
    raw_outputs = model(input_tensor)
    probabilities = torch.sigmoid(raw_outputs).squeeze(0).cpu().numpy()

# 5. Build the Grand Layout Grid (15 Rows, 2 Columns: Original vs. Grad-CAM)
fig, axes = plt.subplots(15, 2, figsize=(10, 50))

print("Generating Grand Sickness Diagnostic Maps...")

for idx, class_name in enumerate(ALL_CLASSES):
    prob_score = probabilities[idx]
    targets = [ClassifierOutputTarget(idx)]
    
    # Generate Heatmap for current class
    with GradCAM(model=model, target_layers=target_layers) as cam:
        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)[0, :]
        visualization = show_cam_on_image(rgb_img_np, grayscale_cam, use_rgb=True)
        
    # Column 1: Original Image
    axes[idx, 0].imshow(pil_img.resize((224, 224)))
    axes[idx, 0].set_title(f"Original: {class_name}", fontsize=10)
    axes[idx, 0].axis('off')
    
    # Column 2: Grad-CAM Overlay
    axes[idx, 1].imshow(visualization)
    axes[idx, 1].set_title(f"Grad-CAM {class_name}\nProb: {prob_score:.4f}", fontsize=10)
    axes[idx, 1].axis('off')
    
    print(f" -> Completed evaluation maps for [{class_name}]")

plt.tight_layout()

# 6. Save the dashboard safely with auto-incrementing naming logic 
folder_path = "src/grad-cam/test_images"
file_base = "all_pathologies_gradcam_dashboard"
extension = ".png"
os.makedirs(folder_path, exist_ok=True)

i = 1
save_path = os.path.join(folder_path, f"{file_base}_{i}{extension}")
while os.path.exists(save_path):
    i += 1
    save_path = os.path.join(folder_path, f"{file_base}_{i}{extension}")

plt.savefig(save_path, bbox_inches='tight', dpi=150)
print(f"Grand Grad-CAM dashboard saved successfully to: {save_path}")
plt.show()