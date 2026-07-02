"""
Dual-Head Medical Imaging Model with Shared Encoder
====================================================

Architecture:
    
    CT Images          CXR Images        Metadata (age, sex, conditions, etc.)
         │                 │                    │
         └─────────────────┴────────────────────┘
                          │
                   [Encoder Networks]
                   - ResNet/ViT for CT
                   - ResNet/ViT for CXR
                          │
              [Fusion + Shared Representation]
              (concatenate or multi-scale fusion)
                          │
             ┌────────────┴────────────┐
             │                         │
        DISEASE HEAD              RISK HEAD
        (Multi-label)             (Severity/Outcome)
        outputs:                  outputs:
        - covid                   - mortality risk
        - pneumonia               - icu admission
        - effusion                - severe outcome
        - fibrosis                - length of stay
        - emphysema               
        - atelectasis          Uses:
        - pneumothorax         - shared representation
        - pulm_embolism        - age, sex
        - ards                 - conditions
        - pulm_edema           - breathing support
                               - mRALE score
                               - hospital/ICU admission flags
                               
                           INDEPENDENT of Disease Head!
                           If Disease Head fails, Risk Head
                           still works from learned features + metadata.

Key Advantages:
  1. Risk Head doesn't cascade errors from Disease Head
  2. Risk Head learns from actual image features (shared representation)
  3. Risk Head can use domain-specific clinical knowledge (metadata)
  4. Shared encoder improves both heads through multi-task learning
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict


# ──────────────────────────────────────────────────────────────────────────────
# 1. SHARED ENCODERS (modality-specific)
# ──────────────────────────────────────────────────────────────────────────────

class CTEncoder(nn.Module):
    """
    Encodes CT chest scans.
    Can use pretrained ResNet50, ViT, or custom architecture.
    """
    def __init__(self, pretrained: bool = True, feature_dim: int = 512):
        super().__init__()
        
        # Option A: ResNet50 (recommended for CT)
        import torchvision.models as models
        self.backbone = models.resnet50(pretrained=pretrained)
        self.backbone.fc = nn.Linear(2048, feature_dim)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, 1, H, W) or (batch, C, H, W)
        Returns:
            (batch, feature_dim)
        """
        return self.backbone(x)


class CXREncoder(nn.Module):
    """
    Encodes CXR (chest X-ray) images.
    Lighter architecture than CT (CXR is lower resolution).
    """
    def __init__(self, pretrained: bool = True, feature_dim: int = 512):
        super().__init__()
        
        # Option B: ResNet34 (lighter, faster)
        import torchvision.models as models
        self.backbone = models.resnet34(pretrained=pretrained)
        self.backbone.fc = nn.Linear(512, feature_dim)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, 1, H, W) or (batch, 3, H, W)
        Returns:
            (batch, feature_dim)
        """
        return self.backbone(x)


# ──────────────────────────────────────────────────────────────────────────────
# 2. FUSION & SHARED REPRESENTATION
# ──────────────────────────────────────────────────────────────────────────────

class SharedRepresentation(nn.Module):
    """
    Fuses CT and CXR representations + metadata.
    Creates a unified feature space for downstream heads.
    """
    def __init__(
        self,
        image_feature_dim: int = 512,
        metadata_dim: int = 10,  # age, sex, conditions, etc.
        shared_dim: int = 256,
    ):
        super().__init__()
        
        # Input: CT features + CXR features + metadata
        total_input_dim = image_feature_dim * 2 + metadata_dim
        
        # Fusion network
        self.fusion = nn.Sequential(
            nn.Linear(total_input_dim, shared_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(shared_dim * 2, shared_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
        
        self.shared_dim = shared_dim
        
    def forward(
        self,
        ct_features: torch.Tensor,
        cxr_features: torch.Tensor,
        metadata: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            ct_features: (batch, 512)
            cxr_features: (batch, 512)
            metadata: (batch, metadata_dim) - age, sex, conditions, etc.
        
        Returns:
            (batch, shared_dim) - unified representation
        """
        # Concatenate all features
        combined = torch.cat([ct_features, cxr_features, metadata], dim=1)
        
        # Fuse
        shared_repr = self.fusion(combined)
        
        return shared_repr


# ──────────────────────────────────────────────────────────────────────────────
# 3. DISEASE HEAD (Multi-label classification on images)
# ──────────────────────────────────────────────────────────────────────────────

