# __TrustAI__

## Project Summary

### What does the application do

TrustAI is a Medical Prediction AI platform created to support clinicians in assessing chest X-ray images. Its main feature is a deep learning model that analyzes uploaded medical images uploaded in .png format, to detect potential abnormalities, diseases, and other visual findings.

Users can upload one or multiple X-ray images and patient information. The model then generates predictions for possible conditions based on the images and also gives a certainty estimation for each result, which we call confidence scores.

On the results page, the dashboard displays heatmaps which highlight the image regions that have contributed to each prediction. For more information, the user can use a medical viewport to take a closer look at the X-Rays or interact with an integrated chatbot. The chatbot has knowledge about the supported diseases and has access to the patient metadata and model findings.

Previous analysis results can be viewed and deleted on the history page of the application.

### Workflow of the application

#### General information

The application is build as a web app without any authentication. We decided not to implement authentication services such as Keycloak because we do not plan on hosting this application ourself, but to make it available for private and local use via Docker.

It is divided into a frontend (located in /frontend), which is built with Typescript and SvelteKit (on top of Vite), a backend (located in /backend), which is built with Golang, and a separate modelling service (located in services/model-api). The model and LLM code is located under ml/model and ml/LLM respectively.

The backend uses PostgreSQL for structured patient and analysis data, while Orthanc is used for X-Ray and heatmap storage.
The OpenAPI standard in combination with Swagger are used to construct the REST API and its' specification.

#### User centric workflow 

The user starts by uploading one or more chest X-Ray .png images and entering patient information such as age, gender, symptoms, and medical history via the upload page through the web interface. The application does not support the upload of .dcm images.

The frontend sends the images and patient metadata to the Go backend. For this, the frontend builds the form data, which consists of the image files, the JSON string with the metadata, the classifier model and the llm model and sends this as a POST request to the backend via the /api/analysis REST endpoint. 

The backend then coordinates the analysis workflow. 
In the production deployment, Nginx rejects request size over 200 MiB. Too much memory usage can lead to crashes due to out-of-memory conditions. The Go backend parses the multipart form, keeping up to 50 MiB of uploaded file data in memory and storing any excess temporarily on disk. 
The backend then validates the request data.
If the request is valid, the backend then stores the uploaded images into the Orthanc database via a POST request to the Orthanc endpoint /tools/create-dicom and creates a patient record in Postgresql, where the Orthanc instance IDs of the images are subsequently added into the patient row. Moreover, the images are forwarded to the deep learning modelling service via a POST request to the /predict endpoint of the model. 

