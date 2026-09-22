"""Evaluate every registered classifier (convnext, swin, densenet, ensemble)
on the held-out patient split, replicating train.py's split logic, the MIDRC
loss masks and the serving preprocess() geometry exactly. That makes the
numbers directly comparable to the val AUCs logged to wandb.

Usage (run from the repo root):
    python ml/model/evaluate/evaluate_models.py --split test
    python ml/model/evaluate/evaluate_models.py --models convnext densenet --limit 256
    python ml/model/evaluate/evaluate_models.py --csv evaluate_results.csv
"""
import argparse
import os
import sys
import time

# MPS safety, same as train.py: cap the memory pool so a long eval never grows
# into swap (24 GB unified RAM). Must be set BEFORE torch is imported.
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.55"
os.environ["PYTORCH_MPS_LOW_WATERMARK_RATIO"] = "0.0"

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO_ROOT, "services", "model-api"))
from models_registry import CLASSIFIER_REGISTRY  # noqa: E402

ALL_CLASSES = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema", "Effusion",
    "Emphysema", "Fibrosis", "Hernia", "Infiltration", "Mass", "Nodule",
    "Pleural_Thickening", "Pneumonia", "Pneumothorax", "Covid",
]
COVID_IDX = ALL_CLASSES.index("Covid")


def build_mask_matrix(frame):
    # Mirrors train.py: MIDRC rows only carry a verified Covid label, so the
    # other 14 classes are masked out of every metric for those rows.
    is_midrc = frame["img_path"].str.contains("midrc", case=False, na=False).to_numpy()
    masks = np.ones((len(frame), len(ALL_CLASSES)), dtype=np.float32)
    masks[is_midrc, :] = 0.0
    masks[is_midrc, COVID_IDX] = 1.0
    return masks


def load_split(csv_path, split, limit):
    df = pd.read_csv(csv_path, low_memory=False)
    df["patient_id"] = df["patient_id"].astype(str)

    bad_images_file = os.path.join(REPO_ROOT, "data_hybrid", "bad_images.tsv")
    if os.path.exists(bad_images_file) and os.path.getsize(bad_images_file) > 0:
        bad = pd.read_csv(bad_images_file, sep="\t", header=None, usecols=[0])[0].tolist()
        df = df[~df["img_path"].isin(bad)].reset_index(drop=True)

    df["stratify_key"] = df["Covid"].astype(str) + "_" + df["Effusion"].astype(str)
    patient_labels = (df.groupby("patient_id")["stratify_key"].first().to_dict())

    train_val_patients, test_patients = train_test_split(
        list(patient_labels), test_size=0.1, random_state=42,
        stratify=np.array(list(patient_labels.values()), dtype=str),
    )
    train_patients, val_patients = train_test_split(
        train_val_patients, test_size=0.111, random_state=42,
        stratify=np.array([patient_labels[p] for p in train_val_patients], dtype=str),
    )
    if split == "test":
        df_split = df[df["patient_id"].isin(test_patients)].reset_index(drop=True)
    elif split == "val":
        df_split = df[df["patient_id"].isin(val_patients)].reset_index(drop=True)
    else:
        raise ValueError(f"unknown split '{split}' (choose 'test' or 'val')")

    if limit:
        df_split = df_split.iloc[:limit].reset_index(drop=True)
    return df_split


class EvalDataset(Dataset):
    def __init__(self, dataframe):
        self.df = dataframe.reset_index(drop=True)
        self.mask_matrix = build_mask_matrix(self.df)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img = Image.open(row["img_path"]).convert("RGB")
        labels = torch.tensor(row[ALL_CLASSES].values.astype("float32"), dtype=torch.float32)
        mask = torch.tensor(self.mask_matrix[idx], dtype=torch.float32)
        return img, labels, mask


def _collate(batch):
    # Raw PIL images cannot be collated by torch's default collate; keep the
    # batch as a plain list so the eval loop can run each model's preprocess.
    return batch


