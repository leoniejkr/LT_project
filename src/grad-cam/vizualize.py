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
import os

# 1. Exact Architecture definition
class DualViewXRayNet(nn.Module):
    def __init__(self, num_classes=15):
        super(DualViewXRayNet, self).__init__()
        self.frontal_backbone = models.resnet50(weights=None)
        self.context_backbone = models.resnet50(weights=None)
        
        self.frontal_features = nn.Sequential(*list(self.frontal_backbone.children())[:-1])
        self.context_features = nn.Sequential(*list(self.context_backbone.children())[:-1])
        self.classifier = nn.Linear(2048 + 2048, num_classes)
        
    def forward(self, img_front, img_context):
        feat_front = self.frontal_features(img_front).squeeze(-1).squeeze(-1)
        feat_context = self.context_features(img_context).squeeze(-1).squeeze(-1)
        combined_features = torch.cat((feat_front, feat_context), dim=1)
        return self.classifier(combined_features)

# Your exact 15 classes in structural order
ALL_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'Covid']

# 2. Initialization and Weights Loading
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = DualViewXRayNet(num_classes=15)
CHECKPOINT_PATH = "dual_view_checkpoint.pth"

try:
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE))
    print("Successfully loaded model weights!")
except FileNotFoundError:
    print(f"Weights file not found at {CHECKPOINT_PATH}. Exiting.")
    exit()

model.to(DEVICE)
model.eval()

# Hook into final convolutional layer of both backbones
target_layers_frontal = [model.frontal_features[7][-1]]
target_layers_context = [model.context_features[7][-1]]

# 3. Target Evaluation Sample Paths
PRIMARY_IMG_PATH = "/Users/leoniejunkherr/.cache/kagglehub/datasets/nih-chest-xrays/data/versions/3/images_010/images/00020946_000.png"
CONTEXT_IMG_PATH = "/Users/leoniejunkherr/.cache/kagglehub/datasets/nih-chest-xrays/data/versions/3/images_010/images/00020946_000.png"


preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

# ALWAYS load primary PIL image first
pil_front = Image.open(PRIMARY_IMG_PATH).convert('RGB')
rgb_front_np = np.float32(pil_front.resize((224, 224))) / 255.0

# Process Context conditionally using PIL images
if CONTEXT_IMG_PATH == "":
    # Safe fallback using the native PIL size tuple
    pil_context = Image.new('RGB', pil_front.size, (0, 0, 0))
    print("No context image provided. Created a black placeholder image.")
else:
    pil_context = Image.open(CONTEXT_IMG_PATH).convert('RGB')
    print(f"Successfully loaded context image from: {CONTEXT_IMG_PATH}")

# Create NumPy array for the visualization loop later
rgb_context_np = np.float32(pil_context.resize((224, 224))) / 255.0

# Normalize input tensors
input_tensor_front = normalize(preprocess(pil_front)).unsqueeze(0).to(DEVICE)
input_tensor_context = normalize(preprocess(pil_context)).unsqueeze(0).to(DEVICE)

# 4. Custom Forward Wrappers for Single Stream Extraction
class FrontalCamWrapper(nn.Module):
    def __init__(self, base_model, context_tensor):
        super().__init__()
        self.base_model = base_model
        self.context_tensor = context_tensor
    def forward(self, img_front):
        return self.base_model(img_front, self.context_tensor)

class ContextCamWrapper(nn.Module):
    def __init__(self, base_model, front_tensor):
        super().__init__()
        self.base_model = base_model
        self.front_tensor = front_tensor
    def forward(self, img_context):
        return self.base_model(self.front_tensor, img_context)

wrapped_frontal_model = FrontalCamWrapper(model, input_tensor_context)
wrapped_context_model = ContextCamWrapper(model, input_tensor_front)

# 5. Extract Baseline Model Diagnosis Probabilities
with torch.no_grad():
    raw_outputs = model(input_tensor_front, input_tensor_context)
    probabilities = torch.sigmoid(raw_outputs).squeeze(0).cpu().numpy()

# 6. Build the Grand Layout Grid (15 Rows, 2 Columns)
fig, axes = plt.subplots(15, 2, figsize=(10, 50)) 

print("Generating Grand Sickness Diagnostic Maps...")

for idx, class_name in enumerate(ALL_CLASSES):
    prob_score = probabilities[idx]
    targets = [ClassifierOutputTarget(idx)]
    
    # Executing Frontal Stream CAM
    with GradCAM(model=wrapped_frontal_model, target_layers=target_layers_frontal) as cam_f:
        gray_cam_f = cam_f(input_tensor=input_tensor_front, targets=targets)[0, :]
        vis_front = show_cam_on_image(rgb_front_np, gray_cam_f, use_rgb=True)
        
    # Executing Context Stream CAM
    with GradCAM(model=wrapped_context_model, target_layers=target_layers_context) as cam_c:
        gray_cam_c = cam_c(input_tensor=input_tensor_context, targets=targets)[0, :]
        vis_context = show_cam_on_image(rgb_context_np, gray_cam_c, use_rgb=True)
        
    # Render Frontal Image Axis
    axes[idx, 0].imshow(vis_front)
    axes[idx, 0].set_title(f"Frontal View: {class_name}\nModel Prob: {prob_score:.4f}", fontsize=10)
    axes[idx, 0].axis('off')
    
    # Render Context Image Axis
    axes[idx, 1].imshow(vis_context)
    axes[idx, 1].set_title(f"Context View: {class_name}\nModel Prob: {prob_score:.4f}", fontsize=10)
    axes[idx, 1].axis('off')
    
    print(f" -> Completed evaluation maps for [{class_name}]")

plt.tight_layout()
# Define the base naming template 
folder_path = "src/grad-cam/test_images"
file_base = "all_pathologies_gradcam_dashboard"
extension = ".png"

# Ensure the destination folder exists locally
os.makedirs(folder_path, exist_ok=True)

# Find the next available incremental index number
i = 1
save_path = os.path.join(folder_path, f"{file_base}_{i}{extension}")

while os.path.exists(save_path):
    i += 1
    save_path = os.path.join(folder_path, f"{file_base}_{i}{extension}")

# Save the dashboard securely to the next open filename path
plt.savefig(save_path, bbox_inches='tight', dpi=150)
print(f"Dashboard saved successfully as: {save_path}")
