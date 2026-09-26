
### What did we do with which data
The Data Collection, Processing, and Assembly stages differ greatly for the usecase of fine-tuning either the Classifier or the LLM.

TODO: maybe list here just the sources(?)

#### Prediction model
The Classifier was trained on a merged Dataset, consisting of two preexisting sources: 1) MIDRC: Open-A1, 2) the NIH Chest X-Ray Dataset. The workflow centeralized around bringing the MIDRC part of the Dataset into a suitable format to fit images of NIH more, involving steps of obtaining, normalizing, rotating, and resizing images into suitable format. 

MIDRC: https://www.midrc.org/midrc-data 
NIH: https://www.kaggle.com/datasets/nih-chest-xrays/data

For more precise infomation on the handling process see [Data: Classifier finetuning](#hybrid-chest-x-ray-multi-label-training-pipeline).


#### LLM 
In constrast to the Prediction model, where we adapted preexisting datasets into a format suitable for our use-case, for the LLM we did not have any Data to begin with. The process of obtaining a fine-tuneable jsonl involved manually selecting informative webpages, extracting information, and structuring it. 

For more precise infomation on the handling process see [Data: LLM finefuning](#llm-finefuning-data).


### Model files (X-ray classifier & LLM)

#### Where the models come from

**GitHub rejects files above 100 MB**, so model weights are distributed as
follows:

- **X-ray classifiers — in the repository via Git LFS:** the CNN checkpoints
  ship with every clone, so the app works out of the box. The git history only
  contains small pointer files; GitHub LFS serves the actual weights (each file
  is well below the 2 GB per-file limit). Adding a retrained model to the
  ensemble is just dropping the `.pth` into `checkpoints/` and committing — Git
  LFS tracks it automatically (see [Getting the classifier](#getting-the-classifier-for-local-development)).
- **LLM — from Hugging Face on demand:** the fine-tuned GGUF is too large for
  Git LFS (4.9 GB vs. the 2 GB per-file limit), so the `ollama` container
  downloads it automatically at startup.

| Model | Purpose | Size | Ships in repo (Git LFS) | File |
|-------|---------|------|------------------------|------|
| X-ray classifier (ConvNeXt-Base) | Predicts 15 conditions per image, 384px input | 334 MB | ✅ | `checkpoints/covnext348.pth` |
| X-ray classifier (Swin-B) | Same 15 conditions, 224px transformer backbone | 331 MB | ✅ | `checkpoints/swin-224px_final.pth` |
| X-ray classifier (DenseNet-121 / CheXNet) | Same 15 conditions, 224px dense backbone | ~31 MB | ❌ (trained locally via Step 9, then committed) | `checkpoints/densenet-224px_final.pth` |
| Chatbot LLM | Fine-tuned Llama-3-8B-Instruct (from `leoniejkr/trustai-llm-gguf`) | 4.9 GB | ❌ (too large for Git LFS) | `llama-3-8b-Instruct.Q4_K_M.gguf` |

The model download differs between the development and production setups:

- **LLM:** the `ollama` container downloads the GGUF from Hugging Face at startup
  and registers the model `trustai-llm:latest`. In a native-Ollama setup you register
  it yourself with `ollama create` (see [LLM model configuration](#llm-model-configuration)).
- **Classifier, development:** `docker-compose.yaml` mounts the local
  `./checkpoints` directory (the Git LFS files) into the modelling container.
  No download step is needed.
- **Classifier, production:** the production image copies the checkpoints from
  the repository into `/app/checkpoints` at build time (Git LFS must be
  installed so the real files are in the clone, see
  [Production-Deployment](#production-deployment-und-docker-hub)).

#### Getting the classifier / adding a new one

The development setup (`docker-compose.yaml`) mounts `./checkpoints` into the
modelling container, and those checkpoint files come straight from Git LFS.
On a correct clone the two default classifiers are already present:

```bash
git lfs install   # once, fetches the LFS model files on clone/pull
git lfs pull      # only needed if pointers were already cloned without LFS
```

To add a retrained model to the ensemble (or replace a checkpoint), drop the
`.pth` into `checkpoints/`, `git add` it and commit — `.gitattributes` routes
`checkpoints/*.pth` through Git LFS automatically, and
`services/model-api/models_registry.py` plus the frontend model selector are
its registration point. Every `checkpoints/**/*.pth` beyond the tracked files
stays local-only by default, so intermediate training outputs are not
committed by accident.

Three architectures are registered end-to-end (`convnext`, `swin`, `densenet`).
`densenet` is brand-new: its serving factory expects the checkpoint at exactly
`checkpoints/densenet-224px_final.pth`, so training it via [Step 9](#pipeline-execution-order)
and saving the result under that name makes it selectable in the frontend and
lets it join the ensemble automatically. The ensemble skips any registered
member whose checkpoint file does not exist yet (with a warning), so a not-yet-
trained `densenet` never breaks the `ensemble` selection.

> Note: `checkpoints/xray_orientation_resnet18.pth` is a
> local helper only used by the MIDRC preprocessing pipeline; it is intentionally
> not distributed.


# Classifier finetuning

## Data preprocessing


An end-to-end pipeline that blends the NIH Chest X-Ray 14 dataset with the MIDRC COVID-19 dataset into a unified 15-class multi-label classification problem.

#### Dataset Sources

| Dataset | Source | Contents |
|---------|--------|----------|
| NIH Chest X-Ray | [Kaggle](https://www.kaggle.com/datasets/nih-chest-xrays/data) | ~112k images, 14 pathologies, no COVID |
| MIDRC | [midrc.org](https://www.midrc.org/midrc-data) | COVID-19 positive chest X-rays |

#### Directory Structure

```
data_hybrid/
├── nih_images/
│   └── path.txt                     ← Pointer to Kaggle cache (run get_nih_data.py first)
├── midrc_dicoms/                    ← Raw MIDRC DICOM zips
├── midrc_images/                    ← Converted 512×512 PNGs
├── midrc_fixed_images/              ← Orientation-corrected MIDRC PNGs
├── midrc_fixed_1024/                ← Working copies used by blend_data.py
├── midrc_download_manifest.json     ← gen3-client download list
├── midrc_processed_manifest.csv     ← Processed image manifest
└── combined_master.csv              ← Final training dataset
```

#### Pipeline Execution Order

Each step reads the output of the previous one. Run from the project root.

```bash
# Step 1: Download NIH dataset to Kaggle cache + create pointer file (skips if cached)
python ml/model/construct_data/get_nih_data.py

# Step 2: Query MIDRC cloud API → generates download manifest (skips if manifest exists)
python ml/model/construct_data/get_midrc_data.py          # add --force to re-query

# Step 3: Download DICOM zips via gen3-client → data_hybrid/midrc_dicoms/ (skips completed)
python ml/model/construct_data/download_midrc_data.py

# Step 4: Convert DICOMs → 512×512 PNGs with CLAHE + auto-rotation (skips existing PNGs)
python ml/model/construct_data/processing.py

# One-time prerequisite for step 5 if the orientation checkpoint does not exist.
# Point --image-dir at a directory containing upright NIH images.
python ml/model/fix/train_rotation_classifier.py \
  --image-dir /path/to/nih/images_001/images \
  --out checkpoints/xray_orientation_resnet18.pth

# Step 5: Apply the learned orientation correction to the MIDRC PNGs
python ml/model/fix/fix_midrc_orientation.py

# Step 6: Create memory-efficient working copies in midrc_fixed_1024/
python ml/model/construct_data/resize_midrc.py

# Step 7: Cap class counts and merge NIH + MIDRC into combined_master.csv
python ml/model/construct_data/blend_data.py

# Step 8: Compute normalization statistics once. The resolution is taken
# automatically from the active model's INPUT_SIZE (default convnext = 384;
# use --model swin for a 224 run), so the stats match the trained backbone.
# One dataset_stats.json is reused everywhere else — the values barely depend
# on the size (SquarePad's black fill is scale-invariant), so re-running per
# model is optional.
python ml/model/train/compute_dataset_stats.py
# (for a Swin-B or DenseNet training run:  python ml/model/train/compute_dataset_stats.py --model swin|densenet)

# Step 9: Train the model
python ml/model/train/train.py --model convnext     # or: --model swin / --model densenet
```

The download and initial DICOM conversion steps reuse or skip existing files.
The orientation correction, resize, dataset merge, statistics calculation and
training steps rewrite their outputs when run again.

The training codebase is shared by all architectures: train the ConvNeXt model with
`--model convnext` (`ChestModel`, the default), Swin-B with `--model swin`
(`SwinTransformerChestModel` from `models.ViT_model`), and the new DenseNet-121 /
CheXNet-style backbone with `--model densenet` (`DenseNetChestModel` from
`models.densenet_model`); resolution and batch size then adapt automatically as
described under *Training (Step 9)*. The same selection is available as the
`TRAIN_MODEL` environment variable.

### What Each Step Does

| Step | Script | Input | Output | Skip Logic |
|------|--------|-------|--------|------------|
| 1 | `get_nih_data.py` | Kaggle API | Kaggle cache + `nih_images/path.txt` | `kagglehub` skips cached downloads |
| 2 | `get_midrc_data.py` | MIDRC Gen3 API | `midrc_download_manifest.json` | Skips if manifest exists (`--force` to re-query) |
| 3 | `download_midrc_data.py` | manifest JSON | `data_hybrid/midrc_dicoms/` | `--skip-completed` flag |
| 4 | `processing.py` | DICOM zips | 512×512 PNGs + `midrc_processed_manifest.csv` | Skips if output PNG already exists |
| Prerequisite | `train_rotation_classifier.py` | Upright NIH images | `checkpoints/xray_orientation_resnet18.pth` | Needed once; overwrites the checkpoint when rerun |
| 5 | `fix_midrc_orientation.py` | MIDRC PNGs + orientation checkpoint | `data_hybrid/midrc_fixed_images/` | Rewrites corrected images |
| 6 | `resize_midrc.py` | Corrected MIDRC PNGs | `data_hybrid/midrc_fixed_1024/` | Rewrites or copies working images |
| 7 | `blend_data.py` | NIH cache + corrected MIDRC images | `combined_master.csv` | Always rewrites (deterministic) |
| 8 | `compute_dataset_stats.py` | `combined_master.csv` | `dataset_stats.json` | Always rewrites |


### Processing Details

**DICOM → PNG (Step 4)** applies:
- MONAI `ScaleIntensityRangePercentiles(0.5, 99.5)` windowing
- CLAHE adaptive histogram equalization (clip_limit=0.02)
- MONOCHROME1 photometric inversion (both Strategy A and fallback)
- Portrait normalization and content-based vertical/horizontal orientation correction
- Resize to 512×512, saved as 8-bit grayscale

**Orientation and resizing (Steps 5–6)** applies:
- A four-class ResNet-18 corrects remaining 0°/90°/180°/270° rotations
- `resize_midrc.py` creates aspect-preserving working copies whose longest side
  is at most 1024 pixels

**Data Blending (Step 7)** applies:
- NIH: 14 pathologies from `Data_Entry_2017.csv`, filtered to PA/AP views only
- Each NIH pathology and the MIDRC COVID set are capped separately at
  `BALANCE_N` images (7000 by default); there is no fixed NIH:MIDRC ratio
- NIH `No Finding` images are retained as the negative backbone
- MIDRC rows contain a COVID label; their other pathology fields are treated as
  unknown and masked out of the loss during training


## Training

**Training (Step 9)** uses:
- **Backbone-adaptive input geometry and batch size.** Each model class declares
  the resolution it was architecture-tuned for (`INPUT_SIZE`) and a memory-safe
  `BATCH_SIZE`, and `train.py` derives both from the selected class so no model
  is squeezed to a size that does not fit its architecture:

  | Backbone | `INPUT_SIZE` | `BATCH_SIZE` | Why these values |
  |----------|--------------|--------------|------------------|
  | ConvNeXt-Base (`ChestModel`) | 384 | 32 | fully-convolutional → resolution-flexible; higher input keeps more X-ray detail |
  | Swin-B (`SwinTransformerChestModel`) | 224 | 24 | matches the ImageNet-1K pre-training grid (safer than interpolating the relative-position bias); transformers need more memory per image |
  | DenseNet-121 (`DenseNetChestModel`, CheXNet-style) | 224 | 32 | dense connectivity is a third, distinct inductive bias for ensemble diversity; tiny and fast on MPS |

  `train.py` resolves `RESOLUTION = config["resolution"] or MODEL_CLASS.INPUT_SIZE`
  and `BATCH_SIZE = config["batch_size"] or MODEL_CLASS.BATCH_SIZE`. The current
  `main` configuration leaves `resolution` at `None` so every model trains at its
  own `INPUT_SIZE` — which is also exactly what the serving-side `preprocess`
  uses, so training and serving geometry can never drift apart (see the model
  table above for the serving inputs). Batch size is pinned conservatively to 16
  for MPS memory safety. All architectures share the same data handling
  otherwise (same `combined_master.csv`, same 15 classes, same masked partial
  labels, same patient splits).
- Aspect-preserving geometry: longer side resized to the model's resolution,
  shorter side black-padded to a square (never distorted).
- Dataset-specific normalization (Step 8 mean/std; one set of statistics serves
  all backbones, since they describe the images, not the network geometry).
- Partial-label masked BCE loss with sqrt-scaled `pos_weight` for class imbalance
- Differential learning rates for backbone vs. classification head +
  CosineAnnealing LR scheduler
- Patient-level 80/10/10 train/validation/test split, stratified by the combined
  COVID/Effusion key
- A fresh training run each time; intermediate weights are written to
  `temp_checkpoint.pth` and final weights to `checkpoint.pth`

TODO


# LLM finetuning

## Data preprocessing


## Training
TODO


# Model integration
## Classifier
simply via git. alsready done
# LLM

### Fast path (recommended): native Ollama

In Docker, Ollama runs on **CPU only** — the Docker VM has no access to the host GPU.
An 8B model on CPU generates ~1 token/s, so replies take minutes. **This is a Docker
limitation, not a problem with the model.**

Ollama supports GPU acceleration natively on **all platforms**:

| OS | GPU API | Install |
|----|---------|---------|
| macOS (Apple Silicon) | Metal | `brew install ollama` |
| Linux (NVIDIA/AMD) | CUDA / ROCm | `curl -fsSL https://ollama.com/install.sh \| sh` |
| Windows | CUDA | Download from [ollama.com](https://ollama.com) |

In every case, install native Ollama once, register the model, and the app runs at
full GPU speed (typically 10-50x faster than Docker CPU):

1. **Install Ollama** (see table above — one-time per machine)
2. **Start the service:**
   ```bash
   # macOS
   brew services start ollama
   # Linux
   ollama serve &   # or via systemd
   ```
3. **Download and register the fine-tuned model**, then pull the fallback model.
   The GGUF is not stored in this Git repository, so save it next to the native
   Modelfile before running `ollama create`:
   ```bash
   curl -L --fail -C - \
     -o ml/LLM/files/clinical_model_dir/llama-3-8b-Instruct.Q4_K_M.gguf \
     https://huggingface.co/leoniejkr/trustai-llm-gguf/resolve/main/llama-3-8b-Instruct.Q4_K_M.gguf
   ollama create trustai-llm -f \
     ml/LLM/files/clinical_model_dir/trustai-llm.Modelfile.native
   ollama pull phi3:mini
   ```
4. **Point the containers at the host Ollama** (`.env` is gitignored):
   ```bash
   echo "LLM_URL=http://host.docker.internal:11434" > .env
   docker compose up -d --force-recreate backend modelling
   ```

The Docker `ollama` service stays in compose (internal-only, no published port) as the
default for pure-Docker setups. Setting `LLM_URL` routes backend and modelling requests
to the native Ollama instance, but the Docker `ollama` service is still started because
it remains a Compose dependency. On its first start it therefore still downloads and
registers the configured models.

The fine-tuned model (`trustai-llm:latest`) is registered automatically when the `ollama` container starts (downloaded from Hugging Face, see [LLM model configuration](#llm-model-configuration)). The fallback model `phi3:mini` is pulled automatically as well, so both options in the **Settings → LLM Model** dropdown work out of the box. On the native path, pull it once with `ollama pull phi3:mini`, otherwise the app will return an error when that model is selected.

Notes:
- the models are stored in the ``ollama_data`` volume (container) or ``~/.ollama`` (native), so they survive restarts; re-download only after ``docker compose down -v``
- on the native path both models must be present in the host Ollama: `ollama create trustai-llm -f ...` and `ollama pull phi3:mini` (both one-time per machine)
- the backend connects to the LLM via ``OLLAMA_URL``/``OLLAMA_MODEL`` — ``OLLAMA_URL`` is ``http://ollama:11434`` by default and overridden by the ``LLM_URL`` env var (see above)
- quick test without the UI: ``curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"message": "hello", "history": []}'``

#### LLM model configuration

The fine-tuned LLM (`trustai-llm:latest`) is registered in the `ollama` container at startup from a GGUF file hosted on Hugging Face. No local model file needs to be present on the developer's machine. The downloaded GGUF is cached in the `llm_models` volume and the registered model in `ollama_data`; the download/registration is skipped if the model already exists.

- **Base model (before fine-tuning):** `unsloth/llama-3-8b-Instruct-bnb-4bit` — the Llama-3-8B-Instruct base model (Meta) in the 4-bit quantized Unsloth variant, used in `ml/LLM/ollama_finetune.py`
- **Fine-tuned GGUF repo:** `leoniejkr/trustai-llm-gguf` (public, read-only for everyone — only the account owner can modify the weights)
- **Default GGUF:** `llama-3-8b-Instruct.Q4_K_M.gguf`

**Important:** the 4.9 GB model file is **not committed to git** (GitHub rejects files > 100 MB).
Every developer/teacher gets the weights from the HF repo instead — either automatically in the `ollama` container (see above) or by downloading the GGUF and then running `ollama create trustai-llm -f ...` in the native setup. Only code/config lives in git.

The download is skipped if the file already exists (cached in `/models`), and the model is only re-created when necessary. Both sources can be overridden via environment variables:

```yaml
# docker-compose.yaml  (ollama service)
environment:
  HF_MODEL_REPO: leoniejkr/trustai-llm-gguf   # namespace/repo on the HF Hub
  HF_GGUF_FILE: llama-3-8b-Instruct.Q4_K_M.gguf
```

If you host your own copy (e.g. a fork on your own HF account), just point `HF_MODEL_REPO` at it. A **private** repo requires authentication inside the container; for the default **public** repo no token is needed.

The Go backend and the modelling service use `OLLAMA_MODEL` (default `trustai-llm:latest`) to talk to the LLM. The model actually used per request is chosen in the **Settings → LLM Model** dropdown of the web app (`trustai-llm:latest` or `phi3:mini`). In the Docker setup both models are installed automatically when the `ollama` container starts. In a native-Ollama setup, download/register `trustai-llm` and pull `phi3:mini` once on the host.


