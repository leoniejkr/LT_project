# __TrustAI__

## Project Summary

### What does the application do

TrustAI is a Medical Prediction AI platform created to support clinicians in assessing chest X-ray images. Its main feature is a deep learning model that analyzes uploaded medical images to detect potential abnormalities, diseases, and other visual findings.

Users can upload one or multiple X-ray images via the upload page and enter relevant patient information (like age, gender, symptoms, and medical history). The model then generates predictions for possible conditions and also gives a certainty estimation for each result (confidence scores).

On the results page, the dashboard displays heatmaps which highlight the image regions that have contributed to each prediction. For more information, the user can use a medical viewport to take a closer look at the X-Rays or interact with an integrated chatbot that is based on a large language model. The chatbot has knowledge about the supported diseases and uses the patient context and AI findings to answer questions, explain results, and assist with risk assessment.

### Workflow of the application

The application is build as a web app. It is divided into a frontend (build with Typescript and Svelte), a backend (build with Go), and a separate modelling service. The user starts by uploading one or more chest X-Ray .png images and entering patient information such as age, gender, symptoms, and medical history through the web interface. The application does not support the upload of .dcm images.

The frontend sends the images and patient metadata to the Go backend via REST. The backend then coordinates the analysis workflow: it stores the uploaded images, creates the patient record, and forwards the images to the deep learning modelling service. The modelling service preprocesses the images and uses the trained multi-label model to identify possible abnormalities and calculate a confidence score for each prediction. It also generates heatmaps that indicate which image regions influenced the model's decision.

All analysis results are returned to the backend and saved together with the patient data. The Svelte frontend then presents them in the results page, where users can review the predictions, confidence scores, original images, and corresponding heatmaps. 
The application presents two types of prediction results. Aggregated results and individual results, which are both accompanied with confidence scores that are measured in percentages. The aggregated results are located at the top and show the aggregated, calculated classifications over all the uploaded X-Ray images, while the individual results at the bottom show the calculated classifications for each individual X-Ray image with their respective corresponding heatmaps. The classifications are ranked according to their confidence scores. The confidence threshold for shown classifications can be modified in the GUI with a slider in the results page after the calculation. The dashboard also passes the relevant patient information and findings to the chatbot, allowing the underlying LLM to answer questions, explain the results, and support risk assessment.

The backend uses PostgreSQL for structured patient and analysis data, while Orthanc is used for medical image storage. The chatbot connects to the locally running Ollama service, which provides the language model used for the conversational assistance.

OpenAPI in combination with Swagger are used to construct the REST API and its specification.

Right now, patient data and analysis results are deleted after every new analysis to comply with regulations. But the repository lays the ground work for future contributors to implement persistent databases, as they are already included as Dockerfiles and implementations exist in the backend.


### What did we do with which data

see [Data](#data)

#### Prediction model

<!-- noch aktuell? -->

The prediction model was trained on the mixed data of MIDRC: Open-A1 and the NIH Chest X-Ray Dataset.

#### LLM -> Chatbot

Data for the LLM

### How did we collect the data

Dataset sources \
MIDRC: https://www.midrc.org/midrc-data \
NIH: https://www.kaggle.com/datasets/nih-chest-xrays/data



## Contributing and locally starting the application

### Running the application

#### Prerequisites for running the application

The application runs all required services in containers, so no separate installation of any programming language or database is needed.
For most OS just install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/). If you use NixOS or Arch-based systems just install the Docker Engine. For MacOS you can install Colima instead to your liking.

#### Starting the application
Open a terminal in the project root directory and run:

```bash
docker compose build
docker compose up -d
<!-- Dieses exec ding muss man eigentlich nicht machen oder?? -->
docker compose exec ollama ollama pull phi3:mini 
```

The first command builds the application images and only has to be executed once, as long as the code stays unchanged. The second command starts the images and has to be executed every time the application is to be started. The last command downloads the language model used by the chatbot and is only required once.

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

### Contributing

#### Frontend

##### Prerequisites

