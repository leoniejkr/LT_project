# Dataset Construction

This folder turns two very different image sources into **one** consistent, balanced
and reproducible training dataset (`data_hybrid/combined_master.csv`), which is read
by training (`../train/`), evaluation (`../evaluate/`) and the model API service
(`services/model-api/`) alike.

Every script is **idempotent**: it skips work that is already done (existing PNGs,
cached downloads, an existing manifest), so an interrupted run can simply be
restarted.

---

## Why a pipeline at all?

We train a multi-label model on chest X-rays with 15 findings (14 NIH pathologies
plus COVID-19). Neither source provides that taxonomy on its own:

| | **NIH Chest X-Ray** | **MIDRC** |
|---|---|---|
| Source | Kaggle (`nih-chest-xrays/data`) | `data.midrc.org` (Gen3 API, program `Open`, project `A1`) |
| Content | ~112 000 chest X-rays, 14 pathologies, **no COVID** | COVID-19-positive chest X-rays, **only** the COVID label is reliable |
| Format | PNG, 1024×1024 | raw DICOM inside ZIP containers, up to ~4400×3610 px |
| Orientation | already standardized (head up, heart right) | **unreliable** — many images rotated by 90°/180°, metadata untrustworthy |
| Processing needed | none | DICOM decode, intensity windowing, orientation, resize |

Neither source is usable alone: NIH has no COVID, MIDRC has none of the 14
pathologies. Only the merge produces all 15 labels — which is precisely the job of
this folder.

NIH is the **reference dataset**: appearance, contrast, orientation and image level
are defined by it. The MIDRC images are processed so that they end up looking like
NIH images.

---

## Why MIDRC contributes exactly one label

MIDRC is worth its place in this dataset for COVID and nothing else. That is a
property of the data, not a shortcut in the pipeline, so it is worth spelling out.

**It is heavily COVID-skewed.** The collection is a COVID-19 imaging archive. There
are no comparable numbers of normal or non-COVID studies to draw on, so whatever we
take from it is a COVID-heavy sample by construction.

**It has no usable labels for the other 14 pathologies.** We investigated the full
node inventory (`explore/explore_available_conditions.py`, results saved in
`explore/available_conditions.txt` and `explore/available_observations.txt`):

| Gen3 node | What is actually in it |
|---|---|
| `condition` | Two distinct values only — *Post COVID-19 condition, unspecified* (835×) and *Myalgic encephalomyelitis / chronic fatigue syndrome* (38×). Both are clinical follow-up diagnoses, not image-level findings, and neither maps onto any of the 14 NIH classes. |
| `observation` | Empty. |
| `annotation`, `radiology_report` | Free-text / study-level only. No per-image structured finding that could be mapped to the NIH taxonomy. |

So a MIDRC image carries exactly one trustworthy label: *this is a COVID case*.
Everything else is **unknown, not negative** — an image tagged `Covid = 1` is not
evidence against cardiomegaly, it is simply silent about it. Treating the missing
labels as zeros would teach the model that COVID patients never have other findings,
which is both false and actively harmful.

**We looked for a better source and did not find one.** The obvious alternative —
adding a public COVID CXR dataset (e.g. the Cohen-style curated collections) to get
multi-label COVID images — was rejected: their labels come from report snippets and
subset selection, not from a radiologist-adjudicated per-image annotation, so their
label quality is not comparable to NIH. Mixing label standards would mean the 14
pathologies are measured on two different scales inside one model, and the noise
would swamp the small positive counts we already have to deal with. Two clean label
sources beat three inconsistent ones.

**Three consequences run through the whole pipeline:**

1. **The other 14 classes are masked, not zero-filled.** `train.py`'s
   `build_mask_matrix()` sets `mask = 0` for every non-COVID label of a MIDRC row and
   `1` for its COVID label, so the unknown cells contribute to neither the loss nor the
   metrics. See [`../train/README.md`](../train/README.md).
2. **MIDRC must be balanced against NIH.** Left alone, several thousand COVID images
   would outweigh the NIH pathologies and the model would mostly learn *which
   acquisition pipeline produced this image* — MIDRC and NIH differ in contrast,
   resolution and post-processing far more than most findings differ visually. This
   is why `blend_data.py` caps both sides at the same `BALANCE_N`.