class DiseaseHead(nn.Module):
    """
    Predicts multiple pathologies from shared representation.
    Uses image features primarily.
    """
    def __init__(self, shared_dim: int = 256, num_diseases: int = 10):
        super().__init__()
        
        # Disease head: focus on image-based pathology
        self.disease_predictor = nn.Sequential(
            nn.Linear(shared_dim, shared_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(shared_dim // 2, num_diseases),
        )
        
        self.diseases = [
            "covid",
            "pneumonia",
            "effusion",
            "fibrosis",
            "emphysema",
            "atelectasis",
            "pneumothorax",
            "pulm_embolism",
            "ards",
            "pulm_edema",
        ]
        
    def forward(self, shared_repr: torch.Tensor) -> torch.Tensor:
        """
        Args:
            shared_repr: (batch, shared_dim)
        
        Returns:
            (batch, num_diseases) - logits or probabilities
        """
        logits = self.disease_predictor(shared_repr)
        return logits
    
    def forward_with_probs(self, shared_repr: torch.Tensor) -> torch.Tensor:
        """Returns sigmoid probabilities instead of logits."""
        logits = self.forward(shared_repr)
        return torch.sigmoid(logits)


# ──────────────────────────────────────────────────────────────────────────────
# 4. RISK HEAD (Severity/Outcome prediction - INDEPENDENT of Disease Head)
# ──────────────────────────────────────────────────────────────────────────────

class RiskHead(nn.Module):
    """
    Predicts patient risk/severity/outcomes.
    
    IMPORTANT: Uses shared representation + metadata directly.
    Does NOT depend on Disease Head predictions.
    
    Why? If Disease Head makes bad predictions, Risk Head still works
    because it learned from image features directly.
    """
    def __init__(
        self,
        shared_dim: int = 256,
        metadata_dim: int = 10,
        num_risk_outputs: int = 1,  # e.g., 1 for binary mortality
    ):
        super().__init__()
        
        # Risk prediction uses shared representation + original metadata
        # (don't use Disease Head predictions)
        input_dim = shared_dim + metadata_dim
        
        self.risk_predictor = nn.Sequential(
            nn.Linear(input_dim, input_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(input_dim // 2, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_risk_outputs),
        )
        
        self.risk_outputs = [
            "mortality_risk",  # or multiple: mortality, icu_admission, severe_outcome, etc.
        ]
        
    def forward(
        self,
        shared_repr: torch.Tensor,
        metadata: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            shared_repr: (batch, shared_dim) - learned image features
            metadata: (batch, metadata_dim) - age, sex, conditions, breathing support, etc.
        
        Returns:
            (batch, num_risk_outputs) - logits or probabilities
        """
        # Recombine shared representation with original metadata
        risk_input = torch.cat([shared_repr, metadata], dim=1)
        logits = self.risk_predictor(risk_input)
        return logits
    
    def forward_with_probs(
        self,
        shared_repr: torch.Tensor,
        metadata: torch.Tensor,
    ) -> torch.Tensor:
        """Returns sigmoid probabilities."""
        logits = self.forward(shared_repr, metadata)
        return torch.sigmoid(logits)


# ──────────────────────────────────────────────────────────────────────────────
# 5. COMPLETE DUAL-HEAD MODEL
# ──────────────────────────────────────────────────────────────────────────────

class DualHeadModel(nn.Module):
    """
    Complete architecture: encoders → shared representation → disease + risk heads.
    """
    def __init__(
        self,
        image_feature_dim: int = 512,
        metadata_dim: int = 10,
        shared_dim: int = 256,
        num_diseases: int = 10,
        num_risk_outputs: int = 1,
    ):
        super().__init__()
        
        # Encoders
        self.ct_encoder = CTEncoder(feature_dim=image_feature_dim)
        self.cxr_encoder = CXREncoder(feature_dim=image_feature_dim)
        
        # Shared representation
        self.shared_repr = SharedRepresentation(
            image_feature_dim=image_feature_dim,
            metadata_dim=metadata_dim,
            shared_dim=shared_dim,
        )
        
        # Heads (INDEPENDENT)
        self.disease_head = DiseaseHead(
            shared_dim=shared_dim,
            num_diseases=num_diseases,
        )
        self.risk_head = RiskHead(
            shared_dim=shared_dim,
            metadata_dim=metadata_dim,
            num_risk_outputs=num_risk_outputs,
        )
        
    def forward(
        self,
        ct_images: torch.Tensor,
        cxr_images: torch.Tensor,
        metadata: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            ct_images: (batch, 1 or 3, H, W)
            cxr_images: (batch, 1 or 3, H, W)
            metadata: (batch, metadata_dim)
        
        Returns:
            disease_logits: (batch, num_diseases)
            risk_logits: (batch, num_risk_outputs)
            shared_representation: (batch, shared_dim)
        """
        # Encode images
        ct_feat = self.ct_encoder(ct_images)
        cxr_feat = self.cxr_encoder(cxr_images)
        
        # Shared representation
        shared = self.shared_repr(ct_feat, cxr_feat, metadata)
        
        # Heads (independent pathways)
        disease_logits = self.disease_head(shared)
        risk_logits = self.risk_head(shared, metadata)
        
        return disease_logits, risk_logits, shared
    
    def forward_with_probs(
        self,
        ct_images: torch.Tensor,
        cxr_images: torch.Tensor,
        metadata: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with probabilities instead of logits.
        """
        ct_feat = self.ct_encoder(ct_images)
        cxr_feat = self.cxr_encoder(cxr_images)
        shared = self.shared_repr(ct_feat, cxr_feat, metadata)
        
        disease_probs = self.disease_head.forward_with_probs(shared)
        risk_probs = self.risk_head.forward_with_probs(shared, metadata)
        
        return {
            "disease_probs": disease_probs,  # (batch, 10)
            "risk_probs": risk_probs,  # (batch, 1)
            "shared_repr": shared,  # (batch, 256)
        }


# ──────────────────────────────────────────────────────────────────────────────
# 6. LOSS FUNCTIONS (Multi-task learning)
# ──────────────────────────────────────────────────────────────────────────────

class DualHeadLoss(nn.Module):
    """
    Combined loss for both heads.
    """
    def __init__(
        self,
        disease_weight: float = 0.6,
        risk_weight: float = 0.4,
    ):
        super().__init__()
        
        # Disease head: multi-label → BCEWithLogitsLoss
        self.disease_loss_fn = nn.BCEWithLogitsLoss()
        
        # Risk head: binary/multi-class → BCEWithLogitsLoss or CrossEntropyLoss
        self.risk_loss_fn = nn.BCEWithLogitsLoss()
        
        self.disease_weight = disease_weight
        self.risk_weight = risk_weight
        
    def forward(
        self,
        disease_logits: torch.Tensor,
        disease_targets: torch.Tensor,
        risk_logits: torch.Tensor,
        risk_targets: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Args:
            disease_logits: (batch, num_diseases)
            disease_targets: (batch, num_diseases) - binary labels
            risk_logits: (batch, num_risk_outputs)
            risk_targets: (batch, num_risk_outputs) - binary labels
        
        Returns:
            total_loss, {'disease_loss': ..., 'risk_loss': ...}
        """
        disease_loss = self.disease_loss_fn(disease_logits, disease_targets.float())
        risk_loss = self.risk_loss_fn(risk_logits, risk_targets.float())
        
        total_loss = (self.disease_weight * disease_loss + 
                     self.risk_weight * risk_loss)
        
        return total_loss, {
            "disease_loss": disease_loss.item(),
            "risk_loss": risk_loss.item(),
            "total_loss": total_loss.item(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# 7. EXAMPLE USAGE
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    # Initialize model
    model = DualHeadModel(
        image_feature_dim=512,
        metadata_dim=10,  # age, sex, conditions, breathing support, etc.
        shared_dim=256,
        num_diseases=10,
        num_risk_outputs=1,  # binary mortality
    )
    
    # Dummy data
    batch_size = 4
    ct_images = torch.randn(batch_size, 3, 512, 512)  # CT scans
    cxr_images = torch.randn(batch_size, 1, 256, 256)  # CXR scans
    metadata = torch.randn(batch_size, 10)  # age, sex, conditions, etc.
    
    disease_targets = torch.randint(0, 2, (batch_size, 10)).float()
    risk_targets = torch.randint(0, 2, (batch_size, 1)).float()
    
    # Forward pass
    disease_logits, risk_logits, shared = model(ct_images, cxr_images, metadata)
    
    print(f"Disease logits shape: {disease_logits.shape}")
    print(f"Risk logits shape: {risk_logits.shape}")
    print(f"Shared representation shape: {shared.shape}")
    
    # Compute loss
    loss_fn = DualHeadLoss(disease_weight=0.6, risk_weight=0.4)
    total_loss, loss_dict = loss_fn(
        disease_logits, disease_targets,
        risk_logits, risk_targets,
    )
    
    print(f"\nLoss breakdown:")
    for key, val in loss_dict.items():
        print(f"  {key}: {val:.4f}")
    
    # Get probabilities
    outputs = model.forward_with_probs(ct_images, cxr_images, metadata)
    print(f"\nDisease probabilities shape: {outputs['disease_probs'].shape}")
    print(f"Risk probability shape: {outputs['risk_probs'].shape}")
