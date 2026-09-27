# Model Evaluation

Measures how well the trained chest X-ray classifiers actually perform, so the
numbers in the project are backed by a reproducible measurement instead of an
assumption.

This folder answers three questions:

1. **How good is each model?** — per-condition AUROC for every registered
   classifier (`convnext`, `swin`, `densenet`, `ensemble`, `convnext_ensemble`).
2. **Is the ensemble worth it?** — the same table side by side, so the gain of
   soft-voting over the best single member is visible.
3. **Is a 0.5 threshold usable?** — clinical metrics (sensitivity, specificity,
   Youden's J) at the default threshold and at per-condition tuned thresholds.

The evaluation is **not** a separate research harness: it imports the *served*
models from `services/model-api` and runs them through the *same* preprocessing
the app uses. Anything measured here is therefore what a user gets at runtime.

---

## Protocol

### Split by patient, not by image

A patient can have several X-rays. Splitting by image would put one patient's
image in training and another's in the test set, which leaks patient-specific
information and inflates the scores. `load_split()` therefore splits on
**`patient_id`** and stratifies on the `Covid`+`Effusion` label combination
(`random_state=42`, identical to `train.py`), so the evaluation set is
reproducible and class-balanced across splits.

| Split | Patients | Images | NIH | MIDRC | Purpose |
|-------|---------:|-------:|----:|------:|---------|
| `train` | 28 563 | 80 890 | 75 442 | 5 448 | seen during training |
| `val` | 3 567 | 9 717 | 9 037 | 680 | threshold tuning |
| `test` | 3 570 | **10 151** | 9 470 | 681 | **held out — the numbers below** |

`--split test` (default) = patients never used for training *or* validation.
`--split val` = patients the model has already seen; useful only to confirm the
harness reproduces the `val_macro_auc` values logged to wandb, never for
reporting performance.

### MIDRC loss mask

MIDRC rows only carry a verified `Covid` label, so the other 14 conditions are
**unknown**, not negative. `build_mask_matrix()` sets `mask = 0` for those cells
and every metric is computed over `mask == 1` only. Without this, 681 images
would contribute 14 fake negatives each and quietly deflate the scores.

### Serving-identical inference

Each model is instantiated through `CLASSIFIER_REGISTRY` (the same factory the
API uses) and preprocessed with its **own** `INPUT_SIZE` + dataset mean/std.
`ResizeLongest` + `SquarePad` geometry therefore matches training and serving
exactly — no resize shortcut that would quietly change the results. For
ensembles, members are preprocessed individually and their sigmoid
probabilities are averaged, which is precisely what
`EnsembleChestModel.forward` does, just batched (~100x faster than the
image-at-a-time serving path).

---

## Files

| File | Role |
|------|------|
| `evaluate_models.py` | main entry point — inference + all metrics + console report |
| `save_preds.py` | dumps per-image predictions to `.npz` so metrics can be recomputed without re-running inference |
| `tune_thresholds.py` | per-condition threshold tuning on `val`, clinical metrics applied to `test` |
| `evaluate_results.csv` | full test-split report: per-condition AUROC + overall summary |
| `convnext_ensemble_fulltest.csv` | same report for the ConvNeXt-only ensemble |
| `estimate_convnext_ensemble.csv` | 2 000-image smoke run (see caveat) |
| `tuned_clinical_metrics.csv` | threshold-tuned clinical metrics |
| `preds/`, `preds_val/` | cached `labels`/`preds`/`masks` per model, test and val |

`preds/` + `preds_val/` are the source of truth for every table below: each
`.npz` holds `(images × 15)` arrays, plus `img_paths.npy` and `patient_ids.npy`
for row alignment.

---

## How to run

Run from the **repo root** in the ml venv (`torch`, `sklearn`, `pandas`,
`pillow`, `tqdm`).

```bash
# full test-split report for every registered model (writes the CSV)
python ml/model/evaluate/evaluate_models.py --split test --csv ml/model/evaluate/evaluate_results.csv

# a single model, quick smoke test on the first 256 images
python ml/model/evaluate/evaluate_models.py --models convnext --limit 256

# cache predictions for test + val (do this before tune_thresholds.py)
python ml/model/evaluate/save_preds.py --split test --outdir ml/model/evaluate/preds
python ml/model/evaluate/save_preds.py --split val  --outdir ml/model/evaluate/preds_val

# clinical metrics with per-condition thresholds tuned on val
python ml/model/evaluate/tune_thresholds.py
```

Device is auto-selected (CUDA → MPS → CPU). On Apple Silicon the MPS memory
pool is capped (`PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.55`) so a long run cannot
grow into swap on a 24 GB machine. `TRAIN_WORKERS` controls DataLoader workers
(default 1).

**Prerequisites** — `data_hybrid/combined_master.csv` and the checkpoints in
`checkpoints/`. The dataset must already exist; see
[`../train/README.md`](../train/README.md) and
[`../construct_data/`](../construct_data). Corrupt images listed in
`data_hybrid/bad_images.tsv` are dropped automatically.

---

## Results — held-out test split

**10 151 images, 3 570 patients never seen in training.** All figures verified
against the cached `preds/*.npz`.

### Overall

| Model | macro-AUC | micro-AUC | micro-P | micro-R | micro-F1 | Spec | Acc | Time |
|-------|----------:|----------:|--------:|--------:|---------:|-----:|----:|-----:|
| `convnext` (default) | 0.8546 | 0.8889 | 0.426 | 0.398 | 0.412 | 0.975 | 0.949 | 25 min |
| `swin` | 0.8492 | 0.8865 | 0.360 | 0.471 | 0.408 | 0.961 | 0.939 | 9 min |
| `densenet` | 0.8424 | 0.8820 | 0.374 | 0.433 | 0.401 | 0.966 | 0.943 | 4 min |
| **`ensemble`** (ConvNeXt+Swin+DenseNet) | **0.8575** | **0.8935** | 0.410 | 0.428 | **0.419** | 0.971 | 0.947 | 30 min |
| `convnext_ensemble` (3 ConvNeXt ckpts) | **0.8581** | 0.8909 | 0.404 | 0.428 | 0.416 | 0.971 | 0.947 | 33 min |

Runtimes are MPS on the dev machine and scale roughly with input pixels.

### Per-condition AUROC

| Condition | Positives | convnext | swin | densenet | ensemble | convnext_ens |
|-----------|----------:|---------:|-----:|---------:|---------:|-------------:|
| Atelectasis | 688 | 0.797 | 0.784 | 0.786 | 0.795 | 0.795 |
| Cardiomegaly | 321 | 0.895 | 0.895 | 0.888 | 0.903 | 0.904 |
| Consolidation | 478 | 0.812 | 0.815 | 0.812 | 0.819 | 0.820 |
| Edema | 216 | 0.927 | 0.925 | 0.923 | 0.930 | 0.931 |
| Effusion | 703 | 0.883 | 0.878 | 0.879 | 0.886 | 0.884 |
| Emphysema | 254 | 0.946 | 0.925 | 0.903 | 0.942 | 0.939 |
| Fibrosis | 163 | 0.827 | 0.813 | 0.807 | 0.825 | 0.822 |
| Hernia | **11** | 0.812 | 0.853 | 0.826 | 0.837 | 0.819 |
| Infiltration | 671 | 0.811 | 0.811 | 0.806 | 0.815 | 0.812 |
| Mass | 540 | 0.853 | 0.845 | 0.823 | 0.854 | 0.853 |
| Nodule | 625 | 0.774 | 0.733 | 0.735 | 0.761 | 0.761 |
| Pleural_Thickening | 321 | 0.807 | 0.811 | 0.792 | 0.812 | 0.812 |
| Pneumonia | 134 | 0.795 | 0.772 | 0.777 | 0.794 | 0.790 |
| Pneumothorax | 536 | 0.883 | 0.878 | 0.879 | 0.889 | 0.891 |
| Covid | 681 | 1.000\* | 1.000\* | 1.000\* | 1.000\* | 1.000\* |

\* **Not a COVID result** — see caveats.

### With per-condition tuned thresholds

Thresholds tuned on `val` (max positive-class F1 over a 201-point grid), then
applied unchanged to `test`. This is the configuration a deployment would use,
since a single 0.5 cut-off is not optimal for 15 conditions with 0.1 %–7 %
prevalence.

| Model | macro-AUC | macro-F1 | Sens | Spec | Youden's J | Acc |
|-------|----------:|---------:|-----:|-----:|-----------:|----:|
| `convnext` | 0.8546 | **0.381** | **0.485** | 0.951 | 0.436 | 0.931 |
| `swin` | 0.8492 | 0.341 | 0.461 | 0.938 | 0.400 | 0.921 |
| `densenet` | 0.8424 | 0.351 | 0.467 | 0.941 | 0.408 | 0.923 |
| `ensemble` | 0.8575 | 0.367 | 0.449 | **0.952** | 0.401 | **0.932** |
| `convnext_ensemble` | **0.8581** | 0.350 | 0.467 | 0.945 | 0.412 | 0.926 |

### Reading the numbers

- **macro-AUC is the headline.** Mean AUROC over the 15 conditions — the only
  figure that treats a rare condition like Hernia equally with a common one.
- **micro-AUC is higher** (0.89) because pooling weights every condition by its
  frequency, so common findings dominate. Useful as a single "overall" number,
  misleading as a per-condition claim.
- **micro-Acc (0.95) is not a quality score.** Only 4.4 % of known
  (image, condition) pairs are positive, so predicting "nothing" everywhere
  already scores 0.956. Accuracy is only meaningful next to specificity.
- **F1 ≈ 0.41 at 0.5** reflects genuine class imbalance plus a threshold that is
  too high for rare conditions; tuning lifts macro-F1 substantially.
- The two ensembles are statistically indistinguishable from each other
  (+0.003 macro-AUC) and only ~0.003 above `convnext` alone. The gain over the
  best single member is real but small; the honest summary is that the ensemble
  mainly buys robustness, not a step change in accuracy.
- Train-time `val_macro_auc` from wandb runs lands at 0.843–0.851, consistent
  with the 0.842–0.858 measured here — the harness reproduces training.

---

## Caveats

- **`Covid` AUROC = 1.000 is a data artifact, not a COVID result.** In the test
  split all 681 MIDRC images are `Covid = 1` and all 9 470 NIH images are
  `Covid = 0`, so the metric effectively separates *MIDRC from NIH* by
  acquisition pipeline rather than diagnosing COVID. Treat it as a source
  classifier; the mask prevents it from corrupting the other 14 conditions, but
  the 1.000 itself must not be quoted as COVID performance.
- **Rare conditions are noise.** Hernia has 11 positives in the whole test split
  and Pneumonia 134 — their AUROC carries a wide error bar, and the
  `swin` Hernia score (0.853 vs `convnext` 0.812) is not a real difference.
  `save_preds.py` exists so bootstrap confidence intervals can be added without
  re-running inference; that script (`bootstrap_ci.py`) is referenced in its
  docstring but **not yet present** in the repo.
- **The `micro-P` / `micro-R` / `micro-F1` columns in the committed CSVs are
  wrong.** `precision_recall_fscore_support(..., average="micro")` on a 1-D
  binary target degenerates to *accuracy* in the installed scikit-learn
  (verified on 1.9.0), which is why P, R, F1 and Acc were all identical
  (`0.949` for every model). The table above uses the corrected values, computed
  with `average="binary", pos_label=1`. The same pattern affects
  `tune_thresholds.py` (`micro_F1` and `micro_Sens`); the `micro_Spec` column
  there is computed manually and is correct, as are all macro columns and every
  AUROC.
- **`estimate_convnext_ensemble.csv` is not reproducible as-is.** It is a
  2 000-image `--limit` smoke run, and it includes `convnext224` / `convnext21k`
  ids that are deliberately not in `CLASSIFIER_REGISTRY`. Treat it as a scratch
  artifact, not a result.
- **Single split, no error bars.** All numbers come from one
  `random_state=42` split. Differences below ~0.01 macro-AUC are within noise.
- **Thresholds tuned on `val`, never on `test`** — the test split stays a clean
  held-out estimate. The app's adjustable GUI slider is the runtime equivalent.
