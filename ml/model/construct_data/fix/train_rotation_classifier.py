#!/usr/bin/env python3
"""
train_rotation_classifier.py
──────────────────────────────────────────────────────────────────────
Trains a small 4-class ResNet-18 classifier that predicts how a chest
X-ray is rotated (0/90/180/270 degrees). The MIDRC PNGs sometimes come
out flipped/sideways with no reliable metadata to fix them, so we learn
to correct them from a clean upright reference dataset.

We synthesize the 4 orientation classes by deterministically rotating a
known-upright dataset (here: the NIH chest X-ray PNGs, which are already
head-up / heart-right). The classifier then learns the anatomical cues
(lungs on top, diaphragm below, cardiac silhouette on the right) that
identify a correct orientation.

Usage:
    python train_rotation_classifier.py \
        --image-dir <path to clean upright PNGs> \
        --out checkpoints/xray_orientation_resnet18.pth \
        --epochs 3
"""

import argparse
import os

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
import torchvision.transforms as T
from torchvision.models import resnet18, ResNet18_Weights


class SyntheticRotationDataset(Dataset):
    """Artificially rotates upright chest X-rays into 4 orientation classes."""

    def __init__(self, image_paths, transform=None):
        self.image_paths = image_paths
        self.transform = transform
        self.angles = [0, 90, 180, 270]  # Classes 0, 1, 2, 3

    def __len__(self):
        return len(self.image_paths) * 4  # 4 rotations per image

    def __getitem__(self, idx):
        img_path = self.image_paths[idx // 4]
        class_id = idx % 4
        angle = self.angles[class_id]

        img = Image.open(img_path).convert("RGB")

        # Deterministic rotation (pillow rotates counter-clockwise)
        if angle != 0:
            img = img.rotate(angle, expand=True)

        if self.transform:
            img = self.transform(img)

        return img, class_id


def collect_images(image_dir, limit=None):
    """Collect all PNG/JPG paths under image_dir (non-recursive)."""
    exts = (".png", ".jpg", ".jpeg", ".PNG", ".JPG")
    paths = [
        os.path.join(image_dir, f)
        for f in sorted(os.listdir(image_dir))
        if f.endswith(exts)
    ]
    if limit is not None:
        paths = paths[:limit]
    if not paths:
        raise SystemExit(f"No images found in {image_dir}")
    return paths


def main():
    p = argparse.ArgumentParser(description="Train a 4-class X-ray rotation classifier.")
    p.add_argument("--image-dir", default="/Users/leoniejunkherr/.cache/kagglehub/"
                                          "datasets/nih-chest-xrays/data/versions/3/images_001/images",
                   help="Folder of clean upright chest X-ray PNGs.")
    p.add_argument("--out", default="checkpoints/xray_orientation_resnet18.pth",
                   help="Where to save the trained weights.")
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--num-images", type=int, default=1000,
                   help="Limit how many upright images to use (each gives 4 samples).")
    p.add_argument("--lr", type=float, default=1e-4)
    args = p.parse_args()

    transform = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    paths = collect_images(args.image_dir, limit=args.num_images)
    print(f"Using {len(paths)} upright images -> {len(paths)*4} orientation samples")

    dataset = SyntheticRotationDataset(paths, transform=transform)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True,
                            num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = resnet18(weights=ResNet18_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, 4)  # 4 orientation classes
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    model.train()
    for epoch in range(args.epochs):
        total_loss, correct, total = 0.0, 0, 0
        for imgs, labels in dataloader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            correct += (outputs.argmax(1) == labels).sum().item()
            total += labels.size(0)
        acc = correct / total * 100
        print(f"Epoch {epoch+1}/{args.epochs} - Loss: {total_loss/len(dataloader):.4f} "
              f"- Acc: {acc:.2f}%")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    torch.save(model.state_dict(), args.out)
    print(f"Model saved as {args.out}")


if __name__ == "__main__":
    main()
