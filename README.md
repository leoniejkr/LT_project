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
Backend, frontend, LLM, and classifier each have their own Dockerfile and run in different containers.

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
frontend settings (ConvNeXt-Base by default). Alongside it, Swin-B and
DenseNet-121 are available, plus two **ensembles** that average the sigmoid
probabilities of their members — one across the three architectures, one across
three ConvNeXt checkpoints — which lifts ROC-AUC slightly; no retraining, the
members are the same checkpoints. Each classifier applies its own
training-matching preprocessing
(the selected model's `INPUT_SIZE` + dataset normalization) and uses it to
identify possible abnormalities and
calculate a confidence score for each prediction. The confidence score is a
certainty estimation showing how certain the model is for each prediction. It
also generates heatmaps in png format that indicate which image regions
influenced the model's decision. 

The patient metadata is not used for the model classification but is instead forwarded to the LLM as metadata. The LLM can help the user better regarding possible questions with the metadata. 

All analysis results and heatmap images are returned to the backend. The analysis results are saved in Postgresql and the heatmaps are saved in the Orthanc database. After the application/json results from the POST request are received by the frontend, the frontend extracts the Orthanc image ids of all images and sends a GET /api/patients/{id}/images/{imageID} to the backend for each of them. The backend sends the raw png byte stream back to the frontend. When all Orthanc images are returned, the frontend automatically navigates to the result page, where users can see the original images through a CornerstoneJS medical viewer. Furthermore, the analysis results such as the predictions, confidence scores and corresponding heatmaps can be reviewed.

The application presents two types of prediction results. Aggregated results and individual results, which are both accompanied with confidence scores that are measured in percentages. The aggregated results are located at the top and show the aggregated, calculated classifications over all the uploaded X-Ray images, while the individual results at the bottom show the calculated classifications for each individual X-Ray image with their respective corresponding heatmaps. The classifications are ranked according to their confidence scores. The confidence threshold for shown classifications can be modified in the GUI with a slider in the results page after the calculation. The dashboard also passes the relevant patient information and findings to the chatbot, allowing the underlying LLM to answer questions, explain the results, and support risk assessment.

When the user asks a follow-up question in the chat panel on the results page, the frontend sends the message to the Go backend via the /api/chat REST endpoint. The browser never contacts the language model itself: the backend combines the conversation so far with the patient's metadata and the model's findings as a system message, forwards it to Ollama's /api/chat endpoint, and returns the generated answer to the frontend, where it appears in the chat panel. Ollama runs our fine-tuned trustai-llm model (Llama-3-8B) and is part of the Docker Compose setup, so it requires no separate installation and is started automatically together with the application.

The patient data, X-Ray images and analysis results are stored in Postgresql and Orthanc and can be re-viewed on the history page of the application at a later point.
The history page shows all previous analysis results. These can be deleted individually via the /api/patients/{id} endpoint with a DELETE request or collectively via the /api/analysis endpoint with a DELETE request. A stored analysis can also be exported as a PDF via GET /api/patients/{id}/export, and the whole history as a ZIP via GET /api/export.

This document only sketches the two models. For the precise details see the dedicated READMEs: [X-ray classifier](/ml/model/train/README.md) for how the dataset is built, how images are preprocessed, and how the backbones are trained, [Evaluation](/ml/model/evaluate/README.md) for the measured performance on a held-out test split, and [LLM](/ml/LLM/README.md) for how the fine-tuned Llama-3-8B was trained and how it is prompted at runtime.

For more precise information about the frontend and backend workflow see [Frontend](/frontend/README.md) and [Backend](/backend/README.md). The production runtime is drawn in [architecture_flowchart.mmd](architecture_flowchart.mmd) (Mermaid).

## How to run and start the application

Everything runs in Docker containers, so the only thing to install locally is
Docker itself ([Docker Desktop](https://www.docker.com/products/docker-desktop/),
Docker Engine on NixOS/Arch, or Colima on macOS).

From the project root:

```bash
git lfs install    # X-ray checkpoints ship via Git LFS; without this they are pointer files
git lfs pull
docker compose up -d --build
```

Then open [http://localhost:5173](http://localhost:5173) in a browser. The
fine-tuned LLM is downloaded by the `ollama` container on its first start, so the
first run takes a few minutes.

After that `docker compose up -d` is enough — the build is only needed when the
code changed. `docker compose down` stops the services; application data and the
downloaded models live in Docker volumes and survive, so add `-v` only if you
want to delete them too.