3. **The `Covid` score is a source classifier, not a COVID diagnosis.** Every MIDRC
   image is `Covid = 1` and every NIH image `Covid = 0`, so the metric effectively
   separates *MIDRC from NIH* rather than diagnosing COVID. The masking in (1) keeps
   it from contaminating the other 14 conditions, but the resulting `Covid` AUROC of
   1.000 must not be quoted as COVID performance. Details in
   [`../evaluate/README.md`](../evaluate/README.md).

In short: MIDRC supplies the positive COVID class and the image-level preprocessing
work; NIH supplies the taxonomy and the ground truth. Neither alone is a dataset.

---

## Order of operations

Each step reads the output of the previous one. Run from the repo root:

```
 1. get_nih_data.py         Kaggle ──────────────────────────────►  nih_images/path.txt
 2. get_midrc_data.py       Gen3 API (metadata only) ──────────►  midrc_download_manifest.json
 3. download_midrc_data.py  Manifest ────────────────────────────►  midrc_dicoms/*.zip
 4. processing.py           DICOM ── MONAI + chest check ──────►  midrc_images/*.png
                                     + CLAHE + heuristic          midrc_processed_manifest.csv
 5. fix/                    ResNet-18 rotation fix
       train_rotation_classifier.py   (once, trained on NIH)
       fix_midrc_orientation.py  ──────────────────────────────►  midrc_fixed_images/*.png
 6. fix/resize_midrc.py      LANCZOS, longest side = 1024 ───────►  midrc_fixed_1024/*.png
 7. blend_data.py           NIH + MIDRC ── balance + merge ─────►  combined_master.csv
                                                                    │
 8. ../train/compute_dataset_stats.py ───────────────────────────►  dataset_stats.json
```

Short version to execute:

```bash
python ml/model/construct_data/get_nih_data.py
python ml/model/construct_data/get_midrc_data.py            # --force re-queries the API
python ml/model/construct_data/download_midrc_data.py       # --limit N / --dry-run for test runs
python ml/model/construct_data/processing.py                # --force-reprocess re-verifies everything

# Step 5a (needed only once): train the orientation classifier
python ml/model/construct_data/fix/train_rotation_classifier.py \
  --image-dir "$(cat data_hybrid/nih_images/path.txt)/images_001/images" \
  --out checkpoints/xray_orientation_resnet18.pth
# Step 5b: apply the classifier to the MIDRC PNGs
python ml/model/construct_data/fix/fix_midrc_orientation.py

# Step 6: I/O-friendly working copies
python ml/model/construct_data/fix/resize_midrc.py
python ml/model/construct_data/blend_data.py
```

| # | Step | Purpose | Can be skipped when … |
|---|------|---------|-----------------------|
| 1 | Fetch NIH | reference data + path pointer | the Kaggle cache is already populated |
| 2 | MIDRC metadata | filtering **before** the download | `midrc_download_manifest.json` exists |
| 3 | MIDRC download | make the raw data available locally | all ZIPs are in `midrc_dicoms/` |
| 4 | DICOM → PNG | decode, normalize, first orientation pass | all PNGs are in `midrc_images/` |
| 5 | Rotation fix | correct the remaining rotations with a CNN | `midrc_fixed_images/` is complete |
| 6 | Resize | I/O-friendly working copies | `midrc_fixed_1024/` is complete |
| 7 | Blend | balance + fusion into one CSV | never (always deterministic and rewritten) |

---

## Step 1 — `get_nih_data.py`: fetching NIH

**What happens.** `kagglehub.dataset_download("nih-chest-xrays/data")` downloads the
Kaggle dataset into the Kaggle cache. That cache path is machine-dependent, so it is
written to `data_hybrid/nih_images/path.txt`.

**Purpose.** NIH needs **no** image processing: 1024×1024, standardized orientation,
labels available as CSV. The pointer file is the entire job — it decouples the cache
path from every downstream script, so no absolute home path is hardcoded anywhere.

**Output.** `data_hybrid/nih_images/path.txt`

**Idempotency.** `kagglehub` skips already-downloaded datasets.

---

## Step 2 — `get_midrc_data.py`: MIDRC Gen3 API ingestion

