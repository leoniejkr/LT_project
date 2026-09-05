#!/usr/bin/env python3
"""
fix_midrc_orientation.py
──────────────────────────────────────────────────────────────────────
Predicts the orientation of each MIDRC chest X-ray PNG and rotates it
back to the correct upright position (lungs on top, heart on the right).

Uses `checkpoints/xray_orientation_resnet18.pth`, a 4-class ResNet-18
trained by `train_rotation_classifier.py` on synthetic rotations of the
upright NIH dataset.

Usage:
    python fix_midrc_orientation.py \
        --input-dir  data_hybrid/midrc_images \
        --output-dir data_hybrid/midrc_fixed_images \
        --model checkpoints/xray_orientation_resnet18.pth
"""

import argparse
import os

import torch
import torch.nn as nn
from PIL import Image
from tqdm import tqdm
import torchvision.transforms as T
from torchvision.models import resnet18

# Inverse rotation to bring an image predicted as class k back to 0 degrees.
# Pillow's Image.rotate is counter-clockwise; class k == clockwise rotation k.
INVERSE_ROTATION = {
    0: 0,    # Correct -> nothing
    1: 270,  # Rotated 90° CCW (class 1) -> rotate 270° CCW to fix
    2: 180,  # Upside down -> rotate 180°
    3: 90,   # Rotated 270° CCW (class 3) -> rotate 90° CCW to fix
}


def main():
    p = argparse.ArgumentParser(description="Auto-correct rotated chest X-ray PNGs.")
    p.add_argument("--input-dir", default="data_hybrid/midrc_images")
    p.add_argument("--output-dir", default="data_hybrid/midrc_fixed_images")
    p.add_argument("--model", default="checkpoints/xray_orientation_resnet18.pth")
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = resnet18()
    model.fc = nn.Linear(model.fc.in_features, 4)
    model.load_state_dict(torch.load(args.model, map_location=device))
    model = model.to(device)
    model.eval()

    transform = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    os.makedirs(args.output_dir, exist_ok=True)
    files = [f for f in os.listdir(args.input_dir) if f.endswith((".png", ".jpg", ".jpeg", ".PNG", ".JPG"))]
    if not files:
        print(f"No images found in {args.input_dir}")
        return

    # Count per-class corrections for a summary at the end.
    counts = {0: 0, 1: 0, 2: 0, 3: 0}

    for file_name in tqdm(files, desc="Fixing orientations"):
        img_path = os.path.join(args.input_dir, file_name)
        raw_img = Image.open(img_path).convert("RGB")

        input_tensor = transform(raw_img).unsqueeze(0).to(device)
        with torch.no_grad():
            outputs = model(input_tensor)
            pred_class = torch.argmax(outputs, dim=1).item()
        counts[pred_class] += 1

        correction_angle = INVERSE_ROTATION[pred_class]
        fixed_img = raw_img.rotate(correction_angle, expand=True) if correction_angle else raw_img
        fixed_img.save(os.path.join(args.output_dir, file_name))

    print("Summary of predicted orientations (class: count):")
    for k in sorted(counts):
        name = {0: "upright (0)", 1: "90 CCW", 2: "180", 3: "270 CCW"}[k]
        print(f"  {k} ({name}): {counts[k]}")
    print(f"Fixed images saved to {args.output_dir}")


if __name__ == "__main__":
    main()
