# __TrustAI__

## Project Summary

### What does the application do

TrustAI is a Medical Prediction AI platform created to support clinicians in assessing chest X-ray images. Its main feature is a deep learning model that analyzes uploaded medical images uploaded in .png format, to detect potential abnormalities, diseases, and other visual findings.

Users can upload one or multiple X-ray images and patient information. The model then generates predictions for possible conditions based on the images and also gives a certainty estimation for each result, which we call confidence scores.

On the results page, the dashboard displays heatmaps which highlight the image regions that have contributed to each prediction. For more information, the user can use a medical viewport to take a closer look at the X-Rays or interact with an integrated chatbot. The chatbot has knowledge about the supported diseases and has access to the patient metadata and model findings.

Previous analysis results can be viewed and deleted on the history page of the application.

#### Example Application:

https://github.com/user-attachments/assets/1a10ae43-8cf5-4fb7-8a14-c307b0627201




### Workflow of the application

#### General information

The application is build as a monorepo web app without any authentication. We decided not to implement authentication services such as Keycloak because we do not plan on hosting this application ourself, but to make it available for private and local use via Docker.

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

All analysis results and heatmap images are returned to the backend. The analysis results are saved in Postgresql and the heatmaps are saved in th Orthanc database. After the application/json results from the POST request are received by the frontend, the frontend extracts the Orthanc image ids of all images and sends a GET /patients/{id}/images{imageIds} to the backend. The backend sends the raw png byte stream back to the frontend. When all Orthanc images are returned, the frontend automatically navigates to the result page, where users can see the original images through a CornerstoneJS medical viewer. Furthermore, the analysis results such as the predictions, confidence scores and corresponding heatmaps can be reviewed.

The application presents two types of prediction results. Aggregated results and individual results, which are both accompanied with confidence scores that are measured in percentages. The aggregated results are located at the top and show the aggregated, calculated classifications over all the uploaded X-Ray images, while the individual results at the bottom show the calculated classifications for each individual X-Ray image with their respective corresponding heatmaps. The classifications are ranked according to their confidence scores. The confidence threshold for shown classifications can be modified in the GUI with a slider in the results page after the calculation. The dashboard also passes the relevant patient information and findings to the chatbot, allowing the underlying LLM to answer questions, explain the results, and support risk assessment.

**ACHTUNG!!!!!!!!??? The chatbot connects to the locally running Ollama service, which provides the language model used for the conversational assistance.**

The patient data, X-Ray images and analysis results are stored in Postgresql and Orthanc and can be re-viewed on the history page of the application at a later point.
The history page shows all previous analysis results. These can be deleted individually via the /api/patient/{id} endpoint with a DELETE request or collectively via the /api/analysis enpoint with a DELETE request. 

For more precise information about the frontend and backend workflow see [Frontend](#frontend) and [Backend](#backend).

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
