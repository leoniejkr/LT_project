#!/usr/bin/env python3
"""Download the model weight files needed by the modelling service.

The weights are NOT in git (too large for GitHub). They are hosted on the
Hugging Face Hub (default repo: leoniejkr/lt-models) and downloaded at
Docker build time, so the resulting image is self-contained and can be
shared directly (docker compose up -d, no model file exchanges).

Usage:
    python download_models.py                      # defaults (build time)
    MODEL_REPO=... MODEL_DIR=./checkpoints python download_models.py
    MODEL_FILES=a.pth,b.pth python download_models.py   # override file list

Adding a future model: append the filename here (or pass it via MODEL_FILES).
No Dockerfile changes needed.
"""

import os

from huggingface_hub import hf_hub_download

DEFAULT_REPO = "leoniejkr/lt-models"
DEFAULT_FILES = [
    "covnext348.pth",
    # "second_model.pth",  # TODO: next trained model
    # "third_model.pth",   # TODO: one more model coming later
]
DEFAULT_DIR = "./checkpoints"


def main() -> None:
    repo = os.getenv("MODEL_REPO", DEFAULT_REPO)
    dest = os.getenv("MODEL_DIR", DEFAULT_DIR)
    files = [f.strip() for f in os.getenv("MODEL_FILES", "").split(",") if f.strip()]
    files = files or DEFAULT_FILES

    os.makedirs(dest, exist_ok=True)
    for name in files:
        print(f"[download_models.py] {repo} -> {dest}/{name}")
        hf_hub_download(
            repo_id=repo,
            filename=name,
            local_dir=dest,
            token=os.getenv("HF_TOKEN") or None,
        )
    print("[download_models.py] all model files ready.")


if __name__ == "__main__":
    main()