def predict(model_id, loader, device, quiet=False):
    model = CLASSIFIER_REGISTRY[model_id]()
    model.eval()
    is_ensemble = model_id == "ensemble"

    all_labels, all_preds, all_masks = [], [], []
    t0 = time.time()
    for items in tqdm(loader, desc=f"{model_id:>8}", leave=True,
                      ncols=100, disable=quiet):
        labels = np.stack([it[1].numpy() for it in items])
        masks = np.stack([it[2].numpy() for it in items])
        pil_batch = [it[0] for it in items]
        if is_ensemble:
            # Batch per member instead of one image at a time: each member sees
            # its OWN input geometry, so stack the batch at the member level.
            # Averaging the member sigmoid probabilities is exactly what the
            # served EnsembleChestModel.forward does -- just ~100x faster.
            member_preds = []
            for member in model.models:
                member_preprocess = member.preprocess(apply_normalize=True)
                with torch.no_grad():
                    tensors = torch.stack([member_preprocess(p) for p in pil_batch])
                    member_preds.append(
                        torch.sigmoid(member(tensors.to(device))).cpu().numpy()
                    )
            preds = np.mean(np.stack(member_preds), axis=0)
        else:
            preprocess = model.preprocess(apply_normalize=True)
            with torch.no_grad():
                tensors = torch.stack([preprocess(p) for p in pil_batch])
                preds = torch.sigmoid(model(tensors.to(device))).detach().cpu().numpy()
        all_labels.append(labels)
        all_preds.append(preds)
        all_masks.append(masks)
    return (np.vstack(all_labels), np.vstack(all_preds),
            np.vstack(all_masks), time.time() - t0)


