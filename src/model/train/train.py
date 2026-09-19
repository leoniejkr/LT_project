import contextlib
import json
import os
import argparse
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision.transforms import v2
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score  
from PIL import Image
from models.chest_model import ChestModel
from models.ViT_model import SwinTransformerChestModel
import wandb
from tqdm import tqdm

# 1. Classes & Global Configurations
ALL_CLASSES = ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Effusion', 
               'Emphysema', 'Fibrosis', 'Hernia', 'Infiltration', 'Mass', 'Nodule', 
               'Pleural_Thickening', 'Pneumonia', 'Pneumothorax', 'Covid']

config = {
    "batch_size": None,  # None -> use selected model's BATCH_SIZE (see below)
    "epochs": 5,
    "backbone_lr": 1e-5,
    "classifier_lr": 1e-4,
    "dataset": "NIH-MIDRC-Hybrid-PatientContext",
    "resolution": None,  # None -> use selected model's INPUT_SIZE
    "use_amp": False,    # FP16 autocast. Benchmarked on MPS (Swin-B@224): 1369 ms/step vs
                         # 1091 ms/step fp32 -> SLOWER (~25%) on this Mac, so off by default.
                         # Flip to True if you run on CUDA or a machine where fp16 wins.
    "checkpoint": None,  # None -> auto: "<model>-<resolution>px.pth"
    "wandb_name": None,  # None -> auto: "<model>-<resolution>px"
}

# ── Architecture selection ────────────────────────────────────────────────────
# Every model class declares its expected INPUT_SIZE and a sensible BATCH_SIZE;
# transforms, resolution and the checkpoint name are derived from the chosen
# class automatically. Choose at runtime, e.g.:
#   python src/model/train/train.py --model convnext
#   python src/model/train/train.py --model swin            (default)
#   MODEL=convnext python src/model/train/train.py
MODEL_CLASSES = {
    "convnext": ChestModel,
    "swin": SwinTransformerChestModel,
}
_parser = argparse.ArgumentParser(description="Train the chest X-ray classifier.")
_parser.add_argument(
    "--model", choices=list(MODEL_CLASSES), default=os.getenv("MODEL", "swin"),
    help="Backbone architecture to train (default: %(default)s)"
)
_parser.add_argument(
    "--resume", default=None,
    help="Path to '<checkpoint>_trainstate.pt' from an interrupted run to "
         "continue training from the last saved epoch instead of restarting."
)
_parser.add_argument(
    "--epochs", type=int, default=config["epochs"],
    help="Number of training epochs (default: %(default)s)"
)
_args = _parser.parse_known_args()[0]
MODEL = _args.model
RESUME = _args.resume
config["epochs"] = _args.epochs
MODEL_CLASS = MODEL_CLASSES[MODEL]

# Resolution and batch size are model-specific: `INPUT_SIZE` / `BATCH_SIZE` on
# each model class. Transforms are built from the selected model so we never
# squeeze/downsample to a size that might not fit the backbone. Override per run
# via the config dict above.
RESOLUTION = config["resolution"] if config["resolution"] else MODEL_CLASS.INPUT_SIZE
BATCH_SIZE = config["batch_size"] if config["batch_size"] else MODEL_CLASS.BATCH_SIZE
CHECKPOINT_NAME = config.get("checkpoint") or f"{MODEL}-{RESOLUTION}px"
WANDB_NAME = config.get("wandb_name") or f"{MODEL}-{RESOLUTION}px"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))

# ── DataLoader tuning (Apple Silicon / MPS) ──────────────────────────────────
# pin_memory only helps on CUDA; on MPS/CPU it is a no-op and can even slow the
# transfer under unified memory, so keep it False outside CUDA.
PIN_MEMORY = DEVICE.type == "cuda"
# Workers parallelize image decoding + transforms (the CPU side). Tune with the
# TRAIN_WORKERS env var; persistent_workers keeps the worker processes alive
# between epochs instead of re-importing torch (~250 MB each) every epoch.
WORKERS = int(os.getenv("TRAIN_WORKERS", "4"))
PERSISTENT_WORKERS = WORKERS >= 1

