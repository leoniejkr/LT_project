import pytorch_lightning as pl
import torch
import torch.nn as nn
import torchvision.models as models
import torchmetrics


class ChestModel(pl.LightningModule):

  # Fully-convolutional backbone (ConvNeXt-Base), so the input resolution is
  # flexible. 384 is a good detail/performance trade-off for chest X-rays.
  INPUT_SIZE = 384
  # Recommended default batch size at INPUT_SIZE (memory-sensitive models can
  # lower this). train.py uses it unless overridden in its config.
  BATCH_SIZE = 32

  def __init__(self, num_classes=15, lr=1e-4, pos_weight=None,
               backbone_factor=0.1, max_epochs=5):
    super().__init__()
    self.save_hyperparameters(ignore=["pos_weight"])

    # Modern backbone replacement: ConvNeXt-Base or DenseNet121
    self.backbone = models.convnext_base(
        weights=models.ConvNeXt_Base_Weights.DEFAULT
    )

    num_ftrs = self.backbone.classifier[2].in_features
    self.backbone.classifier[2] = nn.Linear(num_ftrs, num_classes)

    # Weighted Loss to tackle severe class imbalance
    # pos_weight should be a Tensor of shape [num_classes]
    self.register_buffer("pos_weight", pos_weight)
    self.loss_fn = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight)

    # Metrics setup (AUC per class)
    self.train_auroc = torchmetrics.AUROC(
        task="multilabel", num_labels=num_classes, average="macro"
    )
    self.val_auroc = torchmetrics.AUROC(
        task="multilabel", num_labels=num_classes, average="macro"
    )

  def masked_loss_fn(self, logits, targets, mask):
    """Masked BCE loss for partial labels.

    `mask` has the same shape as `targets` (batch x num_classes) and is
    1 where the label is known/reliable and 0 where it is unknown (missing
    annotation). Loss is only back-propagated through the masked entries,
    so e.g. MIDRC images (only Covid annotated) never push the other 14
    classes towards 0 even though they may carry undisclosed comorbidities.
    """
    bce = torch.nn.functional.binary_cross_entropy_with_logits(
        logits, targets, pos_weight=self.pos_weight, reduction="none"
    )
    bce = bce * mask
    return bce.sum() / mask.sum().clamp(min=1.0)

  def forward(self, x):
    return self.backbone(x)

  def training_step(self, batch, batch_idx):
    images, targets, masks = batch
    logits = self(images)
    loss = self.masked_loss_fn(logits, targets, masks)

    self.train_auroc(logits, targets.long())
    self.log(
        "train_loss", loss, on_step=False, on_epoch=True, prog_bar=True
    )
    self.log(
        "train_auroc",
        self.train_auroc,
        on_step=False,
        on_epoch=True,
        prog_bar=True,
    )
    return loss

  def validation_step(self, batch, batch_idx):
    images, targets, masks = batch
    logits = self(images)
    loss = self.masked_loss_fn(logits, targets, masks)

    self.val_auroc(logits, targets.long())
    self.log("val_loss", loss, on_epoch=True, prog_bar=True)
    self.log("val_auroc", self.val_auroc, on_epoch=True, prog_bar=True)
    return loss

  def configure_optimizers(self):
    # Differential learning rates: frozen-stable backbone features get a lower
    # lr than the freshly-initialized classification head.
    head_params = list(self.backbone.classifier.parameters())
    backbone_params = [
        p for n, p in self.backbone.named_parameters()
        if not n.startswith("classifier")
    ]
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_params, "lr": self.hparams.lr * self.hparams.backbone_factor},
            {"params": head_params, "lr": self.hparams.lr},
        ],
        weight_decay=1e-2,
    )

    # Also honor a real Trainer's max_epochs when used with pl.Trainer,
    # otherwise fall back to the hparam passed at construction.
    try:
        trainer_epochs = getattr(self.trainer, "max_epochs", None)
    except RuntimeError:
        trainer_epochs = None
    max_epochs = trainer_epochs if trainer_epochs else self.hparams.max_epochs
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max_epochs, eta_min=1e-6
    )

    return [optimizer], [scheduler]