**What happens.** Purely at the **metadata level** — not a single pixel is loaded.
`Gen3Auth`/`Gen3Submission` export the nodes `case`, `imaging_study` and
`cr_series_file` as TSV. The result is then filtered:

1. **Body part = chest (mandatory).** Primarily from
   `cr_series_file.body_part_examined`, alternatively via a join over
   `imaging_study`. If the field is missing from *both* tables, the script aborts —
   better to download nothing at all than hand and foot radiographs.
2. **Front-facing views only (PA/AP).** Lateral and oblique views are dropped, so the
   geometry matches the PA/AP-filtered NIH images.
3. **COVID-19-positive cases only** (`covid19_positive` = yes/true/1).
4. **Capped at `--max-covid`** (default 7000, seed 42) — the upper bound that
   balancing later works against.

**Purpose.** The filtering happens **server-side, before the download**, so only the
objects we actually need are touched (otherwise step 3 transfers tens of GiB of
discarded DICOMs). The JSON manifest serves two purposes: it is the download list
*and* the allow-list that `processing.py` iterates over — so no image can enter the
dataset that was not approved beforehand.

**Output.** `data_hybrid/midrc_download_manifest.json` with `object_id`, `file_name`,
`md5sum`, `file_size` per entry.

**Idempotency.** If the manifest exists, the API is not queried again. `--force`
forces a fresh query. Broken filter chains (in particular the body-part abort) end in
`sys.exit(1)` rather than in a silently empty dataset.

---

## Step 3 — `download_midrc_data.py`: transferring the raw data

**What happens.** `gen3-client` / `dataclient` is located, a `midrc` profile is
configured from `credentials.json`, and `download-multiple` is run with 8 parallel
workers, `--skip-completed` and the S3 protocol.

**Purpose.** Parallel, resumable bulk transfer. The raw DICOM ZIPs are kept locally —
they are the traceable source of truth from which the entire MIDRC branch can be
rebuilt at any time. `credentials.json` comes from `data.midrc.org/identity` →
"Create API key".

**Output.** `data_hybrid/midrc_dicoms/*.zip`

**Idempotency.** `--skip-completed` skips existing files. `--limit N` writes a
temporarily shortened manifest (for test runs), `--dry-run` only prints the
gen3-client command.

---

## Step 4 — `processing.py`: MONAI normalization (DICOM → PNG)

The most important step for the *consistent appearance* of the dataset. Every image
passes through:

**a) Decode & intensity windowing (MONAI)**

```python
Compose([
    LoadImage(image_only=False, reader=ITKReader()),
    EnsureChannelFirst(channel_dim='no_channel'),
    ScaleIntensityRangePercentiles(lower=0.5, upper=99.5, b_min=0, b_max=255, clip=True),
])
```

`ScaleIntensityRangePercentiles` clips the extreme 0.5 % at both ends and scales the
rest to 0–255. This removes outliers and brightness differences between scanners and
unifies the greyscale distribution. `MONOCHROME1` images (inverted rendering,
`255 - x`) are inverted back so the lungs stay dark.

**b) Chest sanity check** — applied *after* loading, using the DICOM tags
`BodyPartExamined (0018,0015)`, `ViewPosition (0018,5101)` and `Modality (0008,0060)`.
Anything not unambiguously chest is discarded. This is the second layer of defence
against step 2: DICOMs that slipped in through a leak in earlier downloads are
dropped here.

**c) Fallback path** — if the strict MONAI parse fails, the image is reloaded without
spatial headers and min-max normalized. This prevents a single malformed header from
costing the entire harvest.

**d) Orientation, heuristically** (`orient_chest_xray`) — the DICOMs in this
collection carry **no** `ImageOrientationPatient`, so SimpleITK's `DICOMOrient` is
useless. Image content decides instead:

- *Portrait*: `rot90` if wider than tall.
- *Vertical*: lungs (dark) on top, diaphragm/liver (bright) at the bottom → `flipud`
  if the top half is denser.
- *Horizontal*: cardiac silhouette on the viewer's right → `fliplr` if the left is
  denser.

The `PatientOrientation` tag is used **only** to break ties, because on this
collection it agrees with the pixel content only ~69 % of the time. The heuristic is
deliberately conservative: it only rotates when the signal is decisive.