# ── Automatic Mixed Precision (FP16 autocast) ────────────────────────────────
# MPS supports autocast but has no GradScaler, so we rely on autocast only. On a
# loss that turns non-finite the batch is skipped (existing guard catches it).
USE_AMP = config.get("use_amp", True) and DEVICE.type in ("cuda", "mps")
amp_ctx = torch.autocast(device_type=DEVICE.type, dtype=torch.float16) if USE_AMP else contextlib.nullcontext()

# Aspect-preserving resize + padding: images keep their true cardiothoracic
# proportions (squashing to a square would distort anatomy and hurt classes
# like Cardiomegaly). We scale the LONGER side down to `size`, then pad the
# shorter side to fill the square with black. Black is the natural background
# of a radiograph (air outside the body) and stays consistent with the fill=0
# used by the RandomRotation/RandomAffine augmentations.
# Fixing the longer side guarantees EVERY output is exactly (size, size).
# NOTE: these must live at module level so DataLoader workers (spawn) can
# pickle them — they can NOT be defined inside __main__. They run on CHW
# tensors (right after v2.ToImage()) and use the C++-optimized v2 functional
# ops, which is the main DataLoader throughput win on Apple Silicon.
class ResizeLongest:
    def __init__(self, size):
        self.size = size

    def __call__(self, img):
        c, h, w = img.shape
        scale = self.size / max(h, w)
        new_h, new_w = round(h * scale), round(w * scale)
        return v2.functional.resize(img, (new_h, new_w), antialias=True)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.size})"


class SquarePad:
    def __init__(self, fill=0):
        self.fill = fill

    def __call__(self, img):
        c, h, w = img.shape
        if h == w:
            return img
        max_side = max(h, w)
        pad_l = (max_side - w) // 2
        pad_r = max_side - w - pad_l
        pad_t = (max_side - h) // 2
        pad_b = max_side - h - pad_t
        return v2.functional.pad(img, (pad_l, pad_t, pad_r, pad_b), fill=self.fill)

    def __repr__(self):
        return f"{self.__class__.__name__}(fill={self.fill})"


def load_dataset_stats(stats_path="src/model/train/dataset_stats.json"):
    if os.path.exists(stats_path):
        with open(stats_path) as f:
            stats = json.load(f)
        mean, std = stats["mean"], stats["std"]
        print(f"Loaded dataset normalization: mean={mean}, std={std}")
        return mean, std
    else:
        print(f"WARNING: {stats_path} not found. Using ImageNet defaults.")
        print(f"Run: python src/model/train/compute_dataset_stats.py")
        return [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]


# # 2. Patient Context Multi-Image Dataset
# class PatientContextMultiViewDataset(Dataset):
#     def __init__(self, dataframe, class_list, transform=None):
#         self.df = dataframe.reset_index(drop=True)
#         self.class_list = class_list
#         self.transform = transform
        
#         self.patient_image_groups = self.df.groupby('patient_id')['img_path'].apply(list).to_dict()

#     def __len__(self):
#         return len(self.df)

#     def __getitem__(self, idx):
#         row = self.df.iloc[idx]
#         pid = str(row['patient_id'])
#         primary_path = row['img_path']
        
#         img_primary = Image.open(primary_path).convert('RGB')
        
#         all_patient_images = self.patient_image_groups.get(pid, [primary_path])
#         alternative_images = [path for path in all_patient_images if path != primary_path]
        
#         if len(alternative_images) > 0:
#             context_path = alternative_images[0]
#             img_context = Image.open(context_path).convert('RGB')
#         else:
#             img_context = Image.new('RGB', img_primary.size, (0, 0, 0))
            
#         labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        
#         if self.transform:
#             img_primary = self.transform(img_primary)
#             img_context = self.transform(img_context)
            
#         return img_primary, img_context, labels

# 3. Simplified Single-View Dataset
class SingleViewXRayDataset(Dataset):
    def __init__(self, dataframe, class_list, transform=None, mask_matrix=None):
        self.df = dataframe.reset_index(drop=True)
        self.class_list = class_list
        self.transform = transform
        self.mask_matrix = mask_matrix

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        img = Image.open(row['img_path']).convert('RGB')
        labels = torch.tensor(row[self.class_list].values.astype('float32'), dtype=torch.float32)
        mask = torch.ones(len(self.class_list), dtype=torch.float32)
        if self.mask_matrix is not None:
            mask = torch.tensor(self.mask_matrix[idx], dtype=torch.float32)
        
        if self.transform:
            img = self.transform(img)
            
        return img, labels, mask


