"""
src/models/multilabel_models.py
────────────────────────────────
CXR:  DenseNet-121 pretrained via TorchXRayVision (CheXpert weights)
      → GlobalAvgPool → Dropout → Linear(num_labels)

CT:   SwinUNETR encoder (MONAI, pretrained on BTCV)
      → AdaptiveAvgPool3d → Dropout → Linear(num_labels)

Both optionally fuse tabular metadata features after pooling.
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn

log = logging.getLogger(__name__)

NUM_LABELS = 13   # 12 imaging primaries + normal


# ══════════════════════════════════════════════════════════════════════════════
# CXR — DenseNet-121 with CheXpert pretraining
# ══════════════════════════════════════════════════════════════════════════════

class CXRDenseNet(nn.Module):
    """
    DenseNet-121 pretrained on CheXpert (14 pathologies) via torchxrayvision.
    We strip the original classification head and attach a new multi-label head
    tuned to our label set.

    torchxrayvision gives us domain-specific weights: the features already
    encode chest pathology representations, not general ImageNet features.

    Install: pip install torchxrayvision
    """

    def __init__(
        self,
        num_labels: int = NUM_LABELS,
        weights: str = "densenet121-res224-chex",   # CheXpert pretrained
        dropout: float = 0.3,
        freeze_backbone_epochs: int = 0,             # 0 = no freezing
        meta_dim: int = 0,                           # 0 = no metadata fusion
    ):
        super().__init__()
        self.freeze_backbone_epochs = freeze_backbone_epochs
        self.meta_dim = meta_dim

        # ── Load pretrained DenseNet via torchxrayvision ─────────────────────
        try:
            import torchxrayvision as xrv
            base = xrv.models.DenseNet(weights=weights)
            self.features = base.features          # DenseNet feature extractor
            in_features   = base.classifier.in_features
            log.info(f"Loaded CXR backbone: {weights} ({in_features} features)")
        except ImportError:
            log.warning(
                "torchxrayvision not found — falling back to ImageNet DenseNet.\n"
                "Install: pip install torchxrayvision"
            )
            from torchvision.models import densenet121, DenseNet121_Weights
            base = densenet121(weights=DenseNet121_Weights.IMAGENET1K_V1)
            self.features = base.features
            in_features   = base.classifier.in_features

        self.pool    = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(p=dropout)

        # Optional metadata fusion
        head_in = in_features + meta_dim
        self.classifier = nn.Sequential(
            nn.Linear(head_in, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout / 2),
            nn.Linear(256, num_labels),
        )

    def forward(self, x: torch.Tensor, metadata: Optional[torch.Tensor] = None) -> torch.Tensor:
        # x: [B, 3, H, W] — already normalized
        feats = self.features(x)
        feats = self.pool(feats).flatten(1)     # [B, in_features]
        feats = self.dropout(feats)

        if self.meta_dim > 0 and metadata is not None:
            feats = torch.cat([feats, metadata], dim=1)

        return self.classifier(feats)           # [B, num_labels] — raw logits

    def freeze_backbone(self):
        for p in self.features.parameters():
            p.requires_grad = False
        log.info("CXR backbone frozen")

    def unfreeze_backbone(self):
        for p in self.features.parameters():
            p.requires_grad = True
        log.info("CXR backbone unfrozen")


# ══════════════════════════════════════════════════════════════════════════════
# CT — SwinUNETR encoder pretrained on BTCV
# ══════════════════════════════════════════════════════════════════════════════

SWIN_BTCV_WEIGHTS_URL = (
    "https://github.com/Project-MONAI/MONAI-extra-test-data/releases/download/"
    "0.8.1/swin_unetr.base_5000ep_f48_lr2e-4_pretrained.pt"
)


def _load_swin_pretrained(model: nn.Module, weights_path: str) -> nn.Module:
    """
    Load MONAI SwinUNETR pretrained weights (encoder only).
    The checkpoint contains both encoder and decoder; we only use the encoder.
    """
    import urllib.request
    from pathlib import Path

    cache = Path(weights_path)
    if not cache.exists():
        log.info(f"Downloading SwinUNETR weights → {cache} …")
        cache.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SWIN_BTCV_WEIGHTS_URL, str(cache))

    state = torch.load(str(cache), map_location="cpu")

    # MONAI checkpoints nest weights under 'state_dict' or 'net'
    if "state_dict" in state:
        state = state["state_dict"]
    elif "net" in state:
        state = state["net"]

    # Keep only swinViT (encoder) keys
    encoder_state = {
        k.replace("module.swinViT.", "").replace("swinViT.", ""): v
        for k, v in state.items()
        if "swinViT" in k
    }

    missing, unexpected = model.swinViT.load_state_dict(encoder_state, strict=False)
    log.info(
        f"SwinUNETR encoder weights loaded — "
        f"missing:{len(missing)}  unexpected:{len(unexpected)}"
    )
    return model


class CTSwinClassifier(nn.Module):
    """
    SwinUNETR encoder for 3D CT classification.
    Encoder output: hierarchical features → we take the bottleneck,
    apply 3D global average pooling, then classify.

    Input: [B, 1, D, H, W]  (96×96×96 after crop)
    """

    def __init__(
        self,
        num_labels: int = NUM_LABELS,
        img_size: tuple[int, int, int] = (96, 96, 96),
        feature_size: int = 48,
        dropout: float = 0.3,
        pretrained_weights: Optional[str] = "weights/swin_unetr_btcv.pt",
        meta_dim: int = 0,
    ):
        super().__init__()
        self.meta_dim = meta_dim

        try:
            from monai.networks.nets import SwinUNETR
        except ImportError:
            raise ImportError("Install MONAI: pip install monai[all]")

        # Full SwinUNETR (we only use the encoder path in forward)
        self.swin = SwinUNETR(
            img_size=img_size,
            in_channels=1,
            out_channels=14,        # dummy — we replace the head
            feature_size=feature_size,
            use_checkpoint=True,    # gradient checkpointing → lower VRAM
        )

        if pretrained_weights:
            _load_swin_pretrained(self, pretrained_weights)

        # Encoder output at deepest layer: feature_size * 16
        encoder_out_dim = feature_size * 16     # 48 * 16 = 768

        self.pool    = nn.AdaptiveAvgPool3d((1, 1, 1))
        self.dropout = nn.Dropout(p=dropout)

        head_in = encoder_out_dim + meta_dim
        self.classifier = nn.Sequential(
            nn.Linear(head_in, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout / 2),
            nn.Linear(512, num_labels),
        )

    def forward(self, x: torch.Tensor, metadata: Optional[torch.Tensor] = None) -> torch.Tensor:
        # Extract encoder features from SwinUNETR (skip decoder)
        # SwinUNETR.swinViT returns a list of hierarchical feature maps
        hidden_states = self.swin.swinViT(x, self.swin.normalize)
        feats = hidden_states[-1]           # deepest encoder feature [B, C, d, h, w]

        feats = self.pool(feats).flatten(1) # [B, encoder_out_dim]
        feats = self.dropout(feats)

        if self.meta_dim > 0 and metadata is not None:
            feats = torch.cat([feats, metadata], dim=1)

        return self.classifier(feats)       # [B, num_labels] — raw logits


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
