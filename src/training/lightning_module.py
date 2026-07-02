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
        metric_kw = dict(num_labels=num_labels, average="macro")

        for split in ("train", "val", "test"):
            setattr(self, f"{split}_auroc", MultilabelAUROC(**metric_kw))
            setattr(self, f"{split}_map",   MultilabelAveragePrecision(**metric_kw))
            setattr(self, f"{split}_f1",    MultilabelF1Score(**metric_kw, threshold=0.5))

        # Per-label AUROC for val (diagnostic)
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
        auroc = getattr(self, f"{split}_auroc").compute()
        mAP   = getattr(self, f"{split}_map").compute()
        f1    = getattr(self, f"{split}_f1").compute()

        self.log(f"{split}/AUROC", auroc, prog_bar=True, sync_dist=True)
        self.log(f"{split}/mAP",   mAP,   prog_bar=True, sync_dist=True)
        self.log(f"{split}/F1",    f1,    sync_dist=True)

        getattr(self, f"{split}_auroc").reset()
        getattr(self, f"{split}_map").reset()
        getattr(self, f"{split}_f1").reset()

        if split == "val":
            per_label = self.val_auroc_per.compute()
            self.val_auroc_per.reset()
            for name, auc in zip(self.label_names, per_label):
                self.log(f"val/auroc_{name}", auc, sync_dist=True)
            log.info(
                "Val per-label AUROC:\n" +
                "\n".join(f"  {n:<30}: {v:.3f}" for n, v in zip(self.label_names, per_label))
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
        optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, self.parameters()),
            lr=self.hparams.lr,
            weight_decay=self.hparams.weight_decay,
        )

        # Linear warmup → cosine decay
        def lr_lambda(epoch):
            warmup = self.hparams.warmup_epochs
            total  = self.hparams.max_epochs
            if epoch < warmup:
                return float(epoch + 1) / float(max(1, warmup))
            progress = float(epoch - warmup) / float(max(1, total - warmup))
            import math
            return 0.5 * (1.0 + math.cos(math.pi * progress))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "interval":  "epoch",
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
