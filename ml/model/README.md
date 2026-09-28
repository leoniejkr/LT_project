# Machine Learning Model

The 15-finding multi-label chest X-ray classifier: trained locally on the hybrid
NIH + MIDRC dataset, then served as a standalone container that the Go backend
calls per uploaded image. Grad-CAM heatmaps and the per-class confidence scores
the UI shows come out of the same service.

**Offline — build once**

```
NIH + MIDRC ──► construct_data/ ──► combined_master.csv ──► train/ ──► checkpoints/*.pth
```

`evaluate/` scores those checkpoints on the held-out test patients, importing
the served models through `services/model-api` rather than re-implementing them.

**Runtime — every uploaded image**

```
checkpoints/*.pth ──► services/model-api ──► POST /predict ──► Go backend ──► UI
```

## Submodules

| Folder | What it does | Docs |
|--------|--------------|------|
| [`construct_data/`](construct_data/) | Downloads NIH + MIDRC, converts DICOM → PNG, fixes orientation, blends both into one labelled CSV | [README](construct_data/README.md) |
| [`construct_data/fix/`](construct_data/fix/) | MIDRC orientation correction (4-class ResNet-18) and the 1024 px working copies | [README](construct_data/fix/README.md) |
| [`train/`](train/) | Trains every backbone; declares resolution, batch size, optimizer and loss | [README](train/README.md) |
| [`evaluate/`](evaluate/) | Per-class AUROC and clinical metrics on the held-out test patients, plus threshold tuning | [README](evaluate/README.md) |

The model predicts 15 findings per image — `Atelectasis`, `Cardiomegaly`,
`Consolidation`, `Edema`, `Effusion`, `Emphysema`, `Fibrosis`, `Hernia`,
`Infiltration`, `Mass`, `Nodule`, `Pleural_Thickening`, `Pneumonia`,
`Pneumothorax`, `Covid` — as raw sigmoid scores. What the UI shows is decided by
the frontend decision-mode threshold.

## Checkpoints

`train.py` writes a plain `state_dict` to `--output`. The deployed ones live in
`checkpoints/` at the repo root and are mirrored one-to-one by the classes in
`services/model-api/model.py`, which are loaded with `strict=True`. All five ship
via **Git LFS**, so `git lfs pull` makes every selectable model work in a fresh
clone.

| Checkpoint | Model id | Size |
|------------|----------|------|
| `covnext348.pth` | `convnext` (default) | 334 MB |
| `swin-224px_final.pth` | `swin` | 332 MB |
| `densenet-224px_final.pth` | `densenet` | 27 MB |
| `convnext-224px_final_numero1.pth` | `convnext_ensemble` member | 334 MB |
| `convnext21k-224px_final.pth` | `convnext_ensemble` member | 334 MB |

Architecture, pre-training source and `INPUT_SIZE` per model are in the
[train README](train/README.md#models).

## How the model is integrated into the app

- **Ship** — the served checkpoints live in `checkpoints/` and are mounted
  read-only into the `modelling` service by
  [`docker-compose.yaml`](../../docker-compose.yaml), which also binds each id to
  its file through env vars — see the root
  [README](../../README.md#how-to-run-and-start-the-application).
- **Select** — the frontend sends a model id
  ([`models.ts`](../../frontend/src/lib/models.ts));
  [`models_registry.py`](../../services/model-api/models_registry.py) resolves it
  to a factory in [`model.py`](../../services/model-api/model.py), which
  strict-loads and caches the model, soft-voting member probabilities for the
  ensembles. Described in the frontend
  [README](../../frontend/README.md#communication-with-the-backend).
- **Serve** — frontend → Go backend → `POST /predict` on the modelling service →
  per-image confidences and Grad-CAM heatmaps, which the backend stores and the
  UI renders. Walkthrough in the root
  [README](../../README.md#user-centric-workflow).

The serving class must mirror the training class (backbone, head, `pos_weight` —
the checkpoint loads `strict=True`) and preprocess with the same `INPUT_SIZE` and
dataset mean/std, which is why the geometry is declared per model
([train README](train/README.md#variable-input-resolution)).
