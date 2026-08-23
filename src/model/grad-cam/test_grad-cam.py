import os
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
from model.train.models.multilabel_models import MultiLabelChestModel



# 2. Initialization and Loading Weights
DEVICE = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
model = MultiLabelChestModel(num_classes=15)

# Update to wherever your new single-view checkpoint is saved
CHECKPOINT_PATH = "dual_view_checkpoint.pth" 
checkpoint = torch.load(CHECKPOINT_PATH)
# If checkpoint is a dict containing 'state_dict', extract it:
state_dict = checkpoint.get("state_dict", checkpoint)
model.load_state_dict(state_dict, strict=False)

model.to(DEVICE)
model.eval()

# 3. Target Layers for DenseNet121
# In torchvision's DenseNet121, the feature extractor's final layer is model.backbone.features
target_layers = [model.backbone.features]

# 4. Target Sample Path (No more Context image path!)
PRIMARY_IMG_PATH = "data_hybrid/midrc_images/dg.MD1R_0aa45189-9516-4798-88ed-b630af993b70.png" 

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

# 5. Generate Heatmap
# Covid index is 14 based on your ALL_CLASSES array index
COVID_CLASS_INDEX = 14 
targets = [ClassifierOutputTarget(COVID_CLASS_INDEX)]

# NO wrapper model class needed! We pass the raw model straight into GradCAM
with GradCAM(model=model, target_layers=target_layers) as cam:
    grayscale_cam = cam(input_tensor=input_tensor, targets=targets)[0, :]
    visualization = show_cam_on_image(rgb_img_np, grayscale_cam, use_rgb=True)

# 6. Render and Analyze Results
plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.title("Original Chest X-Ray")
plt.imshow(pil_img.resize((224, 224)))
plt.axis('off')

plt.subplot(1, 2, 2)
plt.title("Grad-CAM (Covid Target)")
plt.imshow(visualization)
plt.axis('off')

plt.tight_layout()

# Save the dashboard safely with auto-incrementing naming logic 
folder_path = "src/grad-cam/test_images"
file_base = "covid_gradcam_dashboard"
extension = ".png"
os.makedirs(folder_path, exist_ok=True)

i = 1
save_path = os.path.join(folder_path, f"{file_base}_{i}{extension}")
while os.path.exists(save_path):
    i += 1
    save_path = os.path.join(folder_path, f"{file_base}_{i}{extension}")

plt.savefig(save_path, bbox_inches='tight', dpi=150)
print(f"Grad-CAM dashboard saved successfully to: {save_path}")
plt.show()