from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn

log = logging.getLogger(__name__)

NUM_LABELS = 13   # 12 imaging primaries + normal

# ══════════════════════════════════════════════════════════════════════════════
# CXR — Medical ViT (BiomedCLIP) oder RadImageNet
# ══════════════════════════════════════════════════════════════════════════════

class CXRMedicalFoundationModel(nn.Module):
    """
    Ersetzt DenseNet durch ein modernes Medical ViT oder CNN via Hugging Face / timm.
    Standardmäßig wird hier Microsofts BiomedCLIP (ViT-B/16) geladen.
    """

    def __init__(
        self,
        num_labels: int = NUM_LABELS,
        model_name: str = "microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
        dropout: float = 0.3,
        meta_dim: int = 0,
    ):
        super().__init__()
        self.meta_dim = meta_dim

        log.info(f"Lade CXR Medical Backbone: {model_name}...")
        try:
            from transformers import AutoModel
            # Wir nutzen nur den Vision-Tower von BiomedCLIP
            base_model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
            self.features = base_model.visual
            in_features = self.features.config.hidden_size # Meistens 768 für ViT-B
        except Exception as e:
            log.warning(f"Konnte Hugging Face Model nicht laden ({e}). Falle zurück auf timm ViT.")
            import timm
            self.features = timm.create_model("vit_base_patch16_224", pretrained=True, num_classes=0)
            in_features = self.features.num_features

        self.dropout = nn.Dropout(p=dropout)

        # Classifier Head mit optionaler Tabular-Metadaten-Fusion
        head_in = in_features + meta_dim
        self.classifier = nn.Sequential(
            nn.Linear(head_in, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout / 2),
            nn.Linear(256, num_labels),
        )

    def forward(self, x: torch.Tensor, metadata: Optional[torch.Tensor] = None) -> torch.Tensor:
        # BiomedCLIP erwartet [B, 3, 224, 224] -> passt perfekt zu deinem Preprocessing
        
        # Hugging Face ViT Output extrahieren (Pooler Output oder CLS-Token)
        outputs = self.features(x)
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            feats = outputs.pooler_output
        elif hasattr(outputs, "last_hidden_state"):
            feats = outputs.last_hidden_state[:, 0]  # CLS token
        else:
            feats = outputs # Falls es ein timm-Modell ohne Head ist
            
        feats = self.dropout(feats)

        if self.meta_dim > 0 and metadata is not None:
            feats = torch.cat([feats, metadata], dim=1)

        return self.classifier(feats)


# ══════════════════════════════════════════════════════════════════════════════
# CT — Medical 3D-ResNet (Med3D / MONAI)
# ══════════════════════════════════════════════════════════════════════════════

class CTMedical3DClassifier(nn.Module):
    """
    3D-CNN Classifier basierend auf MONAIs ResNet3D.
    Perfekt geeignet für den Transfer von Med3D (3D-ResNet Vortraining auf CTs).
    Input: [B, 1, D, H, W] -> (96x96x96 aus deinem Preprocessing)
    """

    def __init__(
        self,
        num_labels: int = NUM_LABELS,
        spatial_dims: int = 3,
        dropout: float = 0.3,
        meta_dim: int = 0,
    ):
        super().__init__()
        self.meta_dim = meta_dim

        try:
            from monai.networks.nets import resnet50
            # Wir bauen ein 3D-ResNet50 mit 1 Input-Kanal (CT-Dichte)
            self.backbone = resnet50(
                spatial_dims=spatial_dims, 
                in_channels=1, 
                num_classes=1  # Dummy, wir kappen den Head
            )
            in_features = self.backbone.fc.in_features
            self.backbone.fc = nn.Identity() # Head entfernen
            log.info("MONAI ResNet3D-50 geladen.")
        except ImportError:
            raise ImportError("Bitte installiere MONAI: pip install monai")

        self.dropout = nn.Dropout(p=dropout)

        head_in = in_features + meta_dim
        self.classifier = nn.Sequential(
            nn.Linear(head_in, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout / 2),
            nn.Linear(512, num_labels),
        )

    def forward(self, x: torch.Tensor, metadata: Optional[torch.Tensor] = None) -> torch.Tensor:
        # x: [B, 1, 96, 96, 96]
        feats = self.backbone(x) # liefert [B, in_features]
        feats = self.dropout(feats)

        if self.meta_dim > 0 and metadata is not None:
            feats = torch.cat([feats, metadata], dim=1)

        return self.classifier(feats)

# ══════════════════════════════════════════════════════════════════════════════
# Asymmetric Loss  (better than BCE for multi-label imbalance)
# ══════════════════════════════════════════════════════════════════════════════

class AsymmetricLoss(nn.Module):
    """
    ASL from Ridnik et al. 2021 (https://arxiv.org/abs/2009.14119).
    Down-weights easy negatives (gamma_neg) while keeping positives at gamma_pos=0
    (standard sigmoid for positives). clip avoids gradient explosion near p=0.

    Defaults: gamma_neg=4, gamma_pos=0, clip=0.05  (paper recommendation for medical)
    """

    def __init__(
        self,
        gamma_neg: float = 4.0,
        gamma_pos: float = 0.0,
        clip: float = 0.05,
        eps: float = 1e-8,
    ):
        super().__init__()
        self.gamma_neg = gamma_neg
        self.gamma_pos = gamma_pos
        self.clip      = clip
        self.eps       = eps

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # Probabilities
        xs_pos = torch.sigmoid(logits)
        xs_neg = 1.0 - xs_pos

        # Probability shifting (clip)
        if self.clip > 0:
            xs_neg = (xs_neg + self.clip).clamp(max=1.0)

        # Basic BCE
        lo_pos = targets       * torch.log(xs_pos.clamp(min=self.eps))
        lo_neg = (1 - targets) * torch.log(xs_neg.clamp(min=self.eps))

        # Asymmetric focusing
        if self.gamma_neg > 0 or self.gamma_pos > 0:
            pt_pos = xs_pos
            pt_neg = xs_neg

            with torch.no_grad():
                pt = pt_pos * targets + pt_neg * (1 - targets)
                gamma = self.gamma_pos * targets + self.gamma_neg * (1 - targets)
                asymmetric_w = (1 - pt) ** gamma

            lo_pos = asymmetric_w * lo_pos
            lo_neg = asymmetric_w * lo_neg

        loss = lo_pos + lo_neg
        return -loss.mean()