1. Install nvm and the current NodeJS version with npm as seen in the tutorial [https://nodejs.org/en/download/current](https://nodejs.org/en/download/current)
2. Navigate into the frontend folder and execute 
```bash
npm install
```
to install all dependencies

##### Running and Testing the Frontend

If you only want to start the frontend, execute ``npm run dev``. Make sure the Docker is not running or else the ports overlap.
If you want to see changes to the frontend, the Docker images are running, and it is not important for you that only the frontend is running, you do not have to execute ``npm run dev`` to start the frontend. You can just use Docker for development purposes. Live reload is included. 

To to test the frontend there are multiple commands that serve different purposes. The most important two are:

```bash
npm run test
```
Starts the unit tests, which are implemented using vitest as recommended by the Svelte team [https://svelte.dev/docs/svelte/testing](https://svelte.dev/docs/svelte/testing).

```bash
npm run test:e2e
```
Starts the E2E tests, which are implemented using Playwright.

#### Backend

##### Prerequisites

1. Install go as instructed here [https://go.dev/doc/install](https://go.dev/doc/install)
2. Run 
```bash
go mod tidy
```
to install all dependencies
3. You maybe have to write ``export PATH=$PATH:$(go env GOPATH)/bin`` into your .bashrc

##### Testind the Backend

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
├── midrc_download_manifest.json     ← gen3-client download list
├── midrc_processed_manifest.csv     ← Processed image manifest
└── combined_master.csv              ← Final training dataset
```

### Pipeline Execution Order

Each step reads the output of the previous one. Run from the project root.

```bash
# Step 1: Download NIH dataset to Kaggle cache + create pointer file (skips if cached)
python src/model/construct_data/get_nih_data.py

# Step 2: Query MIDRC cloud API → generates download manifest (skips if manifest exists)
python src/model/construct_data/get_midrc_data.py          # add --force to re-query

# Step 3: Download DICOM zips via gen3-client → data_hybrid/midrc_dicoms/ (skips completed)
python src/model/construct_data/download_midrc_data.py

# Step 4: Convert DICOMs → 512×512 PNGs with CLAHE + auto-rotation (skips existing PNGs)
python src/model/train/processing.py

# Step 5: Merge NIH + MIDRC into combined_master.csv (2:1 ratio, patient-level)
python src/model/construct_data/blend_data.py

# Step 6: Compute dataset-specific normalization (mean/std)
python src/model/train/compute_dataset_stats.py

# Step 7: Train the model
python src/model/train/train.py
```

All steps are idempotent — re-running any step skips work already done.

### What Each Step Does

| Step | Script | Input | Output | Skip Logic |
|------|--------|-------|--------|------------|
| 1 | `get_nih_data.py` | Kaggle API | Kaggle cache + `nih_images/path.txt` | `kagglehub` skips cached downloads |
| 2 | `get_midrc_data.py` | MIDRC Gen3 API | `midrc_download_manifest.json` | Skips if manifest exists (`--force` to re-query) |
| 3 | `download_midrc_data.py` | manifest JSON | `data_hybrid/midrc_dicoms/` | `--skip-completed` flag |
| 4 | `processing.py` | DICOM zips | 512×512 PNGs + `midrc_processed_manifest.csv` | Skips if output PNG already exists |
| 5 | `blend_data.py` | NIH cache + MIDRC manifest | `combined_master.csv` | Always rewrites (deterministic, fast) |
| 6 | `compute_dataset_stats.py` | `combined_master.csv` | `dataset_stats.json` | Always rewrites (deterministic, fast) |
| 7 | `train.py` | `combined_master.csv` + stats | `dual_view_checkpoint.pth` | Resumes from checkpoint if available |

### Processing Details

**DICOM → PNG (Step 4)** applies:
- MONAI `ScaleIntensityRangePercentiles(0.5, 99.5)` windowing
- CLAHE adaptive histogram equalization (clip_limit=0.02)
- MONOCHROME1 photometric inversion (both Strategy A and fallback)
- Auto-rotation of landscape images to portrait (width > height → rotate 90°)
- Resize to 512×512, saved as 8-bit grayscale

**Data Blending (Step 5)** applies:
- NIH: 14 pathologies from `Data_Entry_2017.csv`, filtered to PA/AP views only
- MIDRC: COVID=1, all other pathologies=0
- 2:1 ratio (NIH:MIDRC) via patient-level random sampling
- Stratified by patient (not image) to prevent data leakage

**Training (Step 7)** uses:
- ConvNeXt-Base backbone (pretrained)
- 384×384 resolution
- Dataset-specific normalization (computed in Step 6)
- sqrt-scaled `pos_weight` BCE loss for class imbalance
- CosineAnnealing LR scheduler
- Patient-stratified 80/10/10 train/val/test split

## Start Docker environment on Windows/Mac and prepare for the project
- download Docker Desktop and start or download docker package
- (optional) download 'Devcontainer Extention' for VSCode
- ``docker compose build`` (execute the first time before starting and also after every change in the requirements.txt, package.json or go.mod/go.sum)
- ``docker compose up`` to run 

## Delete Docker Volumes (and data!)
good if fundamental changes haven been made in the code and they should be visible in the containers
- ``docker compose down -v``

## Run the Frontend
- install (nvm and) Typescript
- ``nvm on``
- ``nvm install latest``
- ``nvm use [installed version]``
- In the Frontend File: ``npm run dev``

## Start the Chatbot
1. boot up the stack:
    - ``docker compose up -d``
2. open the web app and click the bot button in the bottom right corner to start chatting

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
3. **Register the fine-tuned model** (uses the GGUF in the repo, no extra download) and
   pull the fallback model:
   ```bash
   ollama create trustai-llm -f \
     src/LLM/files/clinical_model_dir/trustai-llm.Modelfile.native
   ollama pull phi3:mini
   ```
4. **Point the containers at the host Ollama** (`.env` is gitignored):
   ```bash
   echo "LLM_URL=http://host.docker.internal:11434" > .env
   docker compose up -d --force-recreate backend modelling
   ```

The Docker `ollama` service stays in compose (internal-only, no published port) as the
default for pure-Docker setups; when `LLM_URL` is set the app uses the native Ollama and
the container simply sits idle.

The fine-tuned model (`trustai-llm:latest`) is registered automatically when the `ollama` container starts (downloaded from Hugging Face, see [LLM model configuration](#llm-model-configuration)). The fallback model `phi3:mini` is pulled automatically as well, so both options in the **Settings → LLM Model** dropdown work out of the box. On the native path, pull it once with `ollama pull phi3:mini`, otherwise the app will return an error when that model is selected.

Notes:
- the models are stored in the ``ollama_data`` volume (container) or ``~/.ollama`` (native), so they survive restarts; re-download only after ``docker compose down -v``
- on the native path both models must be present in the host Ollama: `ollama create trustai-llm -f ...` and `ollama pull phi3:mini` (both one-time per machine)
- optional, to enable the fallback model: ``docker compose exec ollama ollama pull phi3:mini``
- the backend connects to the LLM via ``OLLAMA_URL``/``OLLAMA_MODEL`` — ``OLLAMA_URL`` is ``http://ollama:11434`` by default and overridden by the ``LLM_URL`` env var (see above)
- quick test without the UI: ``curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"message": "hello", "history": []}'``

#### LLM model configuration

The fine-tuned LLM (`trustai-llm:latest`) is registered in the `ollama` container at startup from a GGUF file hosted on Hugging Face. No local model file needs to be present on the developer's machine. The downloaded GGUF is cached in the `llm_models` volume and the registered model in `ollama_data`; the download/registration is skipped if the model already exists.

- **Base model (before fine-tuning):** `unsloth/llama-3-8b-Instruct-bnb-4bit` — the Llama-3-8B-Instruct base model (Meta) in the 4-bit quantized Unsloth variant, used in `src/LLM/ollama_finetune.py`
- **Fine-tuned GGUF repo:** `leoniejkr/trustai-llm-gguf` (public, read-only for everyone — only the account owner can modify the weights)
- **Default GGUF:** `llama-3-8b-Instruct.Q4_K_M.gguf`

**Important:** the 4.9 GB model file is **not committed to git** (GitHub rejects files > 100 MB).
Every developer/teacher gets the weights from the HF repo instead — either automatically in
the `ollama` container (see above) or via `ollama create trustai-llm -f ...` in the native
setup. Only code/config lives in git.

The download is skipped if the file already exists (cached in `/models`), and the model is only re-created when necessary. Both sources can be overridden via environment variables:

```yaml
# docker-compose.yaml  (ollama service)
environment:
  HF_MODEL_REPO: leoniejkr/trustai-llm-gguf   # namespace/repo on the HF Hub
  HF_GGUF_FILE: llama-3-8b-Instruct.Q4_K_M.gguf
```

If you host your own copy (e.g. a fork on your own HF account), just point `HF_MODEL_REPO` at it. A **private** repo requires authentication inside the container; for the default **public** repo no token is needed.

The Go backend and the modelling service use `OLLAMA_MODEL` (default `trustai-llm:latest`) to talk to the LLM. The model actually used per request is chosen in the **Settings → LLM Model** dropdown of the web app (`trustai-llm:latest` or `phi3:mini`); `phi3:mini` must be pulled manually if you want to use it.

## Production-Deployment und Docker Hub

Der Dev-Workflow (`docker-compose.yaml`: Live-Reload + Volume-Mounts) ist nicht zum
Publizieren gedacht. Dafür gibt es separate Production-Builds (in den Dockerfiles als
`target: prod`) und ein eigenes Compose-File.

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
- **Modelling**: das trainierte Modell (`./checkpoints/dual_view_checkpoint.pth`, 28 MB)
  ist im Repo versioniert und wird beim Docker-Build ins Image gebacken; gestartet wird
  es als gunicorn-Worker.
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

1. Registry-Namespace im Compose-File setzen (`laterne/trustai-...` → `<user>/<name>`).
2. `docker login`
3. `docker compose -f docker-compose.prod.yaml build`
4. `docker compose -f docker-compose.prod.yaml push`

Danach kann der Stack statt mit den `build:`-Blöcken mit den veröffentlichten `image:`-Namen
ausgerollt werden.

## Update Swagger
- ``swag init --dir ./cmd/server,./internal/api --output ./docs``

## The Use-Case Flow 
### Explanation of Terminus 
#### Blob URL
Temporary URL that directly references in-browser memory. Is generated by the browser locally and allows to view pictures and videos without having to download them or transfer them through a webserver and back into frontend.
Only exists in current browser tab. Closing the browser tab removes the blob URL. Refreshing the website removed the blob URL. Not a real URL, thus does not get uploaded into internet which makes the process very fast.

<!-- ## Docker Umgebung auf Windows/Mac starten und für Projekt vorbereiten
- Docker Desktop herunterladen und starten oder docker package herunterladen
- "Devcontainer Extention" für VSCode herunter laden (optional)
- ``docker compose build`` (Auch bei jeder Änderung der requirements.txt, package.json oder go.mod/go.sum ausführen)
- ``docker compose up``

## Docker Volumes (und damit ganze "Daten") löschen
Gut wenn man grundlegendere Änderungen im Code gemacht hat und diese in den Containern wiederspiegeln lassen möchte
- ``docker compose down -v``

## Frontend zum laufen bringen
- (nvm und) Typescript installieren 
- ``nvm on``
- ``nvm install latest``
- ``nvm use [version die installiert wurde]``
- Im Frontend Ordner: ``npm run dev``

## Swagger updaten
- ``swag init --dir ./cmd/server,./internal/api --output ./docs``

## Den Nutzerflow testen
1. Docker hochfahren ``docker compose up -d``
2. über den Upload Patientendaten hochladen
3. PostgreSQL prüfen:
    - ``psql -h localhost -p 5432 -U trustai_user -d trustai_db -c "SELECT * FROM patients;"``
4. Orthanc prüfen:
    - ``curl -u user:user http://localhost:8042/instances | python3 -m json.tool``
5. Prüfen, ob die Daten zusammenhängend stimmen. Die x_ray_paths in der Patient-Tabelle sind die Orthanc Instance UUIDs:   
    - ``SELECT x_ray_paths::text FROM patients;``
    - UUIDS sollten mit den IDs aus dem http://localhost:8042/instances übereinstimmen -->
 