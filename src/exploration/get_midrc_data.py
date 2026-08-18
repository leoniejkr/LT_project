#!/usr/bin/env python3
"""
scripts/preprocess.py
──────────────────────────────────────────────────────────────────────
Unified MIDRC Data Prep Pipeline:
1. Connects to the cloud API and pulls metadata for COVID-19 cases.
2. Generates the required JSON manifest for gen3-client immediately.
3. If files are downloaded, processes them into 2D PNG images.
"""

import argparse
import io
import json
import logging
import sys
import tempfile
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── Optional MONAI import ──────────────────────────────────────────────────
try:
    import torch
    from monai.transforms import (
        Compose, LoadImage, EnsureChannelFirst, ScaleIntensityRangePercentiles
    )
    from monai.data import ITKReader
    MONAI_AVAILABLE = True
except ImportError:
    MONAI_AVAILABLE = False
    log.warning("MONAI not installed. Processing phase will be unavailable.")

try:
    from gen3.auth import Gen3Auth
    from gen3.submission import Gen3Submission
except ImportError:
    log.error("gen3 package not found. Install with: pip install gen3")
    sys.exit(1)

API        = "https://data.midrc.org"
PROGRAM    = "Open"
PROJECT    = "A1"  
RANDOM_SEED = 42

def clean_id(val) -> str:
    """Removes braces, quotes, brackets, and white space from Gen3 text rows."""
    if pd.isna(val):
        return ""
    return str(val).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

