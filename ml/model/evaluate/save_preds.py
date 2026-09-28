"""Dump per-image predictions for every registered classifier to NPZ so
confidence intervals can be computed later without re-running inference
(see the Caveats section of the evaluate README). Reuses
evaluate_models.predict() so the numbers are identical to
evaluate_results.csv.

Usage (run from the repo root, in the ml venv):
    python ml/model/evaluate/save_preds.py --outdir ml/model/evaluate/preds
"""
import argparse
import os
import sys

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate_models as em  # noqa: E402
from models_registry import CLASSIFIER_REGISTRY  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--split", choices=["test", "val"], default="test")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "preds"))
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    model_ids = args.models or sorted(CLASSIFIER_REGISTRY)
    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available()
        else "cpu"
    )

    df_split = em.load_split(
        os.path.join(em.REPO_ROOT, "data_hybrid", "combined_master.csv"),
        split=args.split, limit=args.limit,
    )
    loader = DataLoader(
        em.EvalDataset(df_split), batch_size=args.batch_size, shuffle=False,
        num_workers=1, collate_fn=em._collate,
    )
    os.makedirs(args.outdir, exist_ok=True)
    np.save(os.path.join(args.outdir, "patient_ids.npy"),
            df_split["patient_id"].astype(str).to_numpy())
    np.save(os.path.join(args.outdir, "img_paths.npy"),
            df_split["img_path"].astype(str).to_numpy())

    for model_id in model_ids:
        labels, preds, masks, dt = em.predict(model_id, loader, device, quiet=True)
        out = os.path.join(args.outdir, f"{model_id}.npz")
        np.savez_compressed(out, labels=labels, preds=preds, masks=masks)
        print(f"[saved] {out}  ({labels.shape[0]} imgs x {labels.shape[1]} classes) "
              f"t={dt / 60.0:.1f} min", flush=True)


if __name__ == "__main__":
    main()