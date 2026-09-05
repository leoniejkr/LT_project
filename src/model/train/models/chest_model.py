import pytorch_lightning as pl
import torch
import torch.nn as nn
import torchvision.models as models
import torchmetrics


class ChestModel(pl.LightningModule):

  def __init__(self, num_classes=15, lr=1e-4, pos_weight=None):
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

    self.train_auroc = torchmetrics.AUROC(
        task="multilabel", num_labels=num_classes, average="macro"
    )
    self.val_auroc = torchmetrics.AUROC(
        task="multilabel", num_labels=num_classes, average="macro"
    )

  def forward(self, x):
    return self.backbone(x)

  def training_step(self, batch, batch_idx):
    images, targets = batch
    logits = self(images)
    loss = self.loss_fn(logits, targets)

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
    images, targets = batch
    logits = self(images)
    loss = self.loss_fn(logits, targets)

    self.val_auroc(logits, targets.long())
    self.log("val_loss", loss, on_epoch=True, prog_bar=True)
    self.log("val_auroc", self.val_auroc, on_epoch=True, prog_bar=True)
    return loss

  def configure_optimizers(self):
    optimizer = torch.optim.AdamW(
        self.parameters(), lr=self.hparams.lr, weight_decay=1e-2
    )

    max_epochs = getattr(getattr(self, "trainer", None), "max_epochs", 50) or 50
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max_epochs
    )

    return [optimizer], [scheduler]