The modelling service parses the data and loads the classifier selected in the
frontend settings (ConvNeXt-Base by default; the extended setup also supports
the Swin-B transformer and an **ensemble** that averages the probabilities of
all other registered classifiers — currently ConvNeXt + Swin soft-voting,
which typically lifts ROC-AUC; no retraining, the members are the same
checkpoints). Each classifier applies its own training-matching preprocessing
(the selected model's `INPUT_SIZE` + dataset normalization) and uses it to
identify possible abnormalities and
calculate a confidence score for each prediction. The confidence score is a
certainty estimation showing how certain the model is for each prediction. It
also generates heatmaps in png format that indicate which image regions
influenced the model's decision. 

The patient metadata is not used for the model classification but is instead forwarded to the LLM as metadata. The LLM can help the user better regarding possible questions with the metadata. 

All analysis results and heatmap images are returned to the backend. The analysis results are saved in Postgresql and the heatmaps are saved in th Orthanc database. When the results from the POST request are received by the frontend, the frontend automatically navigates to the result page, where users can see the original images through a CornerstoneJS medical viewer. Furthermore, the analysis results such as the predictions, confidence scores and corresponding heatmaps can be reviewed.

The application presents two types of prediction results. Aggregated results and individual results, which are both accompanied with confidence scores that are measured in percentages. The aggregated results are located at the top and show the aggregated, calculated classifications over all the uploaded X-Ray images, while the individual results at the bottom show the calculated classifications for each individual X-Ray image with their respective corresponding heatmaps. The classifications are ranked according to their confidence scores. The confidence threshold for shown classifications can be modified in the GUI with a slider in the results page after the calculation. The dashboard also passes the relevant patient information and findings to the chatbot, allowing the underlying LLM to answer questions, explain the results, and support risk assessment.

The chatbot connects to the locally running Ollama service, which provides the language model used for the conversational assistance.

The patient data, X-Ray images and analysis results are stored in Postgresql and Orthanc and can be re-viewed on the history page of the application at a later point.
The history page shows all previous analysis results. These can be deleted individually via the /api/patient/{id} endpoint with a DELETE request or collectively via the /api/analysis enpoint with a DELETE request. 

For more precise information about the frontend and backend workflow see [Frontend](#frontend) and [Backend](#backend).

### What did we do with which data

see [Data](#data)

#### Prediction model

The prediction model was trained on the mixed data of MIDRC: Open-A1 and the NIH Chest X-Ray Dataset.

#### LLM -> Chatbot

Data for the LLM

### How did we collect the data

Dataset sources \
MIDRC: https://www.midrc.org/midrc-data \
NIH: https://www.kaggle.com/datasets/nih-chest-xrays/data


## How to run and start the application

### Running the application

#### Prerequisites for running the application

The application runs all required services in containers, so no separate installation of any programming language or database is needed if you only want to run the application.
The two X-ray classifiers (ConvNeXt + Swin) ship directly in the repository via **Git LFS** (see [Model files](#model-files-x-ray-classifier-llm)); install the Git LFS client once with `git lfs install` so the model files are fetched with the clone. No Hugging Face access is needed for the default models. The fine-tuned LLM is downloaded automatically from Hugging Face by the `ollama` container on its first start.
For most OS just install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/). If you use NixOS or Arch-based systems just install the Docker Engine. For MacOS you can install Colima instead to your liking.

#### Starting the application

The X-ray classifier checkpoints are part of the repository (Git LFS), so a
fresh clone already contains them. The only setup step is making Git LFS fetch
the model files:

```bash
git lfs install
```

> If you cloned the repository **before** installing Git LFS, the checkpoints
> arrive as small pointer files (~130 bytes instead of ~330 MB). Fix it with
> `git lfs pull`.

Then build and start the application from the project root:

```bash
docker compose build
docker compose up
```

The `docker compose build` command builds the application images and only has to
be executed once, as long as the code stays unchanged. The `docker compose up`
command starts the images and has to be executed every time the application is
to be started. The GGUF language model is downloaded by the `ollama` container
automatically on its first start, so no model file has to be prepared manually.
It may take a few minutes until the models are downloaded and the application
is built.
To combine both docker commands you can run:
```bash
docker compose up -d --build
```

For subsequent starts, run:

```bash
docker compose up -d
```

Then, open [http://localhost:5173](http://localhost:5173) in a browser.

To stop the application, run:

```bash
docker compose down
```

The application data and downloaded language model are stored in Docker volumes and remain available after stopping the services. Use 

```bash
docker compose down -v
``` 
only when you intentionally want to delete these volumes and their data.

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

> Note: `checkpoints/xray_orientation_resnet18.pth` is a
> local helper only used by the MIDRC preprocessing pipeline; it is intentionally
> not distributed.

## General Information for backend and brontend and how to contribute

The frontend and backend Docker images can be used for development purposes since live reloading is integrated into both images. The frontend uses Vite as a build and live reloading tool and the backend uses Air. The instruction on how to set up Docker and run the images are written in [Starting the application](#starting-the-application). 

### Frontend

#### Structure of the Frontend
The frontend is written in Typescript in combination with Svelte and SvelteKit as a build tool. SvelteKit is powered by Vite. 
SvelteKit operates on a filesystem based router, which means that routes / URLs are defined by the directories in the frontend codebase. The frontend route/ directory is structured in a way to accomodate this. No manual router setup is needed.

The lib directory contains different kinds of shared functions and components. The individual files are composed of services and utility logic that are used throughout the frontend. General UI components are located in /components. ShadCN for Svelte was used for the UI components. The /assets folder contains .svg files. 

#### Contributing

##### Prerequisites

1. Install nvm and the current NodeJS version with npm as seen in the tutorial [https://nodejs.org/en/download/current](https://nodejs.org/en/download/current)
2. Navigate into the frontend folder and execute 
```bash
npm install
```
to install all dependencies

##### Running and Testing the Frontend

If you only want to start and work on the frontend, execute ``npm run dev``. This command executes Vite, which is a build tool for web development. It comes with integrated live reloading, meaning you dont have to restart Vite after making changes to the code. Make sure the Docker images are not running or else the ports overlap.

To to test the frontend there are multiple commands that serve different purposes. The most important two are:

```bash
npm run test
```
Starts the unit tests, which are implemented using vitest as recommended by the Svelte team [https://svelte.dev/docs/svelte/testing](https://svelte.dev/docs/svelte/testing).

TODO: ACHTUNG NICHT IMPLEMENTIERT!!!
```bash
npm run test:e2e
```
Starts the E2E tests which are implemented using Playwright. Playwright is the de-facto standard nowadays for end-to-end tests as it is generally faster and more reliable than Selenium for example. 

### Backend

#### Structure of the backend

The backend is structured as a layered architecture that sends requests in the backend from handler to service to a repository or client. The handlers are the HTTP layer that translate HTTP requests into service calls that can be understood by the backend. The services contain business and orchestration logic. The repositories do not contain any business logic and instead communicate with the database. For this they use GORM, which is an ORM library for Golang. For more information about ORM, see [ORM](ORM).
Some directories contain files that are named the same as those directories. These files contain types and structs. 

The main.go is located under /cmd/server and acts as a starting point for the backend that initialises the database, reads configuration files, injects dependencies into the components and starts the HTTP server on the configured port.

The rest of the backend code resides in the /internal directory. 

The Rest API is documented in the /docs directory using the OpenAPI standard and Swagger and it is directly used by the frontend. 

#### Contributing

##### Prerequisites

1. Install go as instructed here [https://go.dev/doc/install](https://go.dev/doc/install)
2. Run 
```bash
go mod tidy
```
to install all dependencies
3. You may have to write ``export PATH=$PATH:$(go env GOPATH)/bin`` into your .bashrc

##### Testing the Backend

Tests in Go have the "_test" suffix. The general Go convention is to have one test file for every normal Go file that exists but this repository does not follow this convention for the files that are named after the directory they are in as these files only contain types and structs. 

To test the backend move to the backend/internal folder and run

```bash
go test ./...
```
or if you are in VSCode and have installed GOlang support, right click into the internal folder and click on "Run Tests".

##### Update the API with Swagger

Changing the API in any way requires you to update the API specification and documentation. To do this run the following command in the backend folder:

 ```bash
 swag init --dir ./cmd/server,./internal/api --output ./docs
 ```
Changing the API in the backend may require you to also make changes in the frontend.

# Data

## Hybrid Chest X-Ray Multi-Label Training Pipeline

An end-to-end pipeline that blends the NIH Chest X-Ray 14 dataset with the MIDRC COVID-19 dataset into a unified 15-class multi-label classification problem.

### Dataset Sources

| Dataset | Source | Contents |
|---------|--------|----------|
| NIH Chest X-Ray | [Kaggle](https://www.kaggle.com/datasets/nih-chest-xrays/data) | ~112k images, 14 pathologies, no COVID |
| MIDRC | [midrc.org](https://www.midrc.org/midrc-data) | COVID-19 positive chest X-rays |

### Directory Structure

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

### Pipeline Execution Order

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
# (for a Swin-B training run:  python ml/model/train/compute_dataset_stats.py --model swin)

# Step 9: Train the model
python ml/model/train/train.py
```

The download and initial DICOM conversion steps reuse or skip existing files.
The orientation correction, resize, dataset merge, statistics calculation and
training steps rewrite their outputs when run again.

The training codebase is shared by both backbones: train the ConvNeXt model with
`MODEL_CLASS = ChestModel` in `ml/model/train/train.py` and the Swin-B model with
`MODEL_CLASS = SwinTransformerChestModel` (from `models.ViT_model`); resolution
and batch size then adapt automatically as described under *Training (Step 9)*.
The newer trainer additionally exposes this as a CLI flag
(`--model convnext` / `--model swin`).

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
| 9 | `train.py` | `combined_master.csv` + stats | `dual_view_checkpoint.pth` and `checkpoint.pth` | Trains from scratch and overwrites checkpoints |

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

**Training (Step 9)** uses:
- **Backbone-adaptive input geometry and batch size.** Each model class declares
  the resolution it was architecture-tuned for (`INPUT_SIZE`) and a memory-safe
  `BATCH_SIZE`, and `train.py` derives both from the selected class so no model
  is squeezed to a size that does not fit its architecture:

  | Backbone | `INPUT_SIZE` | `BATCH_SIZE` | Why these values |
  |----------|--------------|--------------|------------------|
  | ConvNeXt-Base (`ChestModel`) | 384 | 32 | fully-convolutional → resolution-flexible; higher input keeps more X-ray detail |
  | Swin-B (`SwinTransformerChestModel`) | 224 | 24 | matches the ImageNet-1K pre-training grid (safer than interpolating the relative-position bias); transformers need more memory per image |

  `train.py` resolves `RESOLUTION = config["resolution"] or MODEL_CLASS.INPUT_SIZE`
  and `BATCH_SIZE = config["batch_size"] or MODEL_CLASS.BATCH_SIZE`. The current
  `main` configuration pins ConvNeXt to 288 px / batch 16; setting those config
  keys to `None` falls back to the class defaults above. Both backbones share the
  same data handling otherwise (same `combined_master.csv`, same 15 classes, same
  masked partial labels, same patient splits).
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
  `dual_view_checkpoint.pth` and final weights to `checkpoint.pth`


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
Every developer/teacher gets the weights from the HF repo instead — either automatically in
the `ollama` container (see above) or by downloading the GGUF and then running
`ollama create trustai-llm -f ...` in the native setup. Only code/config lives in git.

The download is skipped if the file already exists (cached in `/models`), and the model is only re-created when necessary. Both sources can be overridden via environment variables:

```yaml
# docker-compose.yaml  (ollama service)
environment:
  HF_MODEL_REPO: leoniejkr/trustai-llm-gguf   # namespace/repo on the HF Hub
  HF_GGUF_FILE: llama-3-8b-Instruct.Q4_K_M.gguf
```

If you host your own copy (e.g. a fork on your own HF account), just point `HF_MODEL_REPO` at it. A **private** repo requires authentication inside the container; for the default **public** repo no token is needed.

The Go backend and the modelling service use `OLLAMA_MODEL` (default `trustai-llm:latest`) to talk to the LLM. The model actually used per request is chosen in the **Settings → LLM Model** dropdown of the web app (`trustai-llm:latest` or `phi3:mini`). In the Docker setup both models are installed automatically when the `ollama` container starts. In a native-Ollama setup, download/register `trustai-llm` and pull `phi3:mini` once on the host.

## Production-Deployment and Docker Hub

The "normal" docker-compose.yaml is not for publishing. The project contains a seperate compose file and seperate production builds that have the keys "target: prod"

### Produktions-Stack lokal starten

```bash
docker compose -f docker-compose.prod.yaml up -d
```

Danach läuft die App unter [http://localhost](http://localhost). Ein nginx-Reverse-Proxy
ist der einzige Einstiegspunkt: `/` → Frontend (SvelteKit-SSR), `/api/*` → Go-Backend
(das `/api`-Präfix wird entfernt), `/swagger/` → Swagger-UI. Das LLM (`trustai-llm:latest`)
wird wie im Dev-Setup automatisch beim Start des `ollama`-Containers vom Hugging Face Hub
geladen (siehe [LLM model configuration](#llm-model-configuration)).

Unterschiede zur Entwicklung:

- **Multi-Stage-Images**: kein Live-Reload, keine Volume-Mounts, der Code liegt im Image.
  Das Backend läuft als statisches Binary, das Frontend als Node-Server (`adapter-node`).
- **Modelling**: die trainierten Modelle (`covnext348.pth`, `swin-224px_final.pth`)
  liegen als Git-LFS-Dateien im Repo (`checkpoints/`) und werden beim Docker-Build
  direkt mitkopiert (`.dockerignore` filtert auf genau diese zwei Dateien, ein
  Guard bricht den Build ab, falls nur LFS-Pointer statt der Gewichte im Clone
  liegen — also vorher `git lfs install && git lfs pull`). Gestartet wird das
  Image als gunicorn-Worker.
- **Ports**: Frontend und Backend sind intern (nur `nginx` publiziert `80`); `db`, `orthanc`
  und `ollama` sind sogar gar nicht von außen erreichbar.

### Images automatisch publizieren (GitHub Actions)

`.github/workflows/publish-images.yml` baut die drei Produktions-Images und pusht sie nach
**GHCR** — aber nur, wenn man es manuell auslöst, nicht bei jedem Push:

1. Auf GitHub → *Actions → Publish Production Images → Run workflow* klicken.
2. Der Job baut und pusht:
   - `ghcr.io/leoniejkr/lt_project-backend`
   - `ghcr.io/leoniejkr/lt_project-frontend`
   - `ghcr.io/leoniejkr/lt_project-modelling`

Die Pakete werden im Workflow automatisch auf *public* gesetzt (best effort). Für eigene
Deployments können die `image:`-Namen in `docker-compose.prod.yaml` auf diese GHCR-Adressen
umgestellt werden.

Alternativ zu Docker Hub wechseln: im Workflow den Login auf `docker/login-action`
umbauen und die Secrets `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` anlegen.

### Images manuell publizieren (z. B. Docker Hub)

1. Die `image:`-Namen in `docker-compose.prod.yaml` (`trustai/backend`,
   `trustai/frontend`, `trustai/modelling` und `trustai/ollama`) auf den eigenen
   Registry-Namespace umstellen (`<user>/<name>`).
2. `docker login`
3. `docker compose -f docker-compose.prod.yaml build`
4. `docker compose -f docker-compose.prod.yaml push`

Danach kann der Stack statt mit den `build:`-Blöcken mit den veröffentlichten `image:`-Namen
ausgerollt werden.

## Concepts

### ORM

Object relational mapping is a strategy with which one can map object oriented programming structures into relational database structures. This has to be done, because relational databases store object information in data tables and Go stores object information in structs which can not be automatically mapped into data tables.
