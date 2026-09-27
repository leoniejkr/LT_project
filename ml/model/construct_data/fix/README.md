# MIDRC Orientation & Size Fix

Rectifies the orientation of the MIDRC COVID-19 X-rays and downscales them, so
they can be blended with NIH into one consistent training set.

## Why this was needed

- **NIH (reference):** the ChestX-ray14 images are upright, frontal and
  consistently oriented — lungs on top, diaphragm below, cardiac silhouette on
  the patient's right.
- **MIDRC (problem):** the COVID-19 images were contributed from many different
  sources and arrive rotated by 0/90/180/270 degrees, with no metadata that
  reliably says which way is up.

To blend the two sources they have to share the same orientation, so the
correction runs first: [`blend_data.py`](../blend_data.py) only
accepts MIDRC rows that have an orientation-fixed copy, and aborts if none do.

## Approach: learn the orientation from the clean dataset

No orientation labels exist for MIDRC, so instead of annotating thousands of
images by hand we derive a classifier from the upright NIH reference:

1. **Train on synthetic rotations** —
   [`train_rotation_classifier.py`](train_rotation_classifier.py) takes upright
   NIH PNGs and rotates each one to 0/90/180/270 degrees, which *are* the labels
   (4 samples per image; 1,000 images → 4,000 samples by default). The model is
   a 4-class ResNet-18 (ImageNet weights, 224×224, Adam `1e-4`,
   cross-entropy), so it learns the anatomical cues that identify a correct
   orientation: lungs on top, diaphragm below, heart on the right.
   Output: `checkpoints/xray_orientation_resnet18.pth`.
2. **Predict and correct** —
   [`fix_midrc_orientation.py`](fix_midrc_orientation.py) runs that classifier
   over every MIDRC PNG and rotates each image back into the upright reference
   pose, then prints how many images were found in each orientation:

   | Class | Predicted orientation | Correction applied (Pillow, counter-clockwise) |
   |-------|----------------------|----------------------------------------------|
   | 0 | upright | none |
   | 1 | rotated 90° CCW | rotate 270° |
   | 2 | upside down | rotate 180° |
   | 3 | rotated 270° CCW | rotate 90° |

3. **Downscale for training** — [`resize_midrc.py`](resize_midrc.py)
   turns the fixed images into `data_hybrid/midrc_fixed_1024/`, which is the only
   MIDRC directory the training DataLoader reads.

[`turn_midrc_images.py`](turn_midrc_images.py) is the manual fallback: it rotates
a whole folder by one fixed angle (currently 270°) without classifying anything,
useful for inspecting a directory or applying a known global offset.

## Usage

```bash
# 1. train the orientation classifier on synthetic rotations of upright NIH images
python ml/model/construct_data/fix/train_rotation_classifier.py \
    --image-dir <path to upright NIH PNGs> \
    --out checkpoints/xray_orientation_resnet18.pth

# 2. predict + correct the orientation of the MIDRC images
python ml/model/construct_data/fix/fix_midrc_orientation.py \
    --input-dir data_hybrid/midrc_images \
    --output-dir data_hybrid/midrc_fixed_images \
    --model checkpoints/xray_orientation_resnet18.pth
```

The correction script classifies at 224×224 with ImageNet mean/std (a plain
squashing resize is fine for classification) and runs on CPU or CUDA.
