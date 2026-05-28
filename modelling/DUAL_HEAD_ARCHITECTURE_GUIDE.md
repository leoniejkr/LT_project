# Dual-Head Architecture: Shared Encoder + Independent Heads

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  CT Image              CXR Image        Metadata             │
│  (512×512)             (256×256)        (age, sex,           │
│                                          conditions,          │
│                                          breathing support,   │
│                                          mRALE, etc.)        │
│    │                     │                │                  │
│    └─────────────────────┴────────────────┘                  │
│                          │                                   │
│              ┌───────────────────────┐                      │
│              │  CT Encoder (ResNet50)│                      │
│              └──────────┬────────────┘                      │
│                         │ (512-dim features)                │
│              ┌───────────────────────┐                      │
│              │ CXR Encoder(ResNet34) │                      │
│              └──────────┬────────────┘                      │
│                         │ (512-dim features)                │
│              ┌──────────┴──────────┐                        │
│              │  Metadata Processing│                        │
│              │  (normalization,    │                        │
│              │   embedding)        │                        │
│              └─────────┬───────────┘                        │
│                        │ (10-dim features)                  │
│                        │                                    │
│          ┌─────────────┴──────────────┐                     │
│          │  [Fusion Network]          │                     │
│          │  Concatenate CT + CXR      │                     │
│          │  + Metadata                │                     │
│          │  → 1034 dims → MLP         │                     │
│          │  → 256-dim shared repr.    │                     │
│          └─────────────┬──────────────┘                     │
│                        │ (256-dim shared representation)    │
│          ┌─────────────┴──────────────┐                     │
│          │                            │                     │
│     ┌────▼──────────┐           ┌────▼──────────┐           │
│     │ DISEASE HEAD  │           │  RISK HEAD    │           │
│     │               │           │               │           │
│     │ Input:        │           │ Input:        │           │
│     │ • shared_repr │           │ • shared_repr │           │
│     │   (256)       │           │   (256)       │           │
│     │               │           │ • metadata    │           │
│     │ Output:       │           │   (10)        │           │
│     │ • logits (10) │           │               │           │
│     │   diseases    │           │ Output:       │           │
│     │               │           │ • logits (1)  │           │
│     │ Multi-label   │           │ • mortality   │           │
│     │ classification│           │ • or risk score           │
│     └───────────────┘           │               │           │
│                                 │ INDEPENDENT   │           │
│                                 │ of Disease    │           │
│                                 │ Head!         │           │
│                                 └───────────────┘           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. **Shared Encoder is Critical**

The CT and CXR encoders extract visual features that feed into the **shared representation**. This:
- Creates a unified feature space from both modalities
- Enables multi-task learning (Disease + Risk heads benefit from shared features)
- Improves generalization through shared knowledge

### 2. **Risk Head Uses Shared Representation + Metadata (NOT Disease Predictions)**

**Why?** If the Disease Head fails or makes bad predictions, the Risk Head still works because:
- It learned features from images directly (via shared representation)
- It can use explicit clinical metadata (age, breathing support, mRALE score, etc.)
- It's robust to Disease Head errors

```python
# ❌ WRONG: Risk depends on Disease predictions
risk_input = disease_probs  # If disease head fails → risk fails too
risk_pred = risk_head(risk_input)

# ✅ RIGHT: Risk independent of Disease
risk_input = torch.cat([shared_repr, metadata], dim=1)  # Direct features
risk_pred = risk_head(risk_input)  # Uses image features + clinical data
```

### 3. **Multi-Task Learning**

Both heads share the same encoder/representation, so:
- Training Disease Head helps Risk Head (shared features improve)
- Training Risk Head helps Disease Head (forces shared representation to capture risk-relevant features)
- Combined loss balances both objectives:
  ```
  Total Loss = α × Disease Loss + β × Risk Loss
  ```

## Metadata Features for Risk Head

The `metadata` tensor should include:

```python
# Demographic
- age_at_index (continuous, normalized)
- sex (binary: M=1, F=0)

# Clinical conditions (binary flags per condition)
- covid (0/1)
- pneumonia (0/1)
- effusion (0/1)
- fibrosis (0/1)
- emphysema (0/1)
- atelectasis (0/1)
- pneumothorax (0/1)
- pulm_embolism (0/1)
- ards (0/1)
- pulm_edema (0/1)

# Interventions & severity
- breathing_support (0/1)
- mRALE_score (continuous, 0-24, normalized)
- icu_admission (0/1)  # Observed ICU admission

# Note: Don't include outcomes (mortality) in metadata!
# That's the target, not a feature.
```

Example tensor construction:
```python
import torch
import numpy as np

def prepare_metadata(case_data: dict) -> torch.Tensor:
    """
    Args:
        case_data: {
            'age': 65,
            'sex': 'M',
            'conditions': ['covid', 'pneumonia'],
            'breathing_support': 1,
            'mRALE_score': 12,
            'icu_admission': 1,
        }
    
    Returns:
        torch.Tensor of shape (10,) or (batch, 10)
    """
    # Initialize
    metadata = np.zeros(10)
    
    # Age (0-100 years, normalized)
    metadata[0] = case_data['age'] / 100.0
    
    # Sex (0=F, 1=M)
    metadata[1] = 1.0 if case_data['sex'] == 'M' else 0.0
    
    # Conditions (binary flags, indices 2-11 for 10 diseases)
    diseases = ['covid', 'pneumonia', 'effusion', 'fibrosis', 'emphysema',
                'atelectasis', 'pneumothorax', 'pulm_embolism', 'ards', 'pulm_edema']
    for i, disease in enumerate(diseases):
        metadata[i + 2] = 1.0 if disease in case_data['conditions'] else 0.0
    
    # Breathing support (index 12)
    # ... need to expand metadata vector or compress
    
    # mRALE score (0-24, normalized)
    # ... 
    
    return torch.from_numpy(metadata).float()
```

