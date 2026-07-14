# CohortProcessor Implementation Summary

## ✅ What Was Created

### 1. **Main Class: `CohortProcessor`** (`modelling/cohort_processor.py`)
A comprehensive end-to-end processing pipeline with two main components:

#### General Processing
- ✅ **Data Balancing**: Undersample/oversample to balance class distribution
- ✅ **Missing Value Handling**: Fill labels with 0, numeric risk features with median
- ✅ **Stratified Train/Val/Test Split**: 70/15/15 (or custom ratios)
- ✅ **DICOM File Location**: Automatic mapping of case IDs to DICOM files

#### Image-Specific Processing (MONAI)
- ✅ **Load & Parse**: DICOM file loading with `LoadImage`
- ✅ **Normalization**: Intensity normalization to [-1, 1] range
- ✅ **Resizing**: Configurable (default 512×512)
- ✅ **Augmentation** (training only):
  - Random rotations (90°)
  - Random flips (horizontal/vertical)
  - Affine transforms (rotation, translation, scaling)
  - Gaussian noise & smoothing
- ✅ **DataLoaders**: Multi-worker GPU-optimized loading with batching

### 2. **Supporting Dataset Class: `MedicalImagingDataset`**
PyTorch Dataset wrapper that:
- Loads individual DICOM images
- Applies MONAI transforms
- Returns multi-label binary vectors
- Preserves metadata (case ID, file path)

### 3. **Documentation**
- `SETUP_MONAI.md`: Complete installation & configuration guide
- `modelling/QUICK_START.py`: Runnable examples with explanations
- Inline code docstrings for all classes/methods

---

## 📋 Installation (Quick Reference)

```bash
# Activate your virtual environment
source venv/bin/activate

# Install MONAI (if not already installed)
pip install monai

# Update requirements
pip freeze > requirements.txt
```

**Note**: MONAI is already in your requirements.txt, along with torch and other dependencies.

---

## 🚀 Quick Usage

```python
from modelling.cohort_processor import CohortProcessor

# Initialize
processor = CohortProcessor(
    ct_cohort_path="data/cohort_ct.csv",
    cxr_cohort_path="data/cohort_cxr.csv",
    dicom_dir="dicom_data/",
    label_map_path="data/label_map.json",
)

# Get ready-to-use dataloaders (one line!)
train_loader, val_loader, test_loader = processor.get_dataloaders(
    modality="CT",
    batch_size=32,
    image_size=(512, 512),
    num_workers=4,
    augment=True,
    balance=True,
)

# Use in training loop
for batch in train_loader:
    images = batch["image"]     # Shape: (32, 1, 512, 512)
    labels = batch["labels"]    # Shape: (32, 10) - multi-label binary
    metadata = batch["metadata"]  # Case IDs, file paths
    
    # outputs = model(images)
    # loss = criterion(outputs, labels)
```

---

## 🔧 Key Features

### Processing Pipeline

```
Raw Cohort CSV
    ↓
Locate DICOM Files (case_id → .dcm path)
    ↓
Fill Missing Values (labels→0, numeric→median)
    ↓
Balance Classes (undersample/oversample)
    ↓
Stratified Train/Val/Test Split
    ↓
Create MONAI Datasets
    ↓
Wrap in PyTorch DataLoaders
```

### Batch Output Structure

```python
batch = {
    "image": torch.Tensor,      # (batch_size, 1, H, W) - normalized [-1, 1]
    "labels": torch.Tensor,     # (batch_size, 10) - binary multi-label
    "metadata": [
        {
            "image_path": "/path/to/image.dcm",
            "case_id": "10000364-1166858",
        },
        ...
    ]
}
```

### Label Columns (10 diseases)
From `build_final_cohort.py`:
```python
imaging_labels = [
    "covid", "pneumonia", "effusion", "atelectasis", "fibrosis",
    "emphysema", "pneumothorax", "pulm_embolism", "ards", "pulm_edema"
]
```
Plus `"normal"` (when no labels are set)

---

## ⚙️ Customization

### Custom Image Size
```python
train_loader, val_loader, test_loader = processor.get_dataloaders(
    image_size=(256, 256),  # Faster, smaller memory
)
```

### Disable Augmentation (for validation/testing)
```python
# Already automatic - val/test never use augmentation
```

### Custom Transform Pipeline
```python
from monai.transforms import Compose, LoadImage

custom_transforms = Compose([
    LoadImage(image_only=True),
    # Add your transforms...
])

dataset = MedicalImagingDataset(
    df=df_train,
    label_cols=label_cols,
    transforms=custom_transforms,
)
```

### Manual Processing (if you need intermediate access)
```python
# Process cohort separately
splits = processor.process(modality="CT", balance=True)
df_train = splits["train_df"]

# Do something with DataFrame...
df_train.to_csv("my_train.csv")

# Then create dataloaders manually
```

---

## 📊 Processing Steps Explained

