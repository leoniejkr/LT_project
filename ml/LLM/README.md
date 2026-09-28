# TrustAI Clinical LLM

The X-ray classifier says *what* it sees. This LLM provides the **clinical
interpretation**: symptoms, causes, diagnosis, treatment and prognosis for every
finding, contextualized with the patient's own metadata.

> Fine-tuned locally from **Llama-3-8B-Instruct** with **QLoRA**, exported to
> **GGUF `Q4_K_M`** and served by **Ollama** as `trustai-llm:latest` — fully local,
> no inference data leaves the machine.

---

## Contents

| # | Section | What it covers |
|---|---------|----------------|
| — | [At a glance](#at-a-glance) | Key facts in one table |
| — | [Pipeline](#pipeline) | The seven stages, end to end |
| — | [Repository layout](#repository-layout) | Which file does what |
| — | [How the model reaches the app](#how-the-model-reaches-the-app) | Runtime download, registration, model selection |
| **I** | **[Training data: scraping](#i-targeted-scraping)** | **Web search per label, 21 curated pages, 16 files** |
| **II** | **[Training data: structuring](#ii-llm-schema-structuring)** | **Prose → strict prompt → JSON, 11 clinical fields** |
| **III** | **[Training data: auditing](#iii-audit--unrolling)** | **Key mapping, unrolling, CSV + JSONL output** |
| IV | [Building the JSONL](#iv-building-the-jsonl) | Turning records into training examples |
| V | [Training preparation](#v-training-preparation) | Chat template, 4-bit base, LoRA |
| VI | [Training](#vi-training) | `SFTTrainer` and the hyper-parameters |
| VII | [Merge & export](#vii-merge--export) | GGUF, verification, artifacts |
| — | [Use cases](#use-cases) | A. Information box · B. Chatbot |
| — | [Reproducing the pipeline](#reproducing-the-pipeline) | End-to-end rebuild |
| — | [Limitations & intended use](#limitations--intended-use) | What this model is not |

---

## At a glance

| | |
|---|---|
| **Base model** | `unsloth/llama-3-8b-Instruct-bnb-4bit` (Llama-3-8B-Instruct, 4-bit) |
| **Method** | QLoRA — LoRA `r=16`, `alpha=16`, on `q/k/v/o_proj`, 60 steps |
| **Training corpus** | 117 examples from 16 curated medical source files |
| **Training runtime** | Google Colab, single consumer GPU |
| **Export format** | GGUF `Q4_K_M` (≈ 4.9 GB), adapters merged into base weights |
| **Served as** | `trustai-llm:latest` via Ollama |
| **Weights source** | [`leoniejkr/trustai-llm-gguf`](https://huggingface.co/leoniejkr/trustai-llm-gguf) — too large for Git, so downloaded at container start |
| **Fallback model** | `phi3:mini` (faster, weaker), selectable per analysis |
| **Inference parameters** | `temperature 0.3`, `num_ctx 8192`, `num_predict 1024`, `repeat_penalty 1.25` |

---

## Pipeline

```text
                      21 curated medical pages
                      (15 classifier labels)
                             │
  I.   Targeted Scraping  ───┤  manual source selection
                             ▼
  II.  Schema Structuring ───┤  page text + strict prompt
                             │     → JSON (11 clinical fields)
                             ▼
  III. Audit & Unrolling ────┤  inspect_json.py
                             │   ├─ key audit & mapping
                             │   ├─ unrolling subtypes & etiologies
                             │   └─ attribute normalization
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
  ┌───────────────────────┐     ┌───────────────────────┐
  │ medical_dataset_       │     │ fine_tuning_ready.     │
  │ flattened.csv          │     │ jsonl                  │
  │ 117 records · 18 cols  │     │ 117 chat examples      │
  │ (tabular / SQL)        │     │ (LLM fine-tuning)      │
  └───────────────────────┘     └───────────────────────┘
              │                             │
              └──────────────┬──────────────┘
                             ▼
  IV.  Build JSONL      ─────┤  system / user / assistant
                             ▼
  V.   Training Preparation───┤  chat template · QLoRA 4-bit · LoRA r=16
                             ▼
  VI.  Training         ─────┤  SFTTrainer, 60 steps
                             ▼
  VII. Merge & Export    ────┤  GGUF Q4_K_M → Ollama
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
  A. Information Box              B. Chatbot
```

Stages **I–III** are how the training data was gathered and is the subject of
[Part 1](#part-1--how-the-training-data-was-gathered). Stages **IV–VII** are the
fine-tune itself, [Part 2](#part-2--fine-tuning).

---

## Repository layout

| Path | Role |
|------|------|
| `files/raw_data/*.json` | 16 raw, LLM-extracted per-condition files |
| `files/medical_dataset_flattened.csv` | 117 normalized records, 18 columns |
| `files/fine_tuning_ready.jsonl` | 117 chat-format training examples |
| `files/clinical_model_dir/Modelfile` | Ollama registration, mounted-path variant |
| `files/clinical_model_dir/trustai-llm.Modelfile.native` | Ollama registration, native (Metal) variant |
| `inspect_json.py` | stages III–IV — audit, unroll, generate both outputs |
| `ollama_finetune.py` | stages V–VII — QLoRA training + GGUF export |
| `testing/test_finetuned.py` | local `llama-cpp` smoke test |

> The `.gguf` itself is **not** in the repository (≈ 4.9 GB). It is downloaded
> from Hugging Face — see [How the model reaches the app](#how-the-model-reaches-the-app).

---

## How the model reaches the app

The 4.9 GB GGUF is too large for GitHub (> 100 MB limit) and for Git LFS (> 2 GB
per-file limit), so **no model file is committed**. Only code and config live in
git; the weights are fetched on demand.

### Container path (default)

The `ollama` service in `docker-compose.yaml` handles everything at startup:

1. Starts `ollama serve`.
2. Downloads `llama-3-8b-Instruct.Q4_K_M.gguf` from
   `leoniejkr/trustai-llm-gguf` into the `llm_models` volume (skipped if cached).
3. Writes a `Modelfile` and registers the model as `trustai-llm:latest`
   (skipped if already registered).
4. Pulls the `phi3:mini` fallback.
5. Restarts `ollama serve` in the foreground.

Both downloads are **idempotent** — they only happen once per machine and survive
`docker compose down`. To force a re-download, use `docker compose down -v`.

Overridable via environment variables:

```yaml
# docker-compose.yaml  (ollama service)
environment:
  HF_MODEL_REPO: leoniejkr/trustai-llm-gguf   # namespace/repo on the HF Hub
  HF_GGUF_FILE: llama-3-8b-Instruct.Q4_K_M.gguf
  OLLAMA_KEEP_ALIVE: -1    # keep weights in memory, avoid slow cold starts
  OLLAMA_LOAD_TIMEOUT: 30m # generous window for slow CPU-only machines
```

### Native path (Ollama on the host)

For running Ollama directly (e.g. Metal-accelerated on macOS), download the GGUF
next to the native Modelfile and register it yourself:

```bash
curl -L --fail -C - \
  -o ml/LLM/files/clinical_model_dir/llama-3-8b-Instruct.Q4_K_M.gguf \
  https://huggingface.co/leoniejkr/trustai-llm-gguf/resolve/main/llama-3-8b-Instruct.Q4_K_M.gguf

ollama create trustai-llm -f \
  ml/LLM/files/clinical_model_dir/trustai-llm.Modelfile.native
ollama pull phi3:mini

# point the containers at the host instance
echo "LLM_URL=http://host.docker.internal:11434" > .env
docker compose up -d --force-recreate backend modelling
```

### The two Modelfiles

Both are kept in the repository because they differ in **how the GGUF is located**:

| File | `FROM` | Context | Used by |
|------|--------|---------|---------|
| `Modelfile` | `/models/llama-3-8b-Instruct.Q4_K_M.gguf` (absolute) | `num_ctx 2048` | container-style setups where the GGUF is mounted |
| `trustai-llm.Modelfile.native` | `./llama-3-8b-Instruct.Q4_K_M.gguf` (relative to the Modelfile) | `num_ctx 8192` | native Ollama, GPU/Metal |

Both set `temperature 0.3` and the same clinical system prompt. The container
entrypoint writes its **own** Modelfile at runtime using the native parameter set
(`num_ctx 8192`, `num_predict 1024`, `repeat_penalty 1.25`) — so the committed
`Modelfile` is a reference for the mounted-path case, not what the running
service uses. The chatbot endpoint applies the same parameters per request
regardless of Modelfile.

### Model selection at runtime

Both features below call whichever model the user picked. The upload page
defaults to `trustai-llm:latest`; **Settings → LLM Model** offers `phi3:mini` as
a faster alternative (`frontend/src/lib/models.ts:45`). The choice travels with
the request as the `llm_model` form field (`backend/internal/api/handler.go:120`),
so the information box and the chatbot always use the same model for one
analysis.

---

# Part 1 — How the training data was gathered

## I. Targeted Scraping

The classifier's 15 labels are fixed (`ALL_CLASSES`,
`services/model-api/model.py:379`), so the corpus has to cover exactly those
findings. We ran a **web search per condition and finding**, then **manually
selected** the authoritative pages worth extracting — Cleveland Clinic, DocCheck
Flexikon, Healthline and Mesothelioma.com. No aggregators, no SEO filler.

**21 pages → extracted text → 16 per-condition JSON files → the 15 labels**

### 1.1 The source pages

<details open>
<summary><strong>All 21 source URLs, grouped by condition</strong></summary>

| # | Condition | Source |
|---|-----------|--------|
| 1 | Emphysema | [Cleveland Clinic — Emphysema](https://my.clevelandclinic.org/health/diseases/9370-emphysema) |
| 2 | Emphysema | [Cleveland Clinic — Bullous emphysema](https://my.clevelandclinic.org/health/diseases/24728-bullous-emphysema) |
| 3 | Emphysema | [Cleveland Clinic — Subcutaneous emphysema](https://my.clevelandclinic.org/health/diseases/subcutaneous-emphysema) |
| 4 | Hernia | [Cleveland Clinic — Hernia](https://my.clevelandclinic.org/health/diseases/15757-hernia#symptoms-and-causes) |
| 5 | Covid | [Cleveland Clinic — COVID pneumonia](https://my.clevelandclinic.org/health/diseases/24002-covid-pneumonia#symptoms-and-causes) |
| 6 | Covid | [Cleveland Clinic — COVID in children](https://my.clevelandclinic.org/health/diseases/covid-in-children#symptoms-and-causes) |
| 7 | Covid | [Cleveland Clinic — COVID while pregnant](https://my.clevelandclinic.org/health/diseases/covid-while-pregnant#symptoms-and-causes) |
| 8 | Covid | [Cleveland Clinic — Long COVID](https://my.clevelandclinic.org/health/diseases/25111-long-covid#symptoms-and-causes) |
| 9 | Pneumonia | [Cleveland Clinic — Pneumonia](https://my.clevelandclinic.org/health/diseases/4471-pneumonia#symptoms-and-causes) |
| 10 | Pneumonia | [Cleveland Clinic — Pneumonia in children & babies](https://my.clevelandclinic.org/health/diseases/pneumonia-in-children-babies#symptoms-and-causes) |
| 11 | Fibrosis | [Cleveland Clinic — Pulmonary fibrosis](https://my.clevelandclinic.org/health/diseases/10959-pulmonary-fibrosis) |
| 12 | Edema | [Cleveland Clinic — Pulmonary edema](https://my.clevelandclinic.org/health/diseases/24218-pulmonary-edema#symptoms-and-causes) |
| 13 | Infiltration | [DocCheck Flexikon — Pulmonale Infiltration](https://flexikon.doccheck.com/de/Pulmonale_Infiltration) |
| 14 | Consolidation | [Healthline — Lung consolidation](https://www.healthline.com/health/lung-consolidation#treatment) |
| 15 | Effusion | [Cleveland Clinic — Pleural effusion](https://my.clevelandclinic.org/health/diseases/17373-pleural-effusion#symptoms-and-causes) |
| 16 | Pneumothorax | [Cleveland Clinic — Catamenial pneumothorax](https://my.clevelandclinic.org/health/diseases/catamenial-pneumothorax#symptoms-and-causes) |
| 17 | Pneumothorax | [Cleveland Clinic — Collapsed lung (pneumothorax)](https://my.clevelandclinic.org/health/diseases/15304-collapsed-lung-pneumothorax#symptoms-and-causes) |
| 18 | Atelectasis | [Cleveland Clinic — Atelectasis](https://my.clevelandclinic.org/health/diseases/17699-atelectasis#symptoms-and-causes) |
| 19 | Cardiomegaly | [Cleveland Clinic — Enlarged heart (cardiomegaly)](https://my.clevelandclinic.org/health/diseases/21490-enlarged-heart-cardiomegaly) |
| 20 | Pleural_Thickening | [Mesothelioma.com — Pleural thickening](https://www.mesothelioma.com/asbestos-cancer/pleural-thickening/) |
| 21 | Mass, Nodule | [Cleveland Clinic — Pulmonary nodules](https://my.clevelandclinic.org/health/diseases/14799-pulmonary-nodules#overview) |

</details>

Several conditions needed **more than one page** on purpose. Emphysema, COVID
and pneumonia each have sub-entities that the classifier treats as the same
label but that a reader would ask about separately — bullous and subcutaneous
emphysema, COVID in children / pregnancy / long COVID, pneumonia in children. One
generic page per label would have left those questions unanswered.

### 1.2 Label → file mapping

The 21 pages collapse into **16 JSON files**, one per condition or sub-entity,
which together cover all 15 classifier labels:

| Label | File(s) | Source # |
|-------|---------|----------|
| `Atelectasis` | `Atelectasis.json` | 18 |
| `Cardiomegaly` | `Cardiomegaly.json` | 19 |
| `Consolidation` | `Lung Consolidation.json` | 14 |
| `Edema` | `Pulmonary edema.json` | 12 |
| `Effusion` | `Pleural effusion.json` | 15 |
| `Emphysema` | `Emphysema.json` · `Bullous_emphysema.json` · `Subcutaneous emphysema.json` | 1 · 2 · 3 |
| `Fibrosis` | `Pulmonary Fibrosis.json` | 11 |
| `Hernia` | `Hernia.json` | 4 |
| `Infiltration` | `Infiltration.json` | 13 |
| `Mass`, `Nodule` | `Pulmonary Nodule and Lung Mass.json` | 21 |
| `Pleural_Thickening` | `Pleural Thickening.json` | 20 |
| `Pneumonia` | `Pneumonia.json` | 9 · 10 |
| `Pneumothorax` | `pneumothorax.json` | 16 · 17 |
| `Covid` | `COVID.json` | 5 · 6 · 7 · 8 |

> **Why manual?** The label set is fixed, so the corpus has to cover exactly
> those 15 findings — curation kept both source quality and coverage under our
> control, which an automated crawl could not guarantee.

---

## II. LLM Schema Structuring

### 2.1 Extracting the page content

The selected pages are prose. We pulled out the **clinically relevant passages**
of each one — symptoms, causes, diagnosis, treatment, prognosis, prevention,
day-to-day management — discarding navigation, adverts and boilerplate.

### 2.2 Making the text machine-readable

Raw prose is not trainable, so the next step was to turn it into **structured
JSON**. For every page, the extracted text was pasted together with a **strict
prompt**, and an LLM returned a JSON array — one object per condition found on
the page.

> The prompt below is reproduced **verbatim**, including its original spelling,
> because it is the exact text that produced every file in `files/raw_data/`.

```text
Extract medical information from the text into a JSON array.

Strict Rule: Extract ONLY information explicitly stated in the text.
Do not add outside medical knowledge.

Schema:
  disease_name      (string)
  symptoms          (array of strings)
  causes            (array of strings)
  treatments        (array of strings)
  life_expectancy   (array of strings)
  outlook           (array of strings)
  diagnosis         (array of strings)
  complications     (array of strings)
  prevention        (array of strings)
  living_with       (array of strings)
  is_contagious     (boolean, or null if unmentioned)

You can make it hierachical when sicknesses depend on one another
```

The **11 clinical fields** are the contract for every later step. Two clauses
carry the weight:

- *"Only what is stated"* — prevents hallucinated, unsourced medical claims.
- *"Can be hierachical"* — sub-conditions (bullous emphysema, COVID in
  children, Long COVID) stay nested under their parent; stage III decides how to
  handle that.

### 2.3 One file per condition

Output: **one JSON file per condition**, named after the condition and stored in
`files/raw_data/` — 16 files in total, e.g. `COVID.json`, `Emphysema.json`,
`Pneumothorax.json`, `Pulmonary Nodule and Lung Mass.json`.

> 16 files, not 15, because sub-entities that share a classifier label
> (bullous emphysema, subcutaneous emphysema) were kept as separate files so
> their nested structure survived into the record structure.

---

## III. Audit & Unrolling

Running [`inspect_json.py`](inspect_json.py) over the raw JSON files converts
messy LLM output into a clean, trainable corpus — one pass, three jobs, two
outputs.

```text
    Raw nested JSONs  (COVID.json, Pneumothorax.json, …  ·  16 files)
                             │
                             ▼
              ┌─────────────────────────────┐
              │ inspect_json Pipeline       │
              │                             │
              │ 1. Key Audit & Mapping      │
              │ 2. Unrolling Subtypes &     │
              │    Etiologies               │
              │ 3. Attribute Normalization  │
              └─────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
  ┌───────────────────────┐     ┌───────────────────────┐
  │ Flattened CSV          │     │ Fine-Tuning JSONL      │
  │ (Tabular / SQL)        │     │ (LLM Fine-Tuning)      │
  │ 117 records · 18 cols  │     │ 117 chat examples      │
  └───────────────────────┘     └───────────────────────┘
```

### ① Data Audit & Normalization

The extraction LLM named the same concept differently across pages —
`transmission_causes` / `causes` / `general_causes`, `diagnosis` /
`diagnosis_methods` / `general_diagnosis_methods`. The script **catalogued every
key variation** it encountered and mapped the equivalent ones onto unified
clinical attributes.

Crucially, any key it does *not* recognize is **reported together with the file
it came from**, so a schema drift can never turn into silent data loss.

### ② Hierarchical Unrolling

Deeply nested structures — subtypes, etiologies, classifications, underlying
conditions, differential diagnoses — were **flattened into individual records
linked back to their parent** via `primary_condition`.

A subtype **inherits any field it does not define itself**, so no record ends up
empty. `target_demographic` is inferred from the record name
(`Pediatric`, `Pregnancy`, `Geriatric`, `General`).

### ③ Dual Output Generation

The normalized records are written in **two formats at once**, from the same
pass:

| Output | Shape | Used for |
|--------|-------|----------|
| `medical_dataset_flattened.csv` | 18 columns, list fields semicolon-separated | tabular analysis, SQL, quick inspection |
| `fine_tuning_ready.jsonl` | `system` / `user` / `assistant` messages | LLM fine-tuning (stage IV) |

**117 records** result: 17 `primary`, 75 `subtype`, 24 `underlying_cause`,
1 `differential_diagnosis`.

```bash
python ml/LLM/inspect_json.py   # from the project root
```

The script ends with a verification report listing every unmapped key and the
files it came from — check that block after any change to the raw data.

---

## IV. Building the JSONL

`fine_tuning_ready.jsonl` uses the standard chat fine-tuning format: one JSON
object per line holding a `messages` array. This is what TRL/Unsloth expect, and
it keeps training aligned with inference.

| Role | Content | Example |
|------|---------|---------|
| `system` | Fixed persona | `You are a clinical reference model trained on structured medical data.` |
| `user` | What a human would type | `Provide a complete clinical overview and management guide for Pulmonary Nodule.` |
| `assistant` | What the model should answer | `**Condition:** …` `**Category:** …` `**Definition:** …` `**Symptoms:** …` `**Causes:** …` `**Diagnosis:** …` `**Treatments:** …` `**Complications:** …` `**Outlook:** …` `**Living With & Management:** …` |

The assistant target is a **structured Markdown answer in a fixed section
order** — that is what makes the fine-tuned model produce consistently parsable
clinical overviews instead of drifting between formats.

---

# Part 2 — Fine-tuning

## V. Training Preparation

[`ollama_finetune.py`](ollama_finetune.py), run in Google Colab.

- **Chat template + tokenization.** `tokenizer.apply_chat_template()` converts
  each conversation into the Llama-3 instruction format
  (`<|begin_of_text|><|start_header_id|>system…`) and tokenizes it, capped at
  `max_seq_length = 2048`. Only then does the trainer see text.
- **Base model, compressed.** `unsloth/llama-3-8b-Instruct-bnb-4bit` with
  `load_in_4bit=True`. **QLoRA** keeps the 8B weights in 4-bit, which is what
  makes fine-tuning fit on a single consumer GPU.
- **LoRA adapters.** The trainable part is small low-rank matrices
  (`r=16`, `alpha=16`, `dropout=0`) on the attention projections `q_proj`,
  `k_proj`, `v_proj`, `o_proj`. The 4-bit base weights stay frozen.

---

## VI. Training

TRL's **`SFTTrainer`** runs the loop. Per step the model predicts the next
token, the prediction is compared to the expected token, the error is
backpropagated, and the **LoRA weights are nudged** to reduce it.

| Parameter | Value |
|-----------|-------|
| `max_steps` | 60 |
| `per_device_train_batch_size` | 2 |
| `gradient_accumulation_steps` | 4 (effective batch 8) |
| `learning_rate` | 2e-4 |
| `warmup_steps` | 5 |
| `max_seq_length` | 2048 |
| `fp16` | true |
| `logging_steps` | 1 |

60 steps on 117 examples is a **light-touch adaptation**: the goal is to teach
the output format and anchor the model to this corpus, not to replace its
pretrained medical knowledge.

---

## VII. Merge & Export

The LoRA adapters are **merged back into the base weights**, producing a single
self-contained model with no adapter dependency at inference time, then exported
to **GGUF** (`q4_k_m`) — the quantized format Ollama serves.

```python
model.save_pretrained_gguf("ml/LLM/files/clinical_model_dir", tokenizer,
                           quantization_method="q4_k_m")
```

Registration is described in
[How the model reaches the app](#how-the-model-reaches-the-app); both Modelfiles
carry the same clinical system prompt:

```text
You are a medical AI assistant analyzing chest X-ray findings. Provide concise,
professional clinical assessments of the detected conditions. Only answer based
on the information provided in the prompt. Be accurate and do not invent
conditions.
```

**Two artifacts come out of this:**

| Artifact | Purpose |
|----------|---------|
| `llama-3-8b-Instruct.Q4_K_M.gguf` | the model the app runs — fetched by the `ollama` container on first start |
| `fine_tuning_ready.jsonl` + `medical_dataset_flattened.csv` | our own use cases: reproducible retraining, evaluation and experiments without re-scraping |

### Verification before serving

[`testing/test_finetuned.py`](testing/test_finetuned.py) loads the GGUF through
`llama-cpp` (`n_gpu_layers=-1` offloads every layer to the GPU) and runs a chat
completion:

```python
llm.create_chat_completion(messages=[
    {"role": "system", "content": "You are a helpful clinical assistant."},
    {"role": "user", "content": "What are the primary symptoms of pneumonia?"}])
```

If the answer comes back in the trained section format (`**Symptoms:** …`,
`**Treatments:** …`) rather than free prose, the fine-tune took.

---

# Part 3 — In the application

## Use cases

Both use cases reach the model through the **Ollama service**, which runs as a
container in the same Docker Compose stack (see the root
[README](../../README.md)), using the model selected per analysis (see
[Model selection at runtime](#model-selection-at-runtime) above).

### A. Natural Language Information Box

A short clinical justification for every finding above the confidence
threshold, shown next to the classification and its heatmap.

`services/model-api/reason_generator.py` builds the prompt from the **patient
metadata** (age, gender, symptoms, history) plus **derived risk cues** (infant /
child / 65+ / pregnant / smoking, spelled out in plain language because small
local models skim raw JSON) and the **predictions with confidence as
percentages**, instructing the model to assess each finding and then tie it back
to *this* patient. Output is a JSON array of `{"class", "reason"}` pairs,
rendered in `frontend/src/routes/result/finding-card.svelte`.

15 conditions at once makes small models drift, so findings are chunked by 6
with up to 3 re-ask rounds for missing or duplicated reasons. If the LLM fails
entirely, a deterministic fallback reason keeps the result page working.

### B. Integrated Chatbot

A free-text chat widget on the result page for follow-up questions about the
analysis.

`POST /api/chat` (`backend/internal/api/handler.go:238`) forwards to Ollama's
`/api/chat` (`backend/internal/chat/service.go:39`) with `temperature 0.3`,
`num_ctx 8192`, `num_predict 1024`, `repeat_penalty 1.25`. The frontend builds
the context (`frontend/src/routes/result/+page.svelte:43`) from patient metadata
**and** all predictions with confidence scores; the backend injects it as an
extra **system message** declaring the data to be treated as **confirmed fact**,
plus the same derived risk cues as the information box — so both features reason
about the patient identically.

> The chatbot is mounted only on the result page; the history page has no chat.

---

## Reproducing the pipeline

```bash
# 1–4. Rebuild the corpus from the curated JSON files (run from the project root)
python ml/LLM/inspect_json.py

# 5–7. Fine-tune + export — open ml/LLM/ollama_finetune.py in Google Colab
#      and run all cells (requires a GPU; the 4-bit base keeps it to one card).

# Verification (local, needs llama-cpp-python)
python ml/LLM/testing/test_finetuned.py

# Registration — see "How the model reaches the app" above
ollama create trustai-llm -f ml/LLM/files/clinical_model_dir/trustai-llm.Modelfile.native
```

Stages I and II are not scripted: the pages were curated and extracted by hand,
so re-running them means re-doing the curation in `files/raw_data/`. Everything
downstream of that is one command.

---

## Limitations & intended use

- **Not a medical device.** TrustAI is a research/educational prototype. Neither
  the classifier nor the LLM output is a diagnosis, and nothing here replaces a
  radiologist or clinical judgement.
- **Corpus size.** 117 training examples is a format-and-anchoring fine-tune, not
  a knowledge base. The model inherits most of its medical knowledge from
  Llama-3 pretraining, and its clinical grounding is limited to the ~22 pages
  listed in [stage I](#i-targeted-scraping).
- **Grounding is prompt-based.** Both features inject patient data as system
  context. They do not retrieve from a medical database, so statements outside
  the injected context come from the base model's weights and can be wrong.
- **Not evaluated clinically.** No benchmark, no reader study, no sensitivity /
  specificity analysis against real cases. Confidence scores come from the
  *classifier*, not from the LLM, and are not calibrated probabilities.
- **Small models drift.** Chunking and re-asks mitigate this, they do not
  eliminate it. Treat the chatbot as a summarizing aid, not an authority.
- **Sources are public patient-education pages.** They are written for lay
  readers and are not a substitute for clinical guidelines.