def compute_metrics(labels, preds, masks):
    class_aucs = {}
    for i, name in enumerate(ALL_CLASSES):
        known = masks[:, i] == 1
        if known.sum() < 2 or len(np.unique(labels[known, i])) < 2:
            class_aucs[name] = np.nan
            continue
        class_aucs[name] = roc_auc_score(labels[known, i], preds[known, i])

    metric_means = {"P@0.5": [], "R@0.5": [], "F1@0.5": [], "Acc@0.5": []}
    for i in range(len(ALL_CLASSES)):
        known = masks[:, i] == 1
        y, yp = labels[known, i], (preds[known, i] >= 0.5).astype(int)
        if known.sum() < 2 or len(np.unique(y)) < 2:
            continue
        p, r, f1, _ = precision_recall_fscore_support(y, yp, zero_division=0)
        metric_means["P@0.5"].append(float(p[1]))
        metric_means["R@0.5"].append(float(r[1]))
        metric_means["F1@0.5"].append(float(f1[1]))
        metric_means["Acc@0.5"].append(float((y == yp).mean()))

    aucs = [v for v in class_aucs.values() if not np.isnan(v)]

    # Global (micro) metrics: every known (image, class) pair counts as one
    # independent example, pooled across all conditions. This is the single
    # "overall performance" answer the user sees first; macro stays next to it.
    known_all = masks == 1
    y_all = labels[known_all]
    p_all = preds[known_all]
    micro_auc = np.nan
    if len(np.unique(y_all)) >= 2:
        micro_auc = float(roc_auc_score(y_all, p_all))
    yp_all = (p_all >= 0.5).astype(int)
    micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(
        y_all, yp_all, average="micro", zero_division=0
    )
    micro_acc = float((y_all == yp_all).mean())
    macro_row = {k: float(np.mean(v)) for k, v in metric_means.items()}
    return {
        "class_aucs": class_aucs,
        "macro_auc": float(np.mean(aucs)),
        "num_aucs": len(aucs),
        "macro": macro_row,
        "micro_auc": micro_auc,
        "micro": {
            "P@0.5": float(micro_p),
            "R@0.5": float(micro_r),
            "F1@0.5": float(micro_f1),
            "Acc@0.5": micro_acc,
        },
        "known_pairs": int(known_all.sum()),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate registered classifiers on the held-out split.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--models", nargs="*", default=None,
        help="model ids to evaluate (default: all registered ids)",
    )
    parser.add_argument(
        "--split", choices=["test", "val"], default="test",
        help="patient split to evaluate; 'test' (default) are held-out patients "
             "excluded from training AND validation, 'val' were seen during training",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="evaluate only the first N rows of the split (smoke tests)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=64,
        help="images decoded per loader iteration",
    )
    parser.add_argument(
        "--csv", default=None,
        help="write the per-model per-class AUC table to this CSV path",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="disable progress bars (clean logs for background runs)",
    )
    parser.add_argument(
        "--csv-path", default=None, help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    model_ids = args.models or sorted(CLASSIFIER_REGISTRY)

    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )
    workers = int(os.environ.get("TRAIN_WORKERS", "1"))

    df_split = load_split(
        os.path.join(REPO_ROOT, "data_hybrid", "combined_master.csv"),
        split=args.split, limit=args.limit,
    )
    loader = DataLoader(
        EvalDataset(df_split), batch_size=args.batch_size, shuffle=False,
        num_workers=workers, collate_fn=_collate,
        pin_memory=(device.type == "cuda"),
    )
    print(f"[eval] device={device} "
          f"split={args.split} -> "
          f"{'held-out TEST patients (never used for training or validation)' if args.split == 'test' else 'VAL patients (were seen during training)'}")
    print(f"[eval] patients={df_split['patient_id'].nunique()} images={len(df_split)} "
          f"models={', '.join(model_ids)}")
    print(f"[eval] a MIDRC image only counts for Covid (mask=1); "
          f"its other 14 classes are excluded from every metric.")

    print("\nEvaluating...")
    results, auc_table = {}, {}
    for model_id in model_ids:
        labels, preds, masks, dt = predict(model_id, loader, device, quiet=args.quiet)
        results[model_id] = compute_metrics(labels, preds, masks)
        results[model_id]["images"] = len(labels)
        results[model_id]["time_min"] = dt / 60.0
        auc_table[model_id] = results[model_id]["class_aucs"]
        r = results[model_id]
        print(f"[done] {model_id:>8}  macro-AUC={r['macro_auc']:.4f}  "
              f"micro-AUC={r['micro_auc']:.4f}  micro-F1@0.5={r['micro']['F1@0.5']:.3f}  "
              f"(t={r['time_min']:.1f} min)", flush=True)

    print("\nPer-class AUROC (rows = models, cols = classes):")
    auc_df = pd.DataFrame(auc_table).T
    print(auc_df.round(4).to_string())

    csv_out = args.csv or args.csv_path
    if csv_out:
        summary_rows = []
        for model_id in model_ids:
            r = results[model_id]
            m = r["micro"]
            row = {
                "model": model_id, "images": r["images"], "time_min": round(r["time_min"], 2),
                "macro_auc": round(r["macro_auc"], 4), "micro_auc": round(r["micro_auc"], 4),
                "micro_P@0.5": round(m["P@0.5"], 4), "micro_R@0.5": round(m["R@0.5"], 4),
                "micro_F1@0.5": round(m["F1@0.5"], 4), "micro_Acc@0.5": round(m["Acc@0.5"], 4),
            }
            summary_rows.append(row)
        with open(csv_out, "w") as f:
            auc_df.round(6).to_csv(f)
            f.write("\n\n# General/overall performance (pooled across all conditions)\n")
            pd.DataFrame(summary_rows).round(6).to_csv(f, index=False)
        print(f"\nPer-class table + overall summary written to {csv_out}")

    print("\nSummary: overall performance across ALL conditions")
    print(f"{'model':>8}  {'macro-AUC':>9}  {'micro-AUC':>9}  {'micro-P@.5':>10}  "
          f"{'micro-R@.5':>10}  {'micro-F1':>8}  {'micro-Acc':>8}  {'images':>7}  {'time(min)':>9}")
    for model_id in model_ids:
        r = results[model_id]
        m = r["micro"]
        print(f"{model_id:>8}  {r['macro_auc']:.4f}       {r['micro_auc']:>9.4f}  "
              f"{m['P@0.5']:>10.3f}  {m['R@0.5']:>10.3f}  {m['F1@0.5']:>8.3f}  "
              f"{m['Acc@0.5']:>8.3f}  {r['images']:>7}  {r['time_min']:.1f}")

    print("\nMacro per-class averages (mean over conditions):")
    print(f"{'model':>8}  {'P@0.5':>6}  {'R@0.5':>6}  {'F1@0.5':>6}  {'Acc@0.5':>7}")
    for model_id in model_ids:
        t = results[model_id]["macro"]
        print(f"{model_id:>8}  {t['P@0.5']:.3f}   {t['R@0.5']:.3f}   {t['F1@0.5']:.3f}   {t['Acc@0.5']:.3f}")


if __name__ == "__main__":
    main()