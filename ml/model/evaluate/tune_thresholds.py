"""Per-class threshold tuning (as in the ConvNeXt ensemble paper) and a
clinical-metrics table.

For every model the per-class threshold is tuned by maximizing the positive-class
F1 on a grid over the VAL split; that threshold is then applied to the TEST split
to report macro/micro AUC, macro-F1, sensitivity, specificity and Youden's J.

Usage (run from the repo root, in the ml venv):
    python ml/model/evaluate/tune_thresholds.py
"""
import argparse
import os
import sys

import numpy as np
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluate_models import ALL_CLASSES  # noqa: E402

METRIC_KEYS = ["AUC", "F1", "Sens", "Spec", "J", "Acc"]


def load_npz(path):
    d = np.load(path)
    return d["labels"], d["preds"], d["masks"]


def tune_one_class(y, scores, n_ticks=201):
    """Maximize positive-class F1 on a quantile grid of scores."""
    if y.sum() < 2 or len(np.unique(y)) < 2:
        return None
    lo, hi = float(scores.min()), float(scores.max())
    if lo >= hi:
        return lo
    grid = lo + (hi - lo) * np.linspace(0, 1, n_ticks)
    best_t, best_f1 = grid[0], -1.0
    for t in grid:
        yp = (scores >= t).astype(int)
        p, r, f1, _ = precision_recall_fscore_support(
            y, yp, zero_division=0, pos_label=1)
        if f1[1] > best_f1:
            best_t, best_f1 = t, f1[1]
    return float(best_t)


def class_stats(y, scores, thr):
    """Sens, Spec, F1, Youden J, Acc on known labels at a fixed threshold."""
    if y.sum() < 2 or len(np.unique(y)) < 2:
        return None
    yp = (scores >= thr).astype(int)
    p, r, f1, _ = precision_recall_fscore_support(
        y, yp, zero_division=0, pos_label=1)
    tn = int(((y == 0) & (yp == 0)).sum())
    fp = int(((y == 0) & (yp == 1)).sum())
    spec = tn / max(tn + fp, 1)
    return {
        "AUC": float(roc_auc_score(y, scores)),
        "F1": float(f1[1]),
        "Sens": float(r[1]),
        "Spec": float(spec),
        "J": float(r[1] + spec - 1),
        "Acc": float((y == yp).mean()),
    }


def main():
    ap = argparse.ArgumentParser()
    this = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--models", nargs="*", default=[
        "convnext", "swin", "densenet", "ensemble", "convnext_ensemble"])
    ap.add_argument("--val-dir", default=os.path.join(this, "preds_val"))
    ap.add_argument("--test-dir", default=os.path.join(this, "preds"))
    ap.add_argument("--n-ticks", type=int, default=201)
    ap.add_argument("--out", default=os.path.join(this, "tuned_clinical_metrics.csv"))
    args = ap.parse_args()

    print(f"{'model':16s}", *(f"{k:>8s}" for k in ["macro-" + m for m in METRIC_KEYS] + ["micro-" + m for m in METRIC_KEYS]))
    rows = []
    for mid in args.models:
        Lv, Pv, Mv = load_npz(os.path.join(args.val_dir, f"{mid}.npz"))
        Lt, Pt, Mt = load_npz(os.path.join(args.test_dir, f"{mid}.npz"))
        res_per_class = {}
        macro = {k: [] for k in METRIC_KEYS}
        for i, name in enumerate(ALL_CLASSES):
            vk = Mv[:, i] == 1
            t = tune_one_class(Lv[vk, i], Pv[vk, i], args.n_ticks)
            if t is None:
                continue
            tk = Mt[:, i] == 1
            s = class_stats(Lt[tk, i], Pt[tk, i], t)
            if s is None:
                continue
            for k in METRIC_KEYS:
                macro[k].append(s[k])
            res_per_class[name] = (t, s)

        # micro (pooled known pairs, each class at its own tuned threshold)
        thr_all = np.full((Mt.shape[1],), np.nan, dtype=np.float64)
        for i, name in enumerate(ALL_CLASSES):
            if name in res_per_class:
                thr_all[i] = res_per_class[name][0]
        keep = (Mt == 1) & ~np.isnan(thr_all)[None, :]
        yp_all = (Pt >= thr_all[None, :]).astype(int)
        y_all = Lt[keep].astype(int)
        p_all = Pt[keep]
        yp_flat = yp_all[keep]
        micro_auc = float(roc_auc_score(y_all, p_all)) if len(np.unique(y_all)) >= 2 else np.nan
        _, micro_r, micro_f1, _ = precision_recall_fscore_support(
            y_all, yp_flat, zero_division=0, average="micro")
        tn = int(((y_all == 0) & (yp_flat == 0)).sum())
        fp = int(((y_all == 0) & (yp_flat == 1)).sum())
        micro_sens = float(micro_r)
        micro_spec = tn / max(tn + fp, 1)
        micro_acc = float((y_all == yp_flat).mean())
        micro = {"AUC": micro_auc, "F1": micro_f1, "Sens": micro_sens,
                 "Spec": micro_spec, "J": float(micro_sens + micro_spec - 1),
                 "Acc": micro_acc}

        row = {"model": mid}
        for k in METRIC_KEYS:
            row[f"macro_{k}"] = float(np.nanmean(macro[k])) if macro[k] else np.nan
            row[f"micro_{k}"] = micro[k]
        rows.append(row)

        vals = [f"{row[f'macro_{k}']:.3f}" for k in METRIC_KEYS]
        vals += [f"{row[f'micro_{k}']:.3f}" for k in METRIC_KEYS]
        print(f"{mid:16s}", *(f"{v:>8s}" for v in vals))

    import csv
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n[written] {args.out}")


if __name__ == "__main__":
    main()