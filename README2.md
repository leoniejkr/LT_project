Hybrid Chest X-Ray Multi-Label Training Pipeline

This repository contains an end-to-end medical deep learning pipeline designed to blend the NIH Chest X-Ray 14 dataset with the MIDRC COVID-14 dataset. The framework targets a unified 15-class multi-label classification taxonomy utilizing standard medical imaging processing protocols, parallelized data pipelines, and real-time remote experiment tracking.

Repository Directory Structure:

├── data_hybrid/
│   ├── midrc_images/              # Standardized 2D PNG outputs from MIDRC DICOMs
│   ├── combined_master.csv        # Final balanced, unified dataset manifest
│   ├── midrc_download_manifest.json
│   └── midrc_processed_manifest.csv
├── frontend/                      # Optional web deployment / visualization workspace
├── images/                        # Stage repository for raw incoming zip payloads
├── main/                          # Alternative entrypoints / orchestration scripts
└── src/
    ├── exploration/               # Dataset diagnostic scripts & target listings
    │   ├── available_conditions.txt
    │   ├── available_observations.txt
    │   └── explore_available_conditions.py
    ├── blend_data.py              # Compiles and aligns NIH and MIDRC metadata structures
    ├── datasets.py                # PyTorch Dataset construction and mapping utilities
    ├── download_midrc_data.py     # Automates retrieval of targeted COVID-19 cohorts
    ├── get_midrc_data.py          # Formulates cohorts and extracts manifest filters
    ├── get_nih_data.py            # Local cache integration layer for Kaggle NIH assets
    ├── lightning_module.py        # Lightning wrapper (Optional structure alternative)
    ├── processing.py              # Standardizes DICOM files via MONAI pipeline & CLAHE contrast
    └── train.py                   # Patient-grouped training pipeline with Weights & Biases


1. Data Acquisition & Processing Pipeline

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

2. Model Training Engine
The pipeline is set up for multi-label classification using ResNet50, applying weighted binary cross-entropy loops to tackle severe dataset imbalances.

To start training, execute:

    python3 src/train.py