**Better approach**: Use a separate preprocessing step
```python
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler

df_cases = pd.read_csv("data/cases_with_conditions.csv")

# Normalize continuous features
scaler = StandardScaler()
df_cases['age_norm'] = scaler.fit_transform(df_cases[['age_at_index']])
df_cases['mRALE_norm'] = MinMaxScaler().fit_transform(df_cases[['mRALE_score']]) / 24.0

# Sex encoding
df_cases['sex_encoded'] = (df_cases['sex'] == 'M').astype(int)

# Conditions: binary columns
diseases = ['covid', 'pneumonia', 'effusion', ...]
for disease in diseases:
    df_cases[f'cond_{disease}'] = df_cases['condition'].str.contains(disease, case=False).astype(int)

# Interventions
df_cases['breathing_support'] = df_cases['breathing_support'].fillna(0).astype(int)
df_cases['icu_admission'] = df_cases['icu_admission'].fillna(0).astype(int)

# Select metadata features
metadata_cols = ['age_norm', 'sex_encoded', 'cond_covid', 'cond_pneumonia', ...,
                 'breathing_support', 'mRALE_norm', 'icu_admission']

metadata = df_cases[metadata_cols].values  # (n_samples, 10) or more
metadata_tensor = torch.from_numpy(metadata).float()
```

## Training Loop

```python
import torch
import torch.optim as optim
from torch.utils.data import DataLoader

# Initialize
model = DualHeadModel(
    image_feature_dim=512,
    metadata_dim=10,
    shared_dim=256,
    num_diseases=10,
    num_risk_outputs=1,
)
optimizer = optim.Adam(model.parameters(), lr=1e-4)
loss_fn = DualHeadLoss(disease_weight=0.6, risk_weight=0.4)

# Training
for epoch in range(num_epochs):
    for batch in train_loader:
        ct_images = batch['ct_image'].to(device)
        cxr_images = batch['cxr_image'].to(device)
        metadata = batch['metadata'].to(device)
        disease_targets = batch['disease_labels'].to(device)  # (batch, 10) binary
        risk_targets = batch['mortality'].to(device)  # (batch, 1) binary
        
        # Forward
        disease_logits, risk_logits, shared = model(ct_images, cxr_images, metadata)
        
        # Loss
        loss, loss_dict = loss_fn(
            disease_logits, disease_targets,
            risk_logits, risk_targets,
        )
        
        # Backward
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        print(f"Epoch {epoch}: {loss_dict}")
```

## Inference

```python
# Load model
model = DualHeadModel(...)
model.load_state_dict(torch.load("models/dual_head.pth"))
model.eval()

# Prepare new patient data
ct_image = load_ct("path/to/ct.nii.gz")  # (1, H, W)
cxr_image = load_cxr("path/to/cxr.dcm")  # (1, H, W)
metadata = prepare_metadata(patient_data)  # (10,)

# Inference
with torch.no_grad():
    ct_images = ct_image.unsqueeze(0).to(device)  # (1, 1, H, W)
    cxr_images = cxr_image.unsqueeze(0).to(device)  # (1, 1, H, W)
    metadata = metadata.unsqueeze(0).to(device)  # (1, 10)
    
    outputs = model.forward_with_probs(ct_images, cxr_images, metadata)
    
    disease_probs = outputs['disease_probs']  # (1, 10) - pathology predictions
    risk_probs = outputs['risk_probs']  # (1, 1) - mortality risk
    shared_repr = outputs['shared_repr']  # (1, 256) - learned features

print(f"Disease predictions (probabilities):")
for disease, prob in zip(model.disease_head.diseases, disease_probs[0]):
    print(f"  {disease}: {prob:.3f}")

print(f"\nRisk/Mortality probability: {risk_probs[0].item():.3f}")
```

## Robustness to Disease Head Failures

**Scenario**: Disease Head predicts "covid=0.95, pneumonia=0.05" but patient actually has severe pneumonia.

With this architecture:
- ❌ **If Risk Head depended on disease predictions**: Would use covid prob (wrong), risk prediction suffers
- ✅ **With shared representation**: Risk Head sees the actual CT/CXR features directly, can recognize pneumonia patterns in images independently, correct prediction

## Hyperparameter Tuning

```python
# Loss weight balance
# Higher disease_weight → better disease prediction, weaker risk prediction
# Higher risk_weight → better risk prediction, weaker disease prediction
loss_fn = DualHeadLoss(disease_weight=0.5, risk_weight=0.5)  # Balanced

# Shared representation size
shared_dim = 256  # Larger = more capacity, slower training
shared_dim = 128  # Smaller = faster, less capacity

# Metadata dimension
# Rule of thumb: include features that predict outcomes
metadata_dim = 10  # age, sex, 8 condition flags
metadata_dim = 15  # add breathing_support, mRALE_norm, icu_admission

# Dropout rates (prevent overfitting)
# Higher = stronger regularization, weaker learning
# Lower = weaker regularization, risk overfitting
```

## Summary

| Aspect | Benefit |
|--------|---------|
| **Shared Encoder** | Both modalities (CT, CXR) contribute to unified representation |
| **Multi-task Learning** | Disease head helps Risk head (features), Risk head helps Disease head |
| **Independent Risk Head** | Risk predictions don't depend on Disease Head outputs |
| **Uses Metadata** | Age, conditions, breathing support used directly for risk prediction |
| **Robust** | If Disease Head fails, Risk Head still works from learned image features |
| **Flexible** | Can swap encoders, adjust loss weights, change shared_dim easily |
