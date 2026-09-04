#!/usr/bin/env python3
"""
Compute dataset-specific pixel mean and standard deviation for normalization.
Iterates through all training images in a memory-efficient way and outputs
the per-channel statistics needed for transforms.Normalize().

Usage:
    python src/model/train/compute_dataset_stats.py \
        --csv data_hybrid/combined_master.csv \
        --output src/model/train/dataset_stats.json
"""

import argparse
import json
import torch
import pandas as pd
from PIL import Image
from torchvision import transforms
from torch.utils.data import DataLoader, Dataset


class StatsDataset(Dataset):
    """Lightweight dataset that loads images as RGB tensors for stat computation."""

    def __init__(self, dataframe):
        self.paths = dataframe["img_path"].tolist()
        self.to_tensor = transforms.ToTensor()  # converts to [0,1] float tensor

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert("RGB")
        return self.to_tensor(img)  # (3, H, W) float in [0, 1]


def compute_stats(csv_path: str, batch_size: int = 64, num_workers: int = 4):
    df = pd.read_csv(csv_path, low_memory=False)
    dataset = StatsDataset(df)
    loader = DataLoader(dataset, batch_size=batch_size, num_workers=num_workers, shuffle=False)

    # Welford's online algorithm for numerical stability
    n = 0
    mean = torch.zeros(3)
    M2 = torch.zeros(3)

    for batch in loader:
        # batch: (B, 3, H, W) — flatten spatial dims to get per-pixel samples
        b, c, h, w = batch.shape
        pixels = batch.permute(0, 2, 3, 1).reshape(-1, 3)  # (B*H*W, 3)

        batch_n = pixels.shape[0]
        batch_mean = pixels.mean(dim=0)
        batch_var = pixels.var(dim=0, unbiased=False)

        # Parallel Welford merge
        total_n = n + batch_n
        delta = batch_mean - mean
        mean = mean + delta * batch_n / total_n
        M2 = M2 + batch_var * batch_n + delta ** 2 * n * batch_n / total_n
        n = total_n

    std = torch.sqrt(M2 / n)
    return mean.tolist(), std.tolist()


def main():
    parser = argparse.ArgumentParser(description="Compute dataset mean/std for normalization")
    parser.add_argument("--csv", default="data_hybrid/combined_master.csv")
    parser.add_argument("--output", default="src/model/train/dataset_stats.json")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=4)
    args = parser.parse_args()

    print(f"Computing stats over images in {args.csv} ...")
    mean, std = compute_stats(args.csv, batch_size=args.batch_size, num_workers=args.num_workers)

    result = {"mean": mean, "std": std}
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Dataset mean: {mean}")
    print(f"Dataset std:  {std}")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
