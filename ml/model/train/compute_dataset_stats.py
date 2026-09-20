#!/usr/bin/env python3
"""
Compute dataset-specific pixel mean and standard deviation for normalization.
Iterates through all training images in a memory-efficient way and outputs
the per-channel statistics needed for transforms.Normalize().

IMPORTANT: mirrors the exact preprocessing of train.py (ResizeLongest +
SquarePad) so the stats match what the model actually sees at train time,
and so equal-sized batches stack correctly despite mixed source resolutions.

One file is reused for all backbones: the statistics depend very weakly on
the target size (SquarePad's black fill is scale-invariant and resize only
changes interpolation), so there is no need to recompute per architecture.
The resolution defaults to the selected model's INPUT_SIZE so the numbers come
out at the same geometry that backbone trains at:

Usage (default: convnext -> its INPUT_SIZE of 384; aligned with train.py):
    python ml/model/train/compute_dataset_stats.py

For a Swin-B training run, align the resolution to 224:
    python ml/model/train/compute_dataset_stats.py --model swin
"""

import argparse
import json
import torch
import pandas as pd
from PIL import Image
from torchvision import transforms
from torch.utils.data import DataLoader, Dataset

from models.chest_model import ChestModel
from models.ViT_model import SwinTransformerChestModel

# Same model classes (and default) as train.py, so the stats are automatically
# computed at the geometry of whichever backbone is being trained.
STATS_MODEL_CLASSES = {
    "convnext": ChestModel,
    "swin": SwinTransformerChestModel,
}
DEFAULT_STATS_MODEL = "convnext"  # must mirror train.py's default MODEL_CLASS


def resolve_resolution(model_name: str, resolution: int | None) -> int:
    """Return the stats resolution: explicit --resolution, else the selected
    model's INPUT_SIZE (convnext 384, swin 224)."""
    if resolution is not None:
        return resolution
    return STATS_MODEL_CLASSES[model_name].INPUT_SIZE


class StatsDataset(Dataset):
    """Lightweight dataset that applies the training preprocessing pipeline."""

    def __init__(self, dataframe, resolution: int):
        self.paths = dataframe["img_path"].tolist()
        self.transform = transforms.Compose([
            ResizeLongest(resolution),
            SquarePad(),
            transforms.ToTensor(),  # converts to [0,1] float tensor
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert("RGB")
        return self.transform(img)  # (3, RESOLUTION, RESOLUTION) float in [0, 1]


class ResizeLongest:
    def __init__(self, size):
        self.size = size

    def __call__(self, img):
        w, h = img.size
        scale = self.size / max(w, h)
        new_w, new_h = round(w * scale), round(h * scale)
        return transforms.functional.resize(img, (new_h, new_w))


class SquarePad:
    def __init__(self, fill=0):
        self.fill = fill

    def __call__(self, img):
        w, h = img.size
        if w == h:
            return img
        max_side = max(w, h)
        pad_l = (max_side - w) // 2
        pad_r = max_side - w - pad_l
        pad_t = (max_side - h) // 2
        pad_b = max_side - h - pad_t
        return transforms.functional.pad(
            img, (pad_l, pad_t, pad_r, pad_b), fill=(self.fill, self.fill, self.fill)
        )


def compute_stats(csv_path: str, resolution: int, batch_size: int = 64, num_workers: int = 4):
    df = pd.read_csv(csv_path, low_memory=False)
    dataset = StatsDataset(df, resolution)
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
    parser.add_argument("--output", default="ml/model/train/dataset_stats.json")
    parser.add_argument("--model", choices=list(STATS_MODEL_CLASSES),
                        default=DEFAULT_STATS_MODEL,
                        help="Backbone for the stats resolution (default: %(default)s).")
    parser.add_argument("--resolution", type=int, default=None,
                        help="Explicit square size. Default: the selected "
                             "model's INPUT_SIZE (%s), i.e. the geometry that "
                             "backbone trains at."
                             % ", ".join(f"{k}={v.INPUT_SIZE}" for k, v in STATS_MODEL_CLASSES.items()))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=4)
    args = parser.parse_args()

    resolution = resolve_resolution(args.model, args.resolution)
    print(f"Computing stats over images in {args.csv} at {resolution}x{resolution} "
          f"(model: {args.model}) ...")
    mean, std = compute_stats(args.csv, resolution,
                              batch_size=args.batch_size, num_workers=args.num_workers)

    result = {"mean": mean, "std": std}
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Dataset mean: {mean}")
    print(f"Dataset std:  {std}")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
