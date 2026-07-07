import pytorch_lightning as pl
import torch.nn as nn
import torchvision.models as models
import torchmetrics
import torch

class MultiLabelChestModel(pl.LightningModule):
    def __init__(self, num_classes=15, lr=1e-4):
        super().__init__()
        self.save_hyperparameters()
        
        # Instantiate a robust pretrained 2D classifier (e.g., DenseNet121 or ResNet50)
        self.backbone = models.densenet121(weights=models.DenseNet121_Weights.DEFAULT)
        
        # Alter the classification head to output logits for our 15 unique targets
        num_ftrs = self.backbone.classifier.in_features
        self.backbone.classifier = nn.Linear(num_ftrs, num_classes)
        
        # Loss function for multi-label classification
        self.loss_fn = nn.BCEWithLogitsLoss()
        
        # Performance Tracking via AUROC (Crucial metric for NIH/MIDRC datasets)
        self.train_auroc = torchmetrics.AUROC(task="multilabel", num_labels=num_classes, average="macro")
        self.val_auroc = torchmetrics.AUROC(task="multilabel", num_labels=num_classes, average="macro")

    def forward(self, x):
        return self.backbone(x)

    def training_step(self, batch, batch_idx):
        images, targets = batch
        logits = self(images)
        loss = self.loss_fn(logits, targets)
        
        self.train_auroc(logits, targets.long())
        self.log("train_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log("train_auroc", self.train_auroc, on_step=False, on_epoch=True, prog_bar=True)
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
        return torch.optim.AdamW(self.parameters(), lr=self.hparams.lr, weight_decay=1e-4)