### 1. **Locate DICOM Files**
Maps case IDs from CSV to actual .dcm files in `dicom_data/`
- If file not found: row is skipped
- Returns: DataFrame with new `image_path` column

### 2. **Fill Missing Values**
- **Labels**: Fill NaN with 0 (assumes no annotation = negative)
- **Numeric Risk Features**: Fill with column median
- Prints progress for each column

### 3. **Balance Classes**
- Computes label distribution before/after
- Options:
  - `undersample`: Randomly remove majority samples
  - `oversample`: Duplicate minority samples
- Prints counts and percentages

### 4. **Train/Val/Test Split**
- Stratified on `covid` status (or `risk_tier` if unavailable)
- Default: 70/15/15
- Ensures similar label distribution across splits

### 5. **MONAI Transforms**
**Training data:**
- Load → Resize → Normalize → Augment → Tensor

**Val/Test data:**
- Load → Resize → Normalize → Tensor (no augmentation)

---

## 🎯 Best Practices

### Memory Usage
```python
# If you get CUDA out of memory:
# 1. Reduce batch size
batch_size=8  # instead of 32

# 2. Reduce image size
image_size=(256, 256)  # instead of 512

# 3. Reduce num_workers
num_workers=2  # instead of 4
```

### Data Loading Speed
```python
# Check if bottleneck:
# 1. Increase num_workers
num_workers=8

# 2. Pin memory to GPU
# Already enabled in DataLoader

# 3. Prefetch batches
# Already optimized in DataLoader
```

### Reproducibility
```python
# Set random_state for consistent splits
processor = CohortProcessor(
    ...,
    random_state=42,
)

# Also set PyTorch seeds in your training script:
import torch
torch.manual_seed(42)
```

---

## 📁 File Locations

```
LT_project/
├── modelling/
│   ├── cohort_processor.py       ← Main class (you are here)
│   ├── QUICK_START.py            ← Runnable examples
│   └── main.py                   ← Your training script (integrate here)
├── SETUP_MONAI.md                ← Installation guide
├── data/
│   ├── cohort_ct.csv             ← Input (from build_final_cohort.py)
│   ├── cohort_cxr.csv            ← Input (from build_final_cohort.py)
│   ├── label_map.json            ← Input (from build_final_cohort.py)
│   └── [exported train/val/test]  ← Optional output
├── dicom_data/
│   ├── case_id_1/
│   │   ├── IM_*.dcm
│   │   └── ...
│   └── ...
└── requirements.txt              ← Updated with monai/sklearn
```

---

## 🔗 Integration with Training

```python
# modelling/main.py
import torch
import torch.nn as nn
from cohort_processor import CohortProcessor

# Setup
processor = CohortProcessor(...)
train_loader, val_loader, test_loader = processor.get_dataloaders(
    modality="CT",
    batch_size=32,
)

# Model
model = YourModel(num_labels=10)
criterion = nn.BCEWithLogitsLoss()
optimizer = torch.optim.Adam(model.parameters())

# Training loop
for epoch in range(num_epochs):
    for batch in train_loader:
        images = batch["image"]
        labels = batch["labels"]
        
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
    
    # Validation
    with torch.no_grad():
        for batch in val_loader:
            images = batch["image"]
            labels = batch["labels"]
            outputs = model(images)
            # Compute metrics...
```

---

## ❓ FAQ

**Q: How do I use CXR instead of CT?**
```python
train_loader, val_loader, test_loader = processor.get_dataloaders(
    modality="CXR",  # Change this
    ...
)
```

**Q: Can I use both CT and CXR together?**
Not currently in this version. You'd need to:
1. Create separate loaders for CT and CXR
2. Implement custom batch sampler to interleave them
3. Track modality in batch metadata

**Q: What's the difference between training and validation?**
- **Training**: Augmentation ON, shuffle ON
- **Validation/Test**: Augmentation OFF, shuffle OFF

This is automatic in the processor.

**Q: Can I apply custom preprocessing to DICOM files?**
Yes! Modify `_create_transforms()` method or pass custom transforms to `MedicalImagingDataset`.

**Q: What format should my model output be?**
For multi-label classification:
- **Input**: (batch, 1, H, W) grayscale
- **Output**: (batch, 10) logits
- **Loss**: `nn.BCEWithLogitsLoss()` or sigmoid + BCELoss

---

## 📚 References

- [MONAI Documentation](https://docs.monai.io/)
- [PyTorch DataLoader](https://pytorch.org/docs/stable/data.html)
- [Medical Imaging Transforms](https://docs.monai.io/en/latest/transforms.html)
- [Multi-Label Classification](https://pytorch.org/docs/stable/generated/torch.nn.BCEWithLogitsLoss.html)

---

## 🎓 Next Steps

1. **Verify Installation**: Run `python -c "import monai; print(monai.__version__)"`
2. **Try Quick Start**: `python modelling/QUICK_START.py`
3. **Integrate with Training**: Import in `modelling/main.py`
4. **Fine-tune Parameters**: Adjust batch_size, image_size, augmentation as needed

Happy training! 🚀
