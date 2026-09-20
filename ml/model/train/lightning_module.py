"""
src/training/lightning_module.py
─────────────────────────────────
Streamlined LightningModule optimized for 2D multi-label chest classification.
"""

from __future__ import annotations
import logging
import torch
import torch.nn as nn
import lightning as L
from torchmetrics.classification import MultilabelAUROC, MultilabelAveragePrecision

log = logging.getLogger(__name__)


class MultiLabelModule(L.LightningModule):

    def __init__(
        self,
        model: nn.Module,
        label_names: list[str],
        loss_fn: nn.Module,
        lr: float = 1e-4,
        weight_decay: float = 1e-5,
        max_epochs: int = 15,
    ):
        super().__init__()
        self.save_hyperparameters(ignore=["model", "loss_fn"])

        self.model = model
        self.loss_fn = loss_fn
        self.label_names = label_names
        num_labels = len(label_names)

        # ── Metrics ──────────────────────────────────────────────────────────
        self.train_auc = MultilabelAUROC(num_labels=num_labels, average="macro", thresholds=None)
        self.val_auc   = MultilabelAUROC(num_labels=num_labels, average="macro", thresholds=None)
        self.val_map   = MultilabelAveragePrecision(num_labels=num_labels, average="macro")

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        images, targets = batch
        logits = self(images)
        
        loss = self.loss_fn(logits, targets)

        # Metric updates
        self.train_auc(logits, targets.long())
        
        self.log("train_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log("train_auc", self.train_auc, on_step=False, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        images, targets = batch
        logits = self(images)
        
        loss = self.loss_fn(logits, targets)

        self.val_auc(logits, targets.long())
        self.val_map(logits, targets.long())

        self.log("val_loss", loss, on_epoch=True, prog_bar=True)
        self.log("val_auc", self.val_auc, on_epoch=True, prog_bar=True)
        self.log("val_map", self.val_map, on_epoch=True, prog_bar=False)
        return loss

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(
            self.parameters(), 
            lr=self.hparams.lr, 
            weight_decay=self.hparams.weight_decay
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, 
            T_max=self.hparams.max_epochs
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "interval": "epoch"}
        }


def tune_thresholds(
    model: L.LightningModule,
    val_loader: torch.utils.data.DataLoader,
    label_names: list[str],
    device: torch.device,
) -> dict[str, float]:
    """Finds the optimal sigmoid thresholds maximizing F1 on validation set."""
    from sklearn.metrics import f1_score
    import numpy as np

    model.eval().to(device)
    all_probs, all_targets = [], []

    with torch.no_grad():
        for batch in val_loader:
            imgs, labels = batch
            imgs = imgs.to(device)
            logits = model(imgs)
            all_probs.append(torch.sigmoid(logits).cpu().numpy())
            all_targets.append(labels.numpy())

    probs = np.concatenate(all_probs, axis=0)
    targets = np.concatenate(all_targets, axis=0)

    best_thresholds = {}
    threshold_options = [t / 100 for t in range(10, 90, 5)]

    log.info("Per-label threshold tuning (max F1 on validation split):")
    for i, name in enumerate(label_names):
        best_f1, best_t = 0.0, 0.5
        for t in threshold_options:
            preds = (probs[:, i] >= t).astype(int)
            f1 = f1_score(targets[:, i], preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_t = t
        best_thresholds[name] = float(best_t)
        log.info(f"  Class {name:<20} -> Best Threshold: {best_t:.2f} (F1: {best_f1:.4f})")

    return best_thresholds