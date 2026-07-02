# MONAI Installation & Setup Guide

## 1. Install MONAI

### Option A: Using pip (recommended)
```bash
pip install monai torch torchvision torchaudio
```

### Option B: With GPU support (CUDA)
```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Then install MONAI
pip install monai
```

### Option C: With all optional dependencies
```bash
pip install "monai[all]"
```

## 2. Verify Installation

```bash
python -c "import monai; print(monai.__version__)"
```

Expected output:
```
1.3.0  (or latest version)
```

## 3. Within Your Virtual Environment

Since you're already in your virtual environment:

```bash
# Activate venv if not already active
source venv/bin/activate

# Install MONAI + dependencies
pip install monai torch scikit-learn pandas numpy

# Verify
python -c "import monai; import torch; print(f'PyTorch: {torch.__version__}'); print(f'MONAI: {monai.__version__}')"
```

## 4. Update requirements.txt

Add MONAI to your project requirements:

```bash
pip freeze > requirements.txt
```

Or manually add to `requirements.txt`:
```
monai>=1.3.0
torch>=2.0.0
torchvision>=0.15.0
scikit-learn>=1.3.0
pandas>=1.5.0
numpy>=1.24.0
```

## 5. Using the CohortProcessor

### Basic Usage:

```python
from modelling.cohort_processor import CohortProcessor

# Initialize processor
processor = CohortProcessor(
    ct_cohort_path="data/cohort_ct.csv",
    cxr_cohort_path="data/cohort_cxr.csv",
    dicom_dir="dicom_data/",
    label_map_path="data/label_map.json"
)

# Get dataloaders (all preprocessing handled automatically)
train_loader, val_loader, test_loader = processor.get_dataloaders(
    modality="CT",
    batch_size=32,
    image_size=(512, 512),
    num_workers=4,
    augment=True,
    balance=True
)

# Iterate through training batches
for batch in train_loader:
    images = batch["image"]  # Shape: (batch_size, channels, H, W)
    labels = batch["labels"]  # Shape: (batch_size, num_labels)
    metadata = batch["metadata"]
    
    # Pass to your model
    # outputs = model(images)
```

## 6. Key Features of CohortProcessor

### General Processing
- ✅ **Data Balancing**: Undersample/oversample to balance class distribution
- ✅ **Missing Value Handling**: Fill labels with 0, risk features with median
- ✅ **Stratified Splits**: Train/Val/Test split with stratification on COVID status

### Image-Specific (MONAI) Processing

#### Preprocessing Transforms:
- `LoadImage`: Load DICOM files
- `EnsureChannelFirst`: Convert to (C, H, W) format
- `Resize`: Resample to target size (default: 512×512)
- `NormalizeIntensity`: Normalize to [-1, 1] range

#### Data Augmentation (Training only):
- `RandRotate90`: Random 90° rotations
- `RandFlip`: Random flipping on axes
- `RandAffine`: Affine transformations (rotation, translation, scaling)
- `RandGaussianNoise`: Add Gaussian noise
- `RandGaussianSmooth`: Smooth images with Gaussian kernel

#### DataLoader Features:
- Multi-worker loading (configurable)
- Automatic batching with MONAI collate
- GPU-pinned memory for faster transfer
- Metadata preservation (file paths, case IDs)

## 7. Advanced Configuration

### Custom Transforms
```python
from monai.transforms import Compose, LoadImage, EnsureChannelFirst

custom_transforms = Compose([
    LoadImage(image_only=True),
    EnsureChannelFirst(),
    # Add your custom transforms here
])

# Pass to dataset creation
dataset = MedicalImagingDataset(
    df=train_df,
    label_cols=label_cols,
    transforms=custom_transforms
)
```

### Different Image Sizes
```python
train_loader, val_loader, test_loader = processor.get_dataloaders(
    modality="CT",
    batch_size=16,
    image_size=(256, 256),  # Smaller for faster iteration
    num_workers=8,
    augment=True
)
```

### Disable Augmentation for Validation/Testing
```python
# Already handled automatically in processor
# Validation/test use base transforms only (no augmentation)
```

## 8. Common Issues

### Issue: "ModuleNotFoundError: No module named 'monai'"
**Solution**: Ensure pip installed MONAI in your active virtual environment
```bash
pip install monai
```

### Issue: CUDA out of memory
**Solution**: Reduce batch size or image size
```python
train_loader, val_loader, test_loader = processor.get_dataloaders(
    batch_size=8,      # Reduced from 32
    image_size=(256, 256),  # Reduced from 512
)
```

### Issue: DICOM files not found
**Solution**: Check file structure and paths in CohortProcessor
```python
# Verify DICOM directory structure:
# dicom_data/
#   ├── case_id_1/
#   │   ├── IM_*.dcm
#   │   └── ...
#   ├── case_id_2/
#   │   └── ...
```

## 9. Performance Optimization

### For Large Datasets:
```python
train_loader, val_loader, test_loader = processor.get_dataloaders(
    batch_size=64,      # Increase if GPU memory allows
    num_workers=8,      # Increase for parallel loading
    augment=True,
)
```

### For Development/Debugging:
```python
train_loader, val_loader, test_loader = processor.get_dataloaders(
    batch_size=4,       # Small for quick iteration
    num_workers=0,      # Disable parallel for debugging
    augment=False,      # Disable for reproducibility
)
```

## 10. Next Steps

1. **Download DICOM data** (if not already done):
   ```bash
   python exploration/data_download.py
   ```

2. **Run cohort processor**:
   ```bash
   cd modelling
   python cohort_processor.py
   ```

3. **Integrate with your training script**:
   ```python
   from cohort_processor import CohortProcessor
   # Use as shown in "Basic Usage" above
   ```

## References

- [MONAI Documentation](https://docs.monai.io/)
- [PyTorch DataLoader](https://pytorch.org/docs/stable/data.html)
- [Medical Imaging Transforms](https://docs.monai.io/en/latest/transforms.html)
