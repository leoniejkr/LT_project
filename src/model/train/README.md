# Training Pipeline — Image Preprocessing

This document explains how images are loaded, resized and normalized before
they enter the model, and why.

## Source image characteristics

The hybrid dataset mixes two sources with very different image geometries:

| Source       | Resolution                  | Orientation |
|--------------|-----------------------------|-------------|
| NIH          | 1024 x 1024 (always square) | standardized |
| MIDRC (fixed)| 80+ distinct sizes, e.g. 2800x3408, 3032x2520, 4400x3610 | standardized after `fix_midrc_orientation.py` |

MIDRC PNGs are far from square and vary heavily. NIH images happen to be
square, but the pipeline below does **not** assume that — it works for any
aspect ratio, so nothing ever gets distorted.

## The augmentation pipeline (`train.py`)

Every image passes through this chain:

```
ResizeLongest(384)  ->  SquarePad(fill=0)  ->  [train only: flips/rotation/affine]  ->  ToTensor  ->  Normalize
```

### 1. `ResizeLongest(384)` — aspect-preserving downscale

Scales the image so its **longer side** becomes exactly 384 px; the shorter
side follows to preserve the true aspect ratio.

- Example: `2800x3408` -> `~315x384`, `3032x2520` -> `384x~318`,
  `1024x1024` -> `384x384`.
- **Why not `Resize((384, 384))`?** Squashing distorts anatomy — e.g. the
  cardiothoracic ratio changes — which actively hurts classes that depend on
  shape (Cardiomegaly, Cardiothoracic ratios) and warps fine structure.
- **Why fix the longer side?** It guarantees the output is *at most* 384 on
  both sides and that, after padding, **every** output is exactly
  `384 x 384`. Fixing the shorter side instead would leave square outputs of
  varying size (384x467 etc.), which breaks batching.

### 2. `SquarePad(fill=0)` — black border to square

Pads the shorter side symmetrically with black (pixel value 0) so the image
becomes a square.

- **Why black?** Air outside the body is black on a radiograph, so a black
  border is anatomically consistent, and it matches the `fill=0` already used
  by the random-rotation/affine augmentations. A bright or mid-grey border
  would look like tissue and create a visible seam.
- This makes MIDRC portrait/landscape images uniform without any stretching.

### 3. Train-only spatial augmentation

`RandomHorizontalFlip`, `RandomRotation(5, fill=0)`, `RandomAffine(...)` run
on the already-square image. `fill=0` keeps the same black border semantics.

### 4. `ToTensor` + `Normalize`

Converts to a `(3, RESOLUTION, RESOLUTION)` float tensor in `[0, 1]`, then
normalizes with the dataset mean/std from `dataset_stats.json` (computed by
`compute_dataset_stats.py`). Black border pixels become `-mean/std` after
normalization — a constant, standard value the network learns to ignore.

## Why 384 instead of 1024?

Config: `train.py` -> `config["resolution"] = None`, resolved from the selected
model's `INPUT_SIZE` (default `ChestModel` -> 384).

- The default model is `ConvNeXt-Base`, which is fully convolutional and accepts
  any input size. 384 exceeds the ~224 px ImageNet default and is a common
  "high-res" setting. Upscaling to 1024 would hand the backbone ~7x the pixels
  of 384^2, but the backbone was not tuned for that, so the extra detail mostly
  increases compute without a proportional performance gain.
- Cost: a 1024^2 input is ~7x more pixels than 384^2. With batch size 32 and
  ~95k training images on CPU/MPS, that scales runtime and memory roughly 7x.
- Use 512 or 640 as a middle ground if more detail is needed; 1024 is not
  worth it for this backbone.

### Resolution is model-specific

Different backbones have different resolution constraints, so the training
resolution is declared **on the model class**, not hardcoded:

| Model | `INPUT_SIZE` | `BATCH_SIZE` | Why |
|-------|--------------|--------------|-----|
| `ChestModel` (ConvNeXt-Base) | 384 | 32 | Fully convolutional — any size works; 384 balances detail vs cost |
| `SwinTransformerChestModel` (Swin-B) | 224 | 24 | Swin accepts other sizes (relative-position bias is interpolated), but ImageNet-1K weights were tuned at 224; default keeps the pretrained bias intact |

To train a different model, change `MODEL_CLASS` in `train.py`:

```python
MODEL_CLASS = SwinTransformerChestModel   # -> uses INPUT_SIZE=224, BATCH_SIZE=24
```

The `ResizeLongest`/`SquarePad` transforms are then built from
`MODEL_CLASS.INPUT_SIZE`, so every backbone gets the resolution it was
configured for. `config["batch_size"]`/`config["resolution"]` can override the
model defaults if set to a non-None value.

## Dependencies / flow

- `combined_master.csv` is produced by `src/model/construct_data/blend_data.py`
  (NIH balanced + only orientation-fixed MIDRC images).
- `dataset_stats.json` is produced by `compute_dataset_stats.py`.
- Run stats computation if the dataset changes:
  `python src/model/train/compute_dataset_stats.py --csv data_hybrid/combined_master.csv`