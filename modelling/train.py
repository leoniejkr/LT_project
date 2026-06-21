#!/usr/bin/env python3
"""
scripts/train.py
─────────────────
Trains CXR and CT models sequentially (or one at a time).

Usage:
    # Both modalities
    python scripts/train.py --config configs/config.yaml

    # CXR only
    python scripts/train.py --config configs/config.yaml --modality cxr

    # CT only, with metadata features
    python scripts/train.py --config configs/config.yaml --modality ct --use-metadata

    # Resume from checkpoint
    python scripts/train.py --config configs/config.yaml --modality cxr \
        --resume checkpoints/cxr_epoch=12-val_mAP=0.71.ckpt
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def train_cxr(cfg: dict, use_metadata: bool, resume: str | None):
    import lightning as L
    from lightning.pytorch.callbacks import (
        EarlyStopping, ModelCheckpoint, LearningRateMonitor
    )

    from src.data.datasets import make_cxr_dataloaders, PRIMARY_LABELS, METADATA_LABELS
    from src.models.multilabel_models import CXRDenseNet, AsymmetricLoss
    from src.training.lightning_module import MultiLabelModule, tune_thresholds
    import json

    log.info("=" * 60)
    log.info("TRAINING CXR")
    log.info("=" * 60)

    cxr_cfg  = cfg["cxr"]
    data_cfg = cfg["data"]
    train_cfg = cfg["training"]
    labels_cfg = cfg["labels"]

    label_cols = labels_cfg["primary"]
    meta_cols  = labels_cfg["metadata"] if use_metadata else None
    meta_dim   = len(meta_cols) if meta_cols else 0

    # ── Data ─────────────────────────────────────────────────────────────────
    train_loader, val_loader, test_loader, label_cols = make_cxr_dataloaders(
        cohort_csv=data_cfg["cohort_cxr"].replace(".csv", "_preprocessed.csv"),
        prep_dir=data_cfg["prep_dir"] + "cxr",
        label_cols=label_cols,
        meta_cols=meta_cols,
        val_frac=data_cfg["val_frac"],
        test_frac=data_cfg["test_frac"],
        batch_size=cxr_cfg["batch_size"],
        num_workers=data_cfg["num_workers"],
        seed=cfg["project"]["seed"],
    )

    # ── Model ─────────────────────────────────────────────────────────────────
    model = CXRDenseNet(
        num_labels=len(label_cols),
        weights=cxr_cfg.get("pretrained_weights", "densenet121-res224-chex"),
        dropout=0.3,
        meta_dim=meta_dim,
    )

    loss_cfg = cxr_cfg["loss"]
    loss_fn  = AsymmetricLoss(
        gamma_neg=loss_cfg["gamma_neg"],
        gamma_pos=loss_cfg["gamma_pos"],
        clip=loss_cfg["clip"],
    )

    sched_cfg = cxr_cfg["scheduler"]
    module = MultiLabelModule(
        model=model,
        label_names=label_cols,
        loss_fn=loss_fn,
        lr=cxr_cfg["optimizer"]["lr"],
        weight_decay=cxr_cfg["optimizer"]["weight_decay"],
        warmup_epochs=sched_cfg["warmup_epochs"],
        max_epochs=sched_cfg["max_epochs"],
    )

    # ── Logger ────────────────────────────────────────────────────────────────
    log_cfg = cfg["logging"]
    if log_cfg["logger"] == "wandb":
        try:
            from lightning.pytorch.loggers import WandbLogger
            logger = WandbLogger(
                project=log_cfg["project"],
                name=cfg["project"]["run_name"] + "_cxr",
            )
        except ImportError:
            log.warning("wandb not installed — using CSV logger")
            from lightning.pytorch.loggers import CSVLogger
            logger = CSVLogger("logs/", name="cxr")
    else:
        from lightning.pytorch.loggers import CSVLogger
        logger = CSVLogger("logs/", name="cxr")

    # ── Callbacks ─────────────────────────────────────────────────────────────
    es_cfg   = train_cfg["early_stopping"]
    ckpt_cfg = train_cfg["checkpointing"]

    callbacks = [
        EarlyStopping(monitor=es_cfg["monitor"].replace("/", "/"), patience=es_cfg["patience"], mode=es_cfg["mode"]),
        ModelCheckpoint(
            monitor=ckpt_cfg["monitor"],
            mode=ckpt_cfg["mode"],
            save_top_k=ckpt_cfg["save_top_k"],
            dirpath=ckpt_cfg["dirpath"] + "cxr/",
            filename="cxr_{epoch:02d}-val_mAP_{val/mAP:.3f}",
        ),
        LearningRateMonitor(logging_interval="epoch"),
    ]

    # ── Trainer ───────────────────────────────────────────────────────────────
    trainer = L.Trainer(
        max_epochs=sched_cfg["max_epochs"],
        accelerator=train_cfg["accelerator"],
        devices=train_cfg["devices"],
        precision=train_cfg["precision"],
        accumulate_grad_batches=cxr_cfg["accumulate_grad_batches"],
        callbacks=callbacks,
        logger=logger,
        log_every_n_steps=log_cfg["log_every_n_steps"],
        deterministic=False,    # True = slower but reproducible
    )

    trainer.fit(module, train_loader, val_loader, ckpt_path=resume)

    # ── Test ──────────────────────────────────────────────────────────────────
    trainer.test(module, test_loader, ckpt_path="best")

    # ── Threshold tuning ─────────────────────────────────────────────────────
    if cxr_cfg.get("threshold_tuning", True):
        device = "cuda" if train_cfg["devices"] > 0 else "cpu"
        thresholds = tune_thresholds(module.model, val_loader, label_cols, device=device)
        out_path = Path(ckpt_cfg["dirpath"]) / "cxr_thresholds.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            import json
            json.dump(thresholds, f, indent=2)
        log.info(f"Thresholds saved → {out_path}")


def train_ct(cfg: dict, use_metadata: bool, resume: str | None):
    import lightning as L
    from lightning.pytorch.callbacks import (
        EarlyStopping, ModelCheckpoint, LearningRateMonitor
    )

    from src.data.datasets import make_ct_dataloaders, PRIMARY_LABELS, METADATA_LABELS
    from src.models.multilabel_models import CTSwinClassifier, AsymmetricLoss
    from src.training.lightning_module import MultiLabelModule, tune_thresholds
    import json

    log.info("=" * 60)
    log.info("TRAINING CT")
    log.info("=" * 60)

    ct_cfg    = cfg["ct"]
    data_cfg  = cfg["data"]
    train_cfg = cfg["training"]
    labels_cfg = cfg["labels"]

    label_cols = labels_cfg["primary"]
    meta_cols  = labels_cfg["metadata"] if use_metadata else None
    meta_dim   = len(meta_cols) if meta_cols else 0

    # ── Data ─────────────────────────────────────────────────────────────────
    train_loader, val_loader, test_loader, label_cols = make_ct_dataloaders(
        cohort_csv=data_cfg["cohort_ct"].replace(".csv", "_preprocessed.csv"),
        prep_dir=data_cfg["prep_dir"] + "ct",
        label_cols=label_cols,
        meta_cols=meta_cols,
        val_frac=data_cfg["val_frac"],
        test_frac=data_cfg["test_frac"],
        batch_size=ct_cfg["batch_size"],
        num_workers=data_cfg["num_workers"],
        crop_size=tuple(ct_cfg["input_size"]),
        seed=cfg["project"]["seed"],
    )

    # ── Model ─────────────────────────────────────────────────────────────────
    model = CTSwinClassifier(
        num_labels=len(label_cols),
        img_size=tuple(ct_cfg["input_size"]),
        feature_size=48,
        dropout=0.3,
        pretrained_weights="weights/swin_unetr_btcv.pt",
        meta_dim=meta_dim,
    )

    loss_cfg = ct_cfg["loss"]
    loss_fn  = AsymmetricLoss(
        gamma_neg=loss_cfg["gamma_neg"],
        gamma_pos=loss_cfg["gamma_pos"],
        clip=loss_cfg["clip"],
    )

    sched_cfg = ct_cfg["scheduler"]
    module = MultiLabelModule(
        model=model,
        label_names=label_cols,
        loss_fn=loss_fn,
        lr=ct_cfg["optimizer"]["lr"],
        weight_decay=ct_cfg["optimizer"]["weight_decay"],
        warmup_epochs=sched_cfg["warmup_epochs"],
        max_epochs=sched_cfg["max_epochs"],
    )

    # ── Logger ────────────────────────────────────────────────────────────────
    log_cfg = cfg["logging"]
    if log_cfg["logger"] == "wandb":
        try:
            from lightning.pytorch.loggers import WandbLogger
            logger = WandbLogger(
                project=log_cfg["project"],
                name=cfg["project"]["run_name"] + "_ct",
            )
        except ImportError:
            from lightning.pytorch.loggers import CSVLogger
            logger = CSVLogger("logs/", name="ct")
    else:
        from lightning.pytorch.loggers import CSVLogger
        logger = CSVLogger("logs/", name="ct")

    # ── Callbacks ─────────────────────────────────────────────────────────────
    es_cfg   = train_cfg["early_stopping"]
    ckpt_cfg = train_cfg["checkpointing"]

    callbacks = [
        EarlyStopping(monitor=es_cfg["monitor"], patience=es_cfg["patience"], mode=es_cfg["mode"]),
        ModelCheckpoint(
            monitor=ckpt_cfg["monitor"],
            mode=ckpt_cfg["mode"],
            save_top_k=ckpt_cfg["save_top_k"],
            dirpath=ckpt_cfg["dirpath"] + "ct/",
            filename="ct_{epoch:02d}-val_mAP_{val/mAP:.3f}",
        ),
        LearningRateMonitor(logging_interval="epoch"),
    ]

    # ── Trainer ───────────────────────────────────────────────────────────────
    trainer = L.Trainer(
        max_epochs=sched_cfg["max_epochs"],
        accelerator=train_cfg["accelerator"],
        devices=train_cfg["devices"],
        precision=train_cfg["precision"],
        accumulate_grad_batches=ct_cfg["accumulate_grad_batches"],
        callbacks=callbacks,
        logger=logger,
        log_every_n_steps=log_cfg["log_every_n_steps"],
    )

    trainer.fit(module, train_loader, val_loader, ckpt_path=resume)

    trainer.test(module, test_loader, ckpt_path="best")

    if ct_cfg.get("threshold_tuning", True):
        device = "cuda" if train_cfg["devices"] > 0 else "cpu"
        thresholds = tune_thresholds(module.model, val_loader, label_cols, device=device)
        out_path = Path(ckpt_cfg["dirpath"]) / "ct_thresholds.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            import json
            json.dump(thresholds, f, indent=2)
        log.info(f"Thresholds saved → {out_path}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config",       default="configs/config.yaml")
    p.add_argument("--modality",     choices=["cxr", "ct", "both"], default="both")
    p.add_argument("--use-metadata", action="store_true",
                   help="Fuse tabular comorbidity features into classifier head")
    p.add_argument("--resume",       default=None,
                   help="Path to checkpoint to resume from")
    return p.parse_args()


def main():
    args = parse_args()
    cfg  = load_config(args.config)

    L_available = True
    try:
        import lightning
    except ImportError:
        log.error("Install PyTorch Lightning: pip install lightning")
        sys.exit(1)

    if args.modality in ("cxr", "both"):
        train_cxr(cfg, use_metadata=args.use_metadata, resume=args.resume)

    if args.modality in ("ct", "both"):
        train_ct(cfg, use_metadata=args.use_metadata, resume=args.resume)

    log.info("\nAll done. Checkpoints in checkpoints/")


if __name__ == "__main__":
    main()
