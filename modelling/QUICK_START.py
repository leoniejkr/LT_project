"""
Quick Start: Using CohortProcessor
==================================

This script demonstrates how to use the CohortProcessor class
for end-to-end cohort preparation before model training.
"""

from pathlib import Path
from modelling.cohort_processor import CohortProcessor

# ──────────────────────────────────────────────────────────────────────────────
# 1. INITIALIZE PROCESSOR
# ──────────────────────────────────────────────────────────────────────────────

processor = CohortProcessor(
    ct_cohort_path="data/cohort_ct.csv",
    cxr_cohort_path="data/cohort_cxr.csv",
    dicom_dir="dicom_data/",
    label_map_path="data/label_map.json",
    random_state=42,  # For reproducibility
)

print("\n✓ Processor initialized")


# ──────────────────────────────────────────────────────────────────────────────
# 2. GET DATALOADERS (Recommended: One-line approach)
# ──────────────────────────────────────────────────────────────────────────────

train_loader, val_loader, test_loader = processor.get_dataloaders(
    modality="CT",              # or "CXR"
    batch_size=32,
    image_size=(512, 512),      # DICOM resolution
    num_workers=4,              # Parallel data loading
    augment=True,               # Apply augmentation to training data
    balance=True,               # Balance class distribution
    train_size=0.7,             # 70% training
    val_size=0.15,              # 15% validation
    test_size=0.15,             # 15% testing
)

print(f"\n✓ DataLoaders created:")
print(f"  Train: {len(train_loader)} batches")
print(f"  Val:   {len(val_loader)} batches")
print(f"  Test:  {len(test_loader)} batches")


# ──────────────────────────────────────────────────────────────────────────────
# 3. INSPECT A BATCH
# ──────────────────────────────────────────────────────────────────────────────

batch = next(iter(train_loader))

print(f"\n{'='*70}")
print(f"Sample Batch Structure")
print(f"{'='*70}")

print(f"\nImage tensor:")
print(f"  Shape: {batch['image'].shape}")
print(f"    → (batch_size=32, channels=1, height=512, width=512)")
print(f"  Range: [{batch['image'].min():.2f}, {batch['image'].max():.2f}]")

print(f"\nLabel tensor (multi-label binary):")
print(f"  Shape: {batch['labels'].shape}")
print(f"    → (batch_size=32, num_labels=10)")
print(f"  Sample row: {batch['labels'][0]}")
print(f"    → Each position is binary: 0 or 1")

print(f"\nMetadata (for tracking):")
print(f"  Keys: {batch['metadata'][0].keys()}")
print(f"  Sample: {batch['metadata'][0]}")


# ──────────────────────────────────────────────────────────────────────────────
# 4. ITERATE THROUGH TRAINING BATCHES
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print(f"Training Loop Example")
print(f"{'='*70}\n")

for epoch in range(1):  # 1 epoch for demo
    for batch_idx, batch in enumerate(train_loader):
        
        images = batch["image"]     # Shape: (32, 1, 512, 512)
        labels = batch["labels"]    # Shape: (32, 10)
        metadata = batch["metadata"]
        
        # Example: Pass to model
        # outputs = model(images)
        # loss = criterion(outputs, labels)
        # loss.backward()
        # optimizer.step()
        
        if batch_idx == 0:
            print(f"Epoch 0 | Batch {batch_idx}/{len(train_loader)}")
            print(f"  Images: {images.shape}")
            print(f"  Labels: {labels.shape}")
            print(f"  First sample case: {metadata[0]['case_id']}")
            break


# ──────────────────────────────────────────────────────────────────────────────
# 5. VALIDATION/TESTING
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print(f"Validation Loop Example")
print(f"{'='*70}\n")

model_predictions = []

for batch_idx, batch in enumerate(val_loader):
    
    images = batch["image"]
    labels = batch["labels"]
    
    # Example: Model inference
    # with torch.no_grad():
    #     outputs = model(images)
    # model_predictions.append(outputs.cpu().numpy())
    
    if batch_idx == 0:
        print(f"Val Batch {batch_idx}/{len(val_loader)}")
        print(f"  Batch size: {images.shape[0]}")
        print(f"  ✓ Ready for evaluation")
    
    if batch_idx >= 1:  # Demo: just show 2 batches
        break


# ──────────────────────────────────────────────────────────────────────────────
# 6. ALTERNATIVE: MANUAL PROCESSING (if you need more control)
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print(f"Advanced: Manual Processing Pipeline")
print(f"{'='*70}\n")

# Step 1: Process cohort (returns splits as DataFrames)
splits = processor.process(
    modality="CT",
    balance=True,
    balance_strategy="undersample",
    train_size=0.7,
    val_size=0.15,
    test_size=0.15,
)

df_train = splits["train_df"]
df_val = splits["val_df"]
df_test = splits["test_df"]

print(f"\nProcessed splits:")
print(f"  Train: {len(df_train)} samples")
print(f"  Val:   {len(df_val)} samples")
print(f"  Test:  {len(df_test)} samples")

# Step 2: Inspect data
print(f"\nTrain set label distribution:")
label_cols = processor.imaging_labels
for label in label_cols[:3]:  # Show first 3
    count = int(df_train[label].sum())
    pct = 100 * count / len(df_train)
    print(f"  {label}: {count:>3} ({pct:5.1f}%)")

# Step 3: Save processed cohorts (optional)
df_train.to_csv("data/cohort_ct_train.csv", index=False)
df_val.to_csv("data/cohort_ct_val.csv", index=False)
df_test.to_csv("data/cohort_ct_test.csv", index=False)

print(f"\n✓ Processed cohorts saved")


# ──────────────────────────────────────────────────────────────────────────────
# 7. KEY PARAMETERS TO TUNE
# ──────────────────────────────────────────────────────────────────────────────

"""
Parameter Tuning Guide:

GENERAL:
  • batch_size: 8-64 depending on GPU memory
    - 8: Small GPU / debugging
    - 32: Standard
    - 64: Large GPU
  
  • num_workers: 0-8
    - 0: Disable parallel (for debugging)
    - 4: Standard
    - 8: Large machines with many cores
  
  • augment: True/False
    - True: For training (reduces overfitting)
    - False: For validation/testing

IMAGE PROCESSING:
  • image_size: (256, 256), (512, 512), (1024, 1024)
    - Smaller: Faster, uses less memory
    - Larger: More detail, uses more memory
  
  • normalize range: Adjust NormalizeIntensity() in _create_transforms()
    - Default: [-1, 1] (good for medical images)
    - Alternative: [0, 1]

AUGMENTATION (in _create_transforms):
  • Probability parameters (prob=0.3 means 30% chance)
  • Rotation, flip, affine transformations
  • Noise/smoothing (optional, can hurt performance)

BALANCING:
  • balance_strategy: "undersample" or "oversample"
  • Undersample: Remove majority samples
  • Oversample: Duplicate minority samples

SPLITTING:
  • train_size, val_size, test_size
  • Default: 0.7, 0.15, 0.15
  • Alternative: 0.8, 0.1, 0.1 (if large dataset)
"""

print("\n" + "="*70)
print("✓ Quick start guide complete!")
print("="*70)
print("\nNext steps:")
print("  1. Integrate with your training loop")
print("  2. Adjust batch_size based on GPU memory")
print("  3. Tune image_size if needed")
print("  4. Monitor data loading speed (adjust num_workers)")