if __name__ == '__main__':
    # ── wandb reconnect hardening ──────────────────────────────────────────
    # wandb pushes metrics through a background thread that retries network
    # sends with exponential backoff when the connection drops. The defaults
    # give up quickly; raise them so a multi-hour training keeps reconnecting
    # (up to 2h delay between attempts, effectively never exhausting retries)
    # instead of silently dropping the run after a short network blip.
    os.environ.setdefault("WANDB_RETRY_MIN_TIMEOUT", "10")
    os.environ.setdefault("WANDB_RETRY_MAX_TIMEOUT", "7200")
    os.environ.setdefault("WANDB_RETRY_NUMBER", "99999")

    wandb.init(
        project="hybrid-xray-covid", 
        name=WANDB_NAME, 
        config=config,
        settings=wandb.Settings(start_method="fork")
    )

    # 4. Stratified Patient Splitting (No Data Leaks)
    # NOTE: pandas 3.x defaults to Arrow-backed DataFrames; sklearn (and some
    # pandas ops) expect plain numpy data. Force everything to plain NumPy
    # arrays/str right away to avoid Arrow-specific indexing errors.
    df = pd.read_csv("data_hybrid/combined_master.csv", low_memory=False)
    df['patient_id'] = df['patient_id'].astype(str)

    # 4a. Drop known-corrupt/truncated images (produced by verify_images.py).
    # A single truncated PNG previously crashed a DataLoader worker and killed
    # the whole run mid-epoch.
    bad_images_file = "data_hybrid/bad_images.tsv"
    if os.path.exists(bad_images_file) and os.path.getsize(bad_images_file) > 0:
        bad = pd.read_csv(bad_images_file, sep="\t", header=None, usecols=[0])[0].tolist()
        n_bad = len(bad)
        df = df[~df['img_path'].isin(bad)].reset_index(drop=True)
        print(f"Excluding {n_bad} known-corrupt images from dataset ({len(df)} remaining).")

    # 4b. Partial-label (loss) masks.
    # MIDRC rows only carry a Covid annotation; the other 14 findings were never
    # extracted, so 0 is "unknown", NOT a verified negative. Masking these classes
    # out of the loss prevents the model from being taught that a Covid image is
    # e.g. never Pneumonia or Effusion. NIH rows are fully labelled -> all 1s.
    covid_idx = ALL_CLASSES.index('Covid')

    def build_mask_matrix(frame):
        # MIDRC rows are identified by their img path living under a midrc folder.
        is_midrc = frame['img_path'].str.contains('midrc', case=False, na=False).to_numpy()
        masks = np.ones((len(frame), len(ALL_CLASSES)), dtype=np.float32)
        masks[is_midrc, :] = 0.0
        masks[is_midrc, covid_idx] = 1.0
        return masks

    df['stratify_key'] = df['Covid'].astype(str) + "_" + df['Effusion'].astype(str)
    patient_labels = (df.groupby('patient_id')['stratify_key'].first()
                        .to_dict())  # plain python dict: {patient_id: strat_key}

    train_val_patients, test_patients = train_test_split(
        list(patient_labels), test_size=0.1, random_state=42,
        stratify=np.array(list(patient_labels.values()), dtype=str)
    )
    train_patients, val_patients = train_test_split(
        train_val_patients, test_size=0.111, random_state=42,
        stratify=np.array([patient_labels[p] for p in train_val_patients], dtype=str)
    )

    df_train = df[df['patient_id'].isin(train_patients)].reset_index(drop=True)
    df_val = df[df['patient_id'].isin(val_patients)].reset_index(drop=True)
    df_test = df[df['patient_id'].isin(test_patients)].reset_index(drop=True)

    mask_train = build_mask_matrix(df_train)
    mask_val = build_mask_matrix(df_val)

    # 5. Dataset-specific normalization
    dataset_mean, dataset_std = load_dataset_stats()

    # 6. Medical-Grade Augmentation Space (torchvision v2, C++-optimized)
    # v2.ToImage() converts the PIL image to a CHW uint8 tensor first, then all
    # ops (incl. our ResizeLongest/SquarePad) run tensorized via v2.functional.
    train_transforms = v2.Compose([
        v2.ToImage(),
        ResizeLongest(RESOLUTION),
        SquarePad(),
        v2.RandomHorizontalFlip(p=0.5),
        v2.RandomRotation(degrees=5, fill=0),
        v2.RandomAffine(
            degrees=0,
            translate=(0.1, 0.05),
            scale=(0.85, 1.15),
            shear=5,
            fill=0
        ),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=dataset_mean, std=dataset_std)
    ])

    val_transforms = v2.Compose([
        v2.ToImage(),
        ResizeLongest(RESOLUTION),
        SquarePad(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=dataset_mean, std=dataset_std)
    ])

    train_loader = DataLoader(
        SingleViewXRayDataset(df_train, ALL_CLASSES, train_transforms, mask_train), 
        batch_size=BATCH_SIZE, 
        shuffle=True,
        num_workers=WORKERS,
        pin_memory=PIN_MEMORY,
        persistent_workers=PERSISTENT_WORKERS
    )
    val_loader = DataLoader(
        SingleViewXRayDataset(df_val, ALL_CLASSES, val_transforms, mask_val), 
        batch_size=BATCH_SIZE, 
        shuffle=False,
        num_workers=WORKERS,
        pin_memory=PIN_MEMORY,
        persistent_workers=PERSISTENT_WORKERS
    )

    # 7. Model with class-imbalance-aware loss (sqrt-scaled to prevent gradient explosion)
    class_counts = df_train[ALL_CLASSES].sum().values.astype(np.float64)
    total_samples = len(df_train)
    neg_counts = total_samples - class_counts
    pos_weights = np.sqrt(neg_counts / (class_counts + 1e-5))
    pos_weights_tensor = torch.tensor(pos_weights, dtype=torch.float32).to(DEVICE)

    model = MODEL_CLASS(
        num_classes=len(ALL_CLASSES),
        lr=config["classifier_lr"],
        backbone_factor=config["backbone_lr"] / config["classifier_lr"],
        max_epochs=config["epochs"],
        pos_weight=pos_weights_tensor,
    )
    model = model.to(DEVICE)

    wandb.watch(model, log="all", log_freq=100)

    # ChestModel.configure_optimizers() returns [optimizer_list], [scheduler_list]
    optimizers, schedulers = model.configure_optimizers()
    optimizer = optimizers[0]
    scheduler = schedulers[0]

    # 7b. Resume support: `--resume swin-224px_trainstate.pt` continues from the
    # last saved epoch (model + optimizer + scheduler states), so an interrupted
    # run never loses its progress.
    trainstate_path = f"{CHECKPOINT_NAME}_trainstate.pt"
    start_epoch = 0
    if RESUME:
        if not os.path.exists(RESUME):
            raise FileNotFoundError(f"--resume path not found: {RESUME}")
        print(f"Resuming from {RESUME} ...")
        ckpt = torch.load(RESUME, map_location=DEVICE, weights_only=False)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        scheduler.load_state_dict(ckpt["scheduler"])
        start_epoch = ckpt["epoch"] + 1
        print(f"  restored epoch {ckpt['epoch']} -> continuing at epoch {start_epoch}")

    # 8. Training Loop
    for epoch in range(start_epoch, config["epochs"]+1):
        if epoch == 0:
            print("Running baseline validation pass prior to weight optimization adjustments...")
            epoch_train_loss = 0.0
        else: 
            model.train()
            running_train_loss = 0.0
            
            train_progress = tqdm(train_loader, desc=f"Epoch {epoch}/{config['epochs']} [Train]", leave=True)
            for images, labels, masks in train_progress:
                images = images.to(DEVICE)
                labels = labels.to(DEVICE)
                masks = masks.to(DEVICE)
                
                optimizer.zero_grad()

                with amp_ctx:
                    outputs = model(images)
                    loss = model.masked_loss_fn(outputs, labels, masks)

                # A NaN/Inf loss (possible on MPS under memory pressure or on a
                # corrupt sample) must never poison the model: skip the update.
                if not torch.isfinite(loss):
                    print(f"[Warning] Non-finite loss ({loss.item()}) at "
                          f"epoch {epoch}; skipping weight update for this batch.")
                    continue

                loss.backward()
                # Grad clipping: cheap insurance against one exploding gradient
                # wiping out the whole run.
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                
                running_train_loss += loss.item() * images.size(0)
                train_progress.set_postfix(batch_loss=f"{loss.item():.4f}")
                
            epoch_train_loss = running_train_loss / len(train_loader.dataset)
        
        # Validation
        model.eval()
        running_val_loss = 0.0
        all_val_labels = []
        all_val_preds = []
        all_val_masks = []
        
        val_progress = tqdm(val_loader, desc=f"Epoch {epoch}/{config['epochs']} [Val]", leave=True)
        with torch.no_grad():
            for images, labels, masks in val_progress:
                images = images.to(DEVICE)
                labels = labels.to(DEVICE)
                masks = masks.to(DEVICE)
                
                with amp_ctx:
                    outputs = model(images)
                    loss = model.masked_loss_fn(outputs, labels, masks)
                running_val_loss += loss.item() * images.size(0)
                
                probs = torch.sigmoid(outputs)
                all_val_labels.append(labels.cpu().numpy())
                all_val_preds.append(probs.cpu().numpy())
                all_val_masks.append(masks.cpu().numpy())
                
        epoch_val_loss = running_val_loss / len(val_loader.dataset)
        
        if epoch > 0:
            scheduler.step()
        
        # AUC is computed per class on the entries whose label is KNOWN
        # (mask == 1), so unknown MIDRC labels never count as fake negatives.
        all_val_labels = np.vstack(all_val_labels)
        all_val_preds = np.vstack(all_val_preds)
        all_val_masks = np.vstack(all_val_masks)

        class_aucs = {}
        for i, class_name in enumerate(ALL_CLASSES):
            known = all_val_masks[:, i] == 1
            if known.sum() == 0:
                class_aucs[class_name] = 0.5
                continue
            try:
                class_aucs[class_name] = roc_auc_score(
                    all_val_labels[known, i], all_val_preds[known, i]
                )
            except ValueError:
                class_aucs[class_name] = 0.5
        epoch_macro_auc = float(np.mean(list(class_aucs.values())))

        metrics_to_log = {
            "epoch": epoch,
            "train_loss": epoch_train_loss if epoch > 0 else 0.0,
            "val_loss": epoch_val_loss,
            "val_macro_auc": epoch_macro_auc
        }

        print(f"\nEpoch {epoch} Performance Summary:")
        print(f"Val Loss: {epoch_val_loss:.4f} | Macro AUC: {epoch_macro_auc:.4f}")
        
        for i, class_name in enumerate(ALL_CLASSES):
            class_auc = class_aucs[class_name]
            metrics_to_log[f"val_auc_class/{class_name}"] = class_auc
            if class_auc == 0.5 and all_val_masks[:, i].sum() == 0:
                print(f" -> {class_name}: AUC = 0.5000 (No known labels)")
            elif class_auc == 0.5:
                print(f" -> {class_name}: AUC = 0.5000 (Insufficient class instances)")
            else:
                print(f" -> {class_name}: AUC = {class_auc:.4f}")

        if epoch > 0:
            current_lrs = [param_group['lr'] for param_group in optimizer.param_groups]
            metrics_to_log["lr"] = current_lrs[0]
            torch.save(model.state_dict(), f"{CHECKPOINT_NAME}.pth")
            torch.save({
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "epoch": epoch,
            }, trainstate_path)

        print("\n")
        
        try:
            wandb.log(metrics_to_log)
        except Exception as e:
            print(f"[WandB Warning] Failed to log metrics due to network issue: {e}")
            print("Training will continue locally; wandb will attempt background reconnection.")
            print("If the connection is back, the next epoch's log will flush the queue.")

    torch.save(model.state_dict(), f"{CHECKPOINT_NAME}_final.pth")
    print(f"Model weights successfully saved locally to {CHECKPOINT_NAME}_final.pth!")

    try:
        wandb.finish()
    except Exception as e:
        # Trained weights are saved above; never let a wandb teardown failure
        # mask a completed training run.
        print(f"[WandB Warning] finish() failed (likely connectivity): {e}")
        print("Metrics may sync later via `wandb sync`.")
