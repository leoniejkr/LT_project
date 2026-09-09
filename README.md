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

This repository contains an end-to-end medical deep learning pipeline designed to blend the NIH Chest X-Ray 14 dataset with the MIDRC COVID-14 dataset. The framework targets a unified 15-class multi-label classification taxonomy utilizing standard medical imaging processing protocols, parallelized data pipelines, and real-time remote experiment tracking.



#### 1. Data Acquisition & Processing Pipeline

The dataset is compiled sequentially to isolate, transform, and balance raw arrays before feeding them into your deep learning architectures.

    Step A: Fetch & Build the Metadata Framework
    Run the target extraction layers to parse the raw index configurations:

        python3 src/get_nih_data.py
        python3 src/get_midrc_data.py
        python3 src/download_midrc_data.py

    Step B: Standardize DICOM Images
    Raw medical imaging files have distinct structural variations. Run the processing module to apply adaptive histogram transformations (CLAHE) and reshape spatial domains using MONAI's robust fallback architecture:

        python3 src/processing.py

    This handles unusual shapes, flattens extra dimension layers, resolves MONOCHROME1 inversions, and builds high-contrast, uniform 2D gray grids saved natively to data_hybrid/midrc_images/.

    Step C: Blend the Manifests
    To link your physical assets on disk directly to a unified classification matrix, run the data blending engine:

        python3 src/blend_data.py

    This module extracts image paths dynamically, drops unretrieved arrays safely, maps pipe-separated categorical tags, and outputs a clean dataset tracking ledger to data_hybrid/combined_master.csv.

#### 2. Model Training Engine
The pipeline is set up for multi-label classification using ResNet50, applying weighted binary cross-entropy loops to tackle severe dataset imbalances.

To start training, execute:

    python3 src/train.py

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
1. boot up Docker so the ollama service is running:
    - ``docker compose up -d``
2. pull the LLM model into the ollama container (only needed once, ~2.2 GB):
    - ``docker compose exec ollama ollama pull phi3:mini``
3. open the web app and click the bot button in the bottom right corner to start chatting

Notes:
- the model is stored in the ``ollama_data`` volume, so it survives restarts; re-pull only after ``docker compose down -v``
- the backend connects to ollama via ``OLLAMA_URL``/``OLLAMA_MODEL`` (configured in docker-compose.yaml)
- quick test without the UI: ``curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"message": "hello", "history": []}'``

## Production-Deployment und Docker Hub

Der Dev-Workflow (`docker-compose.yaml`: Live-Reload + Volume-Mounts) ist nicht zum
Publizieren gedacht. Dafür gibt es separate Production-Builds (in den Dockerfiles als
`target: prod`) und ein eigenes Compose-File.

### Produktions-Stack lokal starten

```bash
docker compose -f docker-compose.prod.yaml up -d
docker compose -f docker-compose.prod.yaml exec ollama ollama pull phi3:mini
```

Danach läuft die App unter [http://localhost](http://localhost). Ein nginx-Reverse-Proxy
ist der einzige Einstiegspunkt: `/` → Frontend (SvelteKit-SSR), `/api/*` → Go-Backend
(das `/api`-Präfix wird entfernt), `/swagger/` → Swagger-UI.

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
 