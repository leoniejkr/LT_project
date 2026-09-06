import pytorch_lightning as pl
import torch
import torch.nn as nn
import torchmetrics
import torchvision.models as models


class SwinTransformerChestModel(pl.LightningModule):

  # Swin uses a relative-position bias that can be interpolated, so it accepts
  # other resolutions (e.g. 384) without breaking. We default to 224 because the
  # ImageNet-1K pre-trained weights were tuned at 224 — matching the pre-training
  # resolution is the safest transfer-learning choice. Bump INPUT_SIZE if higher
  # detail matters more than preserving the pre-trained bias.
  INPUT_SIZE = 224
  # Transformers are memory-hungry; a conservative batch size at 224.
  BATCH_SIZE = 24

  def __init__(
      self, num_classes=15, lr=1e-4, weight_decay=1e-2, pos_weight=None
  ):
    super().__init__()
    self.save_hyperparameters(ignore=["pos_weight"])

    # 1. Load Pretrained Swin Transformer Base
    self.backbone = models.swin_b(
        weights=models.Swin_B_Weights.SWIN_B_IMAGE1K_V1
    )

    # 2. Extract input features from the default Swin head and swap for multi-label classifier
    num_ftrs = self.backbone.head.in_features
    self.backbone.head = nn.Linear(num_ftrs, num_classes)

    # 3. Class Imbalance Mitigation (register buffer avoids device mismatch issues across GPUs)
    self.register_buffer("pos_weight", pos_weight)
    self.loss_fn = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight)

    # 4. Metrics setup
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
    """Swin Transformers require layer-wise learning rate decay for optimal transfer learning.

    We set a conservative LR for patch embedding and early blocks, with a slightly higher LR for the classification head.
    """
    head_params = list(self.backbone.head.parameters())
    backbone_params = [
        p
        for n, p in self.backbone.named_parameters()
        if not n.startswith("head")
    ]

    optimizer = torch.optim.AdamW(
        [
            {
                "params": backbone_params,
                "lr": self.hparams.lr * 0.1,
            },  # 1e-5 (Preserves pretrained feature representations)
            {
                "params": head_params,
                "lr": self.hparams.lr,
            },  # 1e-4 (Convergence for new targets)
        ],
        weight_decay=self.hparams.weight_decay,
    )

    max_epochs = getattr(getattr(self, "trainer", None), "max_epochs", 10) or 10
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max_epochs, eta_min=1e-6
    )

    return [optimizer], [scheduler]