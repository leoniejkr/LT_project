"""
src/training/lightning_module.py
─────────────────────────────────
Single LightningModule that works for both CXR and CT.
Handles:
  - Asymmetric loss
  - Per-label AUC + macro mAP logging
  - Cosine warmup LR schedule
  - Backbone freeze/unfreeze (for CXR DenseNet)
  - Per-label threshold tuning on val set (called after training)
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn
import lightning as L
from torchmetrics.classification import (
    MultilabelAUROC,
    MultilabelAveragePrecision,
    MultilabelF1Score,
)

log = logging.getLogger(__name__)


class MultiLabelModule(L.LightningModule):

    def __init__(
        self,
        model: nn.Module,
        label_names: list[str],
        loss_fn: nn.Module,
        lr: float = 1e-4,
        weight_decay: float = 1e-5,
        warmup_epochs: int = 3,
        max_epochs: int = 50,
        freeze_backbone_epochs: int = 0,
    ):
        super().__init__()
        self.save_hyperparameters(ignore=["model", "loss_fn"])

        self.model     = model
        self.loss_fn   = loss_fn
        self.label_names = label_names
        num_labels     = len(label_names)

        self.freeze_epochs = freeze_backbone_epochs

        # ── Metrics ──────────────────────────────────────────────────────────
        metric_kw = dict(num_labels=num_labels, average="none")  # <-- WICHTIG: auf "none" ändern!

        for split in ("train", "val", "test"):
            setattr(self, f"{split}_auroc", MultilabelAUROC(**metric_kw))
            setattr(self, f"{split}_map",   MultilabelAveragePrecision(**metric_kw))
            setattr(self, f"{split}_f1",    MultilabelF1Score(**metric_kw, threshold=0.5))

        self.val_auroc_per = MultilabelAUROC(num_labels=num_labels, average="none")

    # ── Shared step ──────────────────────────────────────────────────────────

    def _step(self, batch: dict, split: str):
        logits = self.model(
            batch["image"],
            metadata=batch.get("metadata"),
        )
        targets = batch["label"].float()
        loss    = self.loss_fn(logits, targets)
        probs   = torch.sigmoid(logits)

        getattr(self, f"{split}_auroc").update(probs, targets.int())
        getattr(self, f"{split}_map").update(probs, targets.int())
        getattr(self, f"{split}_f1").update(probs, targets.int())

        if split == "val":
            self.val_auroc_per.update(probs, targets.int())

        self.log(f"{split}/loss", loss, prog_bar=True, on_step=True, on_epoch=True, sync_dist=True)
        return loss

    def _epoch_end(self, split: str):
        # Berechnet die Rohwerte pro Klasse (Form: [num_labels])
        auroc_per_class = getattr(self, f"{split}_auroc").compute()
        map_per_class   = getattr(self, f"{split}_map").compute()
        f1_per_class    = getattr(self, f"{split}_f1").compute()

        # ── Sicherer Macro-Schnitt ───────────────────────────────────────────
        # Wir filtern NaN- oder Null-Werte aus, die durch fehlende Positives/Negatives entstehen
        valid_auroc = auroc_per_class[~torch.isnan(auroc_per_class) & (auroc_per_class > 0.0)]
        valid_map   = map_per_class[~torch.isnan(map_per_class)]
        valid_f1    = f1_per_class[~torch.isnan(f1_per_class)]

        # Falls gar keine Klasse valide Daten hatte, Fallback auf 0.0, sonst Mittelwert
        macro_auroc = valid_auroc.mean() if len(valid_auroc) > 0 else torch.tensor(0.0)
        macro_mAP   = valid_map.mean()   if len(valid_map) > 0   else torch.tensor(0.0)
        macro_f1    = valid_f1.mean()    if len(valid_f1) > 0    else torch.tensor(0.0)

        # Logge die bereinigten Macro-Werte
        self.log(f"{split}/AUROC", macro_auroc, prog_bar=True, sync_dist=True)
        self.log(f"{split}/mAP",   macro_mAP,   prog_bar=True, sync_dist=True)
        self.log(f"{split}/F1",    macro_f1,    prog_bar=True, sync_dist=True)

        # Reset der internen Stat-Tracker
        getattr(self, f"{split}_auroc").reset()
        getattr(self, f"{split}_map").reset()
        getattr(self, f"{split}_f1").reset()

        # Zusätzliches Per-Label-Logging für die Validierung
        if split == "val":
            self.val_auroc_per.reset()
            for name, auc in zip(self.label_names, auroc_per_class):
                # Wenn der Wert ungültig ist, schreiben wir stattdessen NaN ins Log
                val_to_log = auc.item() if not torch.isnan(auc) and auc.item() > 0.0 else float('nan')
                self.log(f"val/auroc_{name}", val_to_log, sync_dist=True)
            
            log.info(
                "Val per-label AUROC:\n" +
                "\n".join(f"  {n:<30}: {auc.item():.3f}" if not torch.isnan(auc) and auc.item() > 0.0 else f"  {n:<30}: NO_SAMPLES" for n, auc in zip(self.label_names, auroc_per_class))
            )
        
    # ── Lightning hooks ───────────────────────────────────────────────────────

    def training_step(self, batch, batch_idx):
        return self._step(batch, "train")

    def on_train_epoch_end(self):
        self._epoch_end("train")
        # Unfreeze backbone after N epochs
        if (
            self.freeze_epochs > 0
            and self.current_epoch == self.freeze_epochs
            and hasattr(self.model, "unfreeze_backbone")
        ):
            self.model.unfreeze_backbone()
            log.info(f"Epoch {self.current_epoch}: backbone unfrozen")

    def validation_step(self, batch, batch_idx):
        return self._step(batch, "val")

    def on_validation_epoch_end(self):
        self._epoch_end("val")

    def test_step(self, batch, batch_idx):
        return self._step(batch, "test")

    def on_test_epoch_end(self):
        self._epoch_end("test")

    # ── Optimizer + scheduler ─────────────────────────────────────────────────

    def configure_optimizers(self):
        # Nutzt die LR und das Weight Decay aus deiner Config
        optimizer = torch.optim.AdamW(
            self.parameters(), 
            lr=self.hparams.lr if hasattr(self, "hparams") else 1e-4, 
            weight_decay=self.hparams.weight_decay if hasattr(self, "hparams") else 1e-4
        )
        
        # Der Scheduler überwacht den Epochen-Loss der Validierung
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, 
            mode="min", 
            factor=0.1, 
            patience=3, 
        )
        
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "monitor": "val/loss_epoch",  # Wichtig: Muss exakt zu deinem self.log() passen
                "interval": "epoch",
                "frequency": 1,
            },
        }


# ── Per-label threshold tuning ────────────────────────────────────────────────

def tune_thresholds(
    model: nn.Module,
    val_loader,
    label_names: list[str],
    device: str = "cuda",
    thresholds: list[float] = None,
) -> dict[str, float]:
    """
    For each label, find the threshold that maximises F1 on the val set.
    Returns a dict: {label_name: optimal_threshold}.

    Use this AFTER training to convert logits → binary predictions at test time.
    """
    from sklearn.metrics import f1_score
    import numpy as np

    if thresholds is None:
        thresholds = [t / 100 for t in range(10, 90, 5)]

    model.eval().to(device)
    all_probs, all_targets = [], []

    with torch.no_grad():
        for batch in val_loader:
            imgs = batch["image"].to(device)
            meta = batch.get("metadata")
            if meta is not None:
                meta = meta.to(device)
            logits = model(imgs, metadata=meta)
            all_probs.append(torch.sigmoid(logits).cpu().numpy())
            all_targets.append(batch["label"].numpy())

    probs   = np.concatenate(all_probs,   axis=0)   # [N, num_labels]
    targets = np.concatenate(all_targets, axis=0)

    best_thresholds = {}
    log.info("Per-label threshold tuning (max F1 on val):")
    for i, name in enumerate(label_names):
        best_f1, best_t = 0.0, 0.5
        for t in thresholds:
            preds = (probs[:, i] >= t).astype(int)
            f1 = f1_score(targets[:, i], preds, zero_division=0)
            if f1 > best_f1:
                best_f1, best_t = f1, t
        best_thresholds[name] = best_t
        log.info(f"  {name:<30}: threshold={best_t:.2f}  F1={best_f1:.3f}")

    return best_thresholds
