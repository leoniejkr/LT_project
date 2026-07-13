import torch
import numpy as np
import cv2
import matplotlib.pyplot as plt
from PIL import Image
from torchvision import transforms
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image

# 1. Redefine Architecture (Must match your training file perfectly)
import torchvision.models as models
import torch.nn as nn

class DualViewXRayNet(nn.Module):
    def __init__(self, num_classes=15):
        super(DualViewXRayNet, self).__init__()
        self.frontal_backbone = models.resnet50(weights=None) # No default weights needed, we load yours
        self.context_backbone = models.resnet50(weights=None)
        
        self.frontal_features = nn.Sequential(*list(self.frontal_backbone.children())[:-1])
        self.context_features = nn.Sequential(*list(self.context_backbone.children())[:-1])
        self.classifier = nn.Linear(2048 + 2048, num_classes)
        
    def forward(self, img_front, img_context):
        feat_front = self.frontal_features(img_front).squeeze(-1).squeeze(-1)
        feat_context = self.context_features(img_context).squeeze(-1).squeeze(-1)
        combined_features = torch.cat((feat_front, feat_context), dim=1)
        return self.classifier(combined_features)

# 2. Load the Weights
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = DualViewXRayNet(num_classes=15)

# REPLACE THIS PATH with the actual path to your checkpoint file
CHECKPOINT_PATH = "dual_view_checkpoint.pth"  # Ensure this path points to your trained model checkpoint

try:
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE))
    print("Successfully loaded model checkpoints!")
except FileNotFoundError:
    print(f"Could not find checkpoint at {CHECKPOINT_PATH}. Please verify the folder structure.")
    exit()

model.to(DEVICE)
model.eval()

# 3. Setup Target Layer for Grad-CAM (The last conv block of ResNet50 layer4)
# In standard ResNet50, layer4 is children item 7
target_layers = [model.frontal_features[7][-1]]

# 4. Prepare a Covid Sample Image
# Replace these paths with a real validation image from your Covid set
CONTEXT_IMG_PATH = "data_hybrid/midrc_images/dg.MD1R_0aa45189-9516-4798-88ed-b630af993b70.png" 
PRIMARY_IMG_PATH = "data_hybrid/midrc_images/dg.MD1R_0aa45189-9516-4798-88ed-b630af993b70.png" 

# Image preprocessing matching validation transforms
preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

# Load raw image for visualization later
rgb_img = Image.open(PRIMARY_IMG_PATH).convert('RGB').resize((224, 224))
rgb_img_np = np.float32(rgb_img) / 255.0

# Prepare tensors
tensor_primary = preprocess(Image.open(PRIMARY_IMG_PATH).convert('RGB')).unsqueeze(0).to(DEVICE)
tensor_context = preprocess(Image.open(CONTEXT_IMG_PATH).convert('RGB')).unsqueeze(0).to(DEVICE)

# Apply normalization only for model forward passes
input_tensor_primary = normalize(tensor_primary.squeeze(0)).unsqueeze(0)
input_tensor_context = normalize(tensor_context.squeeze(0)).unsqueeze(0)

# 5. Define Custom Forward Wrapper for Wrapper-agnostic GradCAM
# Since Grad-CAM package expects single-tensor input, we wrap our multi-input step:
class MultiInputWrapper(nn.Module):
    def __init__(self, base_model, context_tensor):
        super().__init__()
        self.base_model = base_model
        self.context_tensor = context_tensor
    def forward(self, img_front):
        return self.base_model(img_front, self.context_tensor)

wrapped_model = MultiInputWrapper(model, input_tensor_context)

# 6. Generate Heatmap
# Covid index is 14 based on your ALL_CLASSES array index
COVID_CLASS_INDEX = 14 
targets = [ClassifierOutputTarget(COVID_CLASS_INDEX)]

with GradCAM(model=wrapped_model, target_layers=target_layers) as cam:
    grayscale_cam = cam(input_tensor=input_tensor_primary, targets=targets)[0, :]
    visualization = show_cam_on_image(rgb_img_np, grayscale_cam, use_rgb=True)

# 7. Render and Analyze Results
plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.title("Original X-Ray")
plt.imshow(rgb_img)
plt.axis('off')

plt.subplot(1, 2, 2)
plt.title("Grad-CAM (Covid Target)")
plt.imshow(visualization)
plt.axis('off')

plt.tight_layout()
plt.savefig("covid_shortcut_diagnostic.png")
plt.show()