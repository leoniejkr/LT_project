import os
import logging

import torch
import torch.nn as nn
import torchvision.models as models
import pytorch_lightning as pl

logger = logging.getLogger(__name__)


class MultiLabelChestModel(pl.LightningModule):
    def __init__(self, num_classes=15, lr=1e-4):
        super().__init__()
        self.save_hyperparameters()

        self.backbone = models.densenet121(weights=DEFAULT)
        num_ftrs = self.backbone.classifier.in_features
        self.backbone.classifier = nn.Linear(num_ftrs, num_classes)

        self.loss_fn = nn.BCEWithLogitsLoss()

    def forward(self, x):
        return self.backbone(x)


ALL_CLASSES = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Effusion",
    "Emphysema",
    "Fibrosis",
    "Hernia",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
    "Covid",
]

_model_instance = None


def get_model() -> MultiLabelChestModel:
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )
    logger.info("Using device: %s", device)

    checkpoint_path = os.getenv(
        "CHECKPOINT_PATH", "/app/checkpoints/dual_view_checkpoint.pth"
    )
    logger.info("Loading checkpoint from %s", checkpoint_path)

    model = MultiLabelChestModel(num_classes=15)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint)
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()

    logger.info("Model loaded successfully on %s", device)
    _model_instance = model
    return model