**e) CLAHE** (`apply_clahe_contrast`, `clip_limit=0.02`) — adaptive histogram
equalization lifts the local contrast of the lung fields, matching what the NIH set
already looks like. Together with (a) this produces the NIH look.

**Output.** `data_hybrid/midrc_images/<object_id>.png` (8-bit greyscale, **native
resolution**) + `data_hybrid/midrc_processed_manifest.csv` (`img_path`, `patient_id`,
`Covid = 1`).

**Deliberate decision: no resize here.** `processing.py` saves at full resolution; all
downscaling happens later in step 6 or in the DataLoader (`ResizeLongest` +
`SquarePad`). Rescaling here would throw away diagnostic detail a second time.

**Idempotency.** If the target PNG exists, it is taken over as is. `--force-reprocess`
deletes all PNGs and the manifest and re-verifies every image including the chest
check.

---

## Step 5 — ResNet-18 rotation fix (`fix/`)

Step 4 only corrects what the heuristic recognizes *unambiguously*. What remains is a
residue of rotated images — MIDRC is exactly the untidy dataset we are pulling from.
A CNN takes care of that residue.

**5a — `fix/train_rotation_classifier.py` (one-time prerequisite)**

A 4-class ResNet-18 (ImageNet-pretrained) is trained on **synthetic rotations of the
NIH images**: every known-upright NIH image is deterministically rotated by
0/90/180/270° (1 image → 4 samples, 1 000 images → 4 000 samples, 224², Adam 1e-4, a
few epochs). The network therefore learns exactly the anatomical cues that define a
correct orientation: lungs on top, diaphragm below, cardiac silhouette on the right.
The reference is thus the *cleaned* NIH dataset — the same ground-truth quality that
later characterizes the NIH images themselves.

**5b — `fix/fix_midrc_orientation.py`**

Applies the trained classifier to every MIDRC PNG and rotates back by the **inverse**
angle (`{0:0°, 1:270°, 2:180°, 3:90°}`; Pillow rotates counter-clockwise). At the end
it logs per class how many images were corrected in which way, so the amount of
residual rotation is visible at a glance.

**Output.** `data_hybrid/midrc_fixed_images/*.png` (full resolution, oriented)

**Limits.** Only 0/90/180/270° are corrected — **no mirroring**. The classifier cannot
tell whether an image is anatomically mirrored, because there is simply no training
label for it.

**Idempotency.** Outputs are rewritten on every run.

---

## Step 6 — `fix/resize_midrc.py`: aspect-ratio resizing

**What happens.** A one-time downscale of the oriented full-resolution PNGs (up to
~4400×3610 px, ~48 GB in total) into working copies whose **longest side is exactly
`--size` (default 1024)** — using LANCZOS, preserving the aspect ratio. A
multiprocessing pool is used (`--workers 4`). Images that are already small enough
are copied unchanged.

**Purpose.** This is purely an I/O and decoding problem. Otherwise the DataLoader
would decode 48 GB of PNGs on every epoch — on the 24 GB machine that thrashed
training into swap and collapsed it to minutes per batch. With the working copies the
downscaling path becomes `1024 → 384` instead of `4400 → 384`: visually negligible,
but ~30× cheaper. The model's own resolution is decided later by `train.py`.

**Output.** `data_hybrid/midrc_fixed_1024/*.png`

---

## Step 7 — `blend_data.py`: balancing and merging

**NIH side.** `Data_Entry_2017.csv` is read, the pipe-separated `Finding Labels`
column is split into 14 binary columns, `Image Index` is mapped to real paths by
walking the directory, files that are not present are discarded, and the set is
filtered to PA/AP.

**Balancing.** `subsample_per_condition` caps each of the 14 pathologies at
`BALANCE_N = 7000` (environment variable). Because NIH images are multi-label, a
single image can hit several conditions — naively capping per column would overshoot
through the secondary labels. Rows are therefore dropped **greedily**, one at a time,
in a way that wastes as little data as possible: rows are preferred that touch many
over-limit conditions and that do **not** co-occur with a rare class. Rare classes
like `Hernia` (227 images) thus stay complete and are balanced later via class weights
during training rather than by discarding data. `No Finding` is kept in full as the
negative backbone.

**MIDRC side.** `midrc_processed_manifest.csv` is read and every `img_path` is
**remapped** onto `midrc_fixed_1024/`:

```python
MIDRC_FIXED_DIR = os.path.join("data_hybrid", "midrc_fixed_1024")
```

Rows without an existing, oriented *and* downscaled copy are dropped. This is the
gate: **neither an unrotated nor an unresized image can enter training**, even if
steps 5/6 were incomplete. For those rows the 14 NIH classes do not *mean* `0`, they
are *unknown* — which is exactly why they are masked out of the loss (see
[`../train/README.md`](../train/README.md)); the counterpart is the `Covid` column set
to `1`. The MIDRC set is capped at `BALANCE_N` as well.

**Output.** `data_hybrid/combined_master.csv` — columns `img_path`, `patient_id`,
`view_position` + 15 labels. This is the *only* file that training and evaluation
read.

> **Note:** `No Finding` is carried along as a bookkeeping column (and counted for the
> balance report), but is not part of the exported 15-class taxonomy.

**Idempotency.** Deterministic (seed 42) and always rewritten.

---

## Result

`data_hybrid/combined_master.csv` — verified against the state in the repo:

**100 758 images**, of which 6 809 are COVID (MIDRC) and 93 949 are NIH images with
the 14 pathology labels.

| Finding | Positives | | Finding | Positives |
|---|---:|---|---|---:|
| Atelectasis | 7 000 | | Mass | 5 782 |
| Cardiomegaly | 2 776 | | Nodule | 6 331 |
| Consolidation | 4 667 | | Pleural_Thickening | 3 385 |
| Edema | 2 303 | | Pneumonia | 1 431 |
| Effusion | 7 000 | | Pneumothorax | 5 302 |
| Emphysema | 2 516 | | **Covid** | **6 809** |
| Fibrosis | 1 686 | | | |
| Hernia | 227 | | | |
| Infiltration | 7 000 | | | |

Three classes sit at the 7 000 cap, the rest stay at their natural counts — exactly
the goal of the per-class capping: frequent findings get trimmed, rare ones do not.

**Two steps outside this folder** complete the dataset:

```bash
# 8: compute normalization statistics (mean/std) from the final CSV
python ml/model/train/compute_dataset_stats.py --csv data_hybrid/combined_master.csv --resolution 384
# 9: train
python ml/model/train/train.py --model convnext
```

---

## File overview

| File | Role |
|------|------|
| `get_nih_data.py` | Kaggle download + pointer file |
| `get_midrc_data.py` | Gen3 API metadata query, filtering, manifest |
| `download_midrc_data.py` | gen3-client bulk transfer |
| `processing.py` | MONAI normalization, chest check, heuristic, CLAHE, DICOM→PNG |
| `blend_data.py` | class balancing, fusion, `combined_master.csv` |
| `fix/train_rotation_classifier.py` | 4-class ResNet-18 on synthetic NIH rotations |
| `fix/fix_midrc_orientation.py` | apply the inverse rotation |
| `fix/resize_midrc.py` | aspect-ratio-preserving downscale |
| `fix/turn_midrc_images.py` | manual blind rotation (90/180/270) for spot checks |
| `explore/explore_available_conditions.py` | dumps every MIDRC `condition` / `observation` / `annotation` value — the evidence behind *Why MIDRC contributes exactly one label* |
| `explore/investigate_nih.py` | NIH view-position distribution (how much survives the PA/AP filter) |

## Gotchas worth knowing

- **The chest filter is not optional.** If it cannot be applied in
  `get_midrc_data.py`, both scripts abort rather than processing hand and abdomen
  images.
- **`--force-reprocess` is how you actually apply a changed script.** Without that
  flag, already existing PNGs count as valid.
- **Step 5 before step 7.** `blend_data.py` requires `midrc_fixed_1024/` and aborts
  with a clear error message if it is empty, instead of silently continuing with
  rotated images.
- **The Covid column separates the sources, not the disease.** In the test split all
  MIDRC images are `Covid = 1` and all NIH images are `Covid = 0`; masking the
  remaining 14 labels prevents this source shortcut from distorting the other
  metrics. Details in [`../evaluate/README.md`](../evaluate/README.md).
- **`midrc_images/` and `midrc_fixed_images/` are not interchangeable.** Only the
  `*_fixed_*` directories make it into `combined_master.csv`.