def extract_zip_and_find_dicoms(zip_path: Path, temp_dir: Path) -> Path | None:
    """Extracts zip file and returns the folder containing raw DICOM files."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
    except zipfile.BadZipFile:
        log.error(f"Corrupted zip file skipped: {zip_path}")
        return None
    
    for p in temp_dir.rglob("*"):
        if p.is_dir() and not list(p.iterdir()) == []:
            first_file = next(p.iterdir(), None)
            if first_file and first_file.is_file():
                return p
    return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image-root", default="images/", help="Path where gen3-client saves downloads")
    p.add_argument("--output-dir", default="data_hybrid", help="Target folder for manifests and images")
    args = p.parse_args()

    output_root = Path(args.output_dir)
    midrc_cxr_dir = output_root / "midrc_images"
    
    output_root.mkdir(exist_ok=True, parents=True)
    midrc_cxr_dir.mkdir(exist_ok=True, parents=True)

    # ==============================================================================
    # PHASE 1: AUTH, CLOUD METADATA QUERY, & MANIFEST GENERATION (Always Runs First)
    # ==============================================================================
    try:
        auth = Gen3Auth(API, refresh_file="credentials.json")
        sub  = Gen3Submission(API, auth)
        log.info(f"Connected to {API}")
    except Exception as e:
        log.error(f"Authentication failed: {e}")
        sys.exit(1)

    log.info("Querying 'case' nodes from MIDRC cloud...")
    cases_raw = sub.export_node(PROGRAM, PROJECT, "case", "tsv")
    df_cases  = pd.read_csv(io.StringIO(cases_raw), sep="\t")
    log.info(f"Found {len(df_cases)} overall patient cases.")

    log.info("Querying 'imaging_study' nodes from MIDRC cloud...")
    study_raw = sub.export_node(PROGRAM, PROJECT, "imaging_study", "tsv")
    df_study  = pd.read_csv(io.StringIO(study_raw), sep="\t", low_memory=False)
    log.info(f"Found {len(df_study)} imaging studies.")

    log.info("Querying 'cr_series_file' nodes from MIDRC cloud...")
    cr_raw    = sub.export_node(PROGRAM, PROJECT, "cr_series_file", "tsv")
    df_cr     = pd.read_csv(io.StringIO(cr_raw), sep="\t", low_memory=False)
    log.info(f"Found {len(df_cr)} Computed Radiography series objects available.")

    # ── Filter: body part must be CHEST ──────────────────────────────────────
    CHEST_KEYWORDS = {"CHEST", "CHEST (PORT)", "CHEST PA", "CHEST AP",
                      "CHEST PA AND LAT", "CHEST AP AND LAT", "THORAX"}
    if "body_part_examined" in df_study.columns and "imaging_studies" in df_cr.columns:
        df_cr["_study_id"] = df_cr["imaging_studies"].apply(clean_id)
        df_study["_study_id"] = df_study["submitter_id"].apply(clean_id)
        chest_studies = set(
            df_study[
                df_study["body_part_examined"]
                .fillna("")
                .str.upper()
                .str.strip()
                .isin(CHEST_KEYWORDS)
            ]["_study_id"]
        )
        before = len(df_cr)
        df_cr = df_cr[df_cr["_study_id"].isin(chest_studies)].copy().reset_index(drop=True)
        df_cr.drop(columns=["_study_id"], inplace=True, errors="ignore")
        log.info(
            f"Filtered to {len(df_cr)} chest scans "
            f"(removed {before - len(df_cr)} non-chest body parts)."
        )
    else:
        log.warning("⚠ 'body_part_examined' or 'imaging_studies' not found – skipping body-part filter.")

    # ── Filter: front-facing views only (PA / AP) ───────────────────────────
    FRONT_FACING_VIEWS = {"PA", "AP", "PA AND AP", "AP AND PA"}
    if "view_position" in df_cr.columns:
        before = len(df_cr)
        df_cr = df_cr[
            df_cr["view_position"]
            .fillna("")
            .str.upper()
            .str.strip()
            .isin(FRONT_FACING_VIEWS)
        ].copy().reset_index(drop=True)
        log.info(
            f"Filtered to {len(df_cr)} front-facing (PA/AP) scans "
            f"(removed {before - len(df_cr)} lateral/other views)."
        )
    else:
        log.warning("⚠ 'view_position' column not found in cr_series_file – skipping view filter.")

    # Apply thorough structural string cleaning to links
    df_cases["case_id_clean"] = df_cases["submitter_id"].apply(clean_id)
    df_cr["case_ids_clean"] = df_cr["case_ids"].apply(clean_id)

    # Isolate explicit COVID-19 positive records using a relaxed case-insensitive match
    covid_cases = set(df_cases[df_cases["covid19_positive"].fillna("").str.lower().str.contains("yes|true|1")]["case_id_clean"])
    log.info(f"Identified {len(covid_cases)} COVID-19 positive patient IDs.")

    # Filter our image table down using the matching patient IDs
    df_covid_cxr = df_cr[df_cr["case_ids_clean"].isin(covid_cases)].copy().reset_index(drop=True)
    log.info(f"Filtered down to {len(df_covid_cxr)} matching images belonging to those COVID patients.")

    if len(df_covid_cxr) == 0:
        log.error("❌ ERROR: Structural alignment yielded 0 matching rows. Check project ID configuration.")
        return

    # Cap at a manageable subset size (e.g., up to 1000 records)
    df_covid_cxr = df_covid_cxr.sample(n=min(1000, len(df_covid_cxr)), random_state=RANDOM_SEED).reset_index(drop=True)

    # ── BUILD AND EXPORT THE DOWNLOAD JSON MANIFEST FIRST ───────────────────────
    manifest_objects = []
    for _, row in df_covid_cxr.iterrows():
        manifest_objects.append({
            "object_id": str(row["object_id"]),
            "file_name": str(row["file_name"]),
            "md5sum": str(row["md5sum"]) if pd.notna(row["md5sum"]) else "",
            "file_size": int(row["file_size"]) if pd.notna(row["file_size"]) else 0
        })
    
    json_manifest_path = output_root / "midrc_download_manifest.json"
    with open(json_manifest_path, "w") as f:
        json.dump(manifest_objects, f, indent=2)
        
    log.info(f"✓ GENERATED GEN3 DOWNLOAD MANIFEST: {json_manifest_path}")
    log.info(f"Contains {len(manifest_objects)} targeted cloud object paths.")
