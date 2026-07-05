# MIDRC Multi-Label Chest Disease Classification

**CXR → DenseNet-121** (CheXpert pretrained, 2D)
**CT  → SwinUNETR encoder** (BTCV pretrained, 3D)

Both models share the same Asymmetric Loss + cosine warmup pipeline
via PyTorch Lightning.

---

## Setup

```bash
pip install -r requirements.txt

# gen3-client binary (separate from the Python package)
# Download from: https://github.com/uc-cdis/cdis-data-client/releases
# Add to PATH
```

---

## Step 1 — Download data from MIDRC

Get your credentials JSON from https://data.midrc.org → Profile → "Create API key"

```bash
python modelling/download_data.py \
    --manifest-ct  data/manifest_ct.json \
    --manifest-cxr data/manifest_cxr.json \
    --output-dir   images/ \
    --credentials  credentials.json \
    --workers      8
```

Downloads land in:
```
images/
  ct/<object_id>/<dicom_files>
  cxr/<object_id>/<dicom_files>
```

---

## Step 2 — Preprocess

Converts raw DICOM to model-ready tensors. **Idempotent — safe to rerun.**

```bash
python modelling/preprocess.py \
    --cohort-ct  data/cohort_ct.csv \
    --cohort-cxr data/cohort_cxr.csv \
    --image-root images/ \
    --prep-dir   data/preprocessed/
```

Outputs:
- `data/preprocessed/ct/...`  — 
- `data/preprocessed/cxr/...`     — 
- Updated CSVs with `preprocessed_path` column

---

## Step 3 — Train

```bash
# Both modalities
python modelling/train.py --config configs/config.yaml

# CXR only
python modelling/train.py --config configs/config.yaml --modality cxr

# CT only
python modelling/train.py --config configs/config.yaml --modality ct

# With tabular metadata features fused into classifier head
python modelling/train.py --config configs/config.yaml --use-metadata

# Resume from checkpoint
python modelling/train.py --config configs/config.yaml --modality cxr \
    --resume checkpoints/cxr/cxr_epoch=12-val_mAP=0.710.ckpt
```

Checkpoints saved to `checkpoints/cxr/` and `checkpoints/ct/`.
Tuned per-label thresholds saved to `checkpoints/cxr_thresholds.json` etc.

---

## Key design decisions

### Why DenseNet-121 for CXR?
TorchXRayVision provides weights pretrained on CheXpert (224k+ chest X-rays
across 14 pathologies). Starting from these weights rather than ImageNet cuts
convergence time by ~40% and gives better AUROC on small downstream sets.

### Why SwinUNETR for CT?
MONAI's SwinUNETR was pretrained on 5,000 CT volumes (BTCV segmentation).
Its hierarchical shifted-window attention captures both local texture
(nodule margins, GGO) and global context (bilateral distribution) better
than ResNet3D, and the encoder compresses a 96³ volume to a 768-d vector
efficiently under 16 GB VRAM with gradient checkpointing.

### Why Asymmetric Loss?
Your dataset has severe positive/negative imbalance per label
(e.g. `lung_abscess` ~5% positive). ASL down-weights easy negatives
(γ_neg=4) while leaving positive examples at standard sigmoid loss (γ_pos=0),
which outperforms weighted BCE and focal loss for multi-label at these ratios.

### COVID dominance (84% of CT, 82% of CXR)
This is inherent to MIDRC (a COVID-focused data commons). Two mitigations:
1. The `normal` class (250 balanced samples) provides a hard negative anchor.
2. ASL's negative down-weighting prevents COVID from dominating gradients.
3. Watch per-label AUROC during training — if minority labels (lung_abscess,
   pulm_embolism) flatline, increase their sampling weight in config or add
   label-specific loss weighting.

### Threshold tuning
`tune_thresholds()` runs on the val set after training and finds the
per-label probability threshold that maximises F1. Use these thresholds
at inference rather than a fixed 0.5 for all labels.

---

## Expected rough baselines (val AUROC)

| Label             | CXR (DenseNet) | CT (SwinUNETR) |
|-------------------|---------------|----------------|
| covid             | 0.92–0.96     | 0.94–0.97      |
| bacterial_pneumonia | 0.78–0.85   | 0.80–0.87      |
| pleural_effusion  | 0.88–0.93     | 0.90–0.95      |
| pneumothorax      | 0.90–0.95     | 0.92–0.96      |
| atelectasis       | 0.75–0.82     | 0.77–0.84      |
| pulm_embolism     | 0.65–0.75     | 0.82–0.89      |
| lung_abscess      | 0.70–0.80     | 0.75–0.85      |
| lung_malignancy   | 0.72–0.82     | 0.78–0.88      |

(These are illustrative; actual values depend on split and label noise.)

---

## Directory layout

```
midrc_training/
├── configs/
│   └── config.yaml          ← all hyperparameters here
├── modelling/
│   ├── download_data.py     ← Step 1: Gen3 download
│   ├── preprocess.py        ← Step 2: MONAI preprocessing
│   └── train.py             ← Step 3: training entrypoint
├── src/
│   ├── data/
│   │   └── datasets.py      ← Dataset, DataLoader, stratified split
│   ├── models/
│   │   └── multilabel_models.py  ← DenseNet CXR, SwinUNETR CT, ASL
│   └── training/
│       └── lightning_module.py   ← LightningModule, threshold tuning
├── data/                    ← cohort CSVs, manifests (from dataset builder)
├── images/                  ← Gen3 download target
├── weights/                 ← pretrained weights cache
├── checkpoints/             ← training outputs
└── requirements.txt
```
