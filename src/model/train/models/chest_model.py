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

    # Cosine Annealing usually works significantly better than Plateau for vision transfer learning
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=self.trainer.max_epochs
    )

    return [optimizer], [scheduler]