#!/usr/bin/env python3
"""
scripts/download_data.py
────────────────────────
Downloads MIDRC imaging data via the Gen3 client using the manifests
produced by the dataset builder (manifest_ct.json, manifest_cxr.json).

Usage:
    python scripts/download_data.py \
        --manifest-ct  data/manifest_ct.json \
        --manifest-cxr data/manifest_cxr.json \
        --output-dir   images/ \
        --credentials  credentials.json \
        --workers      8

Requirements:
    pip install gen3
    gen3 client binary: https://github.com/uc-cdis/cdis-data-client/releases
    (the Python gen3 SDK wraps this binary for downloads)
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
import shutil
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MIDRC_API = "https://data.midrc.org"


def parse_args():
    p = argparse.ArgumentParser(description="Download MIDRC data via Gen3")
    p.add_argument("--manifest-ct",  default="data/manifest_ct.json")
    p.add_argument("--manifest-cxr", default="data/manifest_cxr.json")
    p.add_argument("--output-dir",   default="images/")
    p.add_argument("--credentials",  default="credentials.json",
                   help="Gen3 credentials JSON (download from MIDRC profile page)")
    p.add_argument("--workers",      type=int, default=8,
                   help="Parallel download threads")
    p.add_argument("--skip-ct",      action="store_true")
    p.add_argument("--skip-cxr",     action="store_true")
    p.add_argument("--dry-run",      action="store_true",
                   help="Print commands without executing")
    p.add_argument("--gen3-path",    default=None,
                   help="Path or name of the gen3-client binary to use (overrides system lookup)")
    p.add_argument("--skip-gen3-check", action="store_true",
                   help="Skip verifying gen3-client is installed (useful when running in container)")
    return p.parse_args()


def check_gen3_client(gen3_path: Optional[str] = None) -> Optional[str]:
    """Verify the gen3-client binary is available.

    Returns the resolved binary path (or name) if available, otherwise None.
    """
    candidate = None

    # If user passed a path or name, prefer that (resolve with shutil.which)
    if gen3_path:
        candidate = shutil.which(gen3_path) or (str(Path(gen3_path)) if Path(gen3_path).exists() else None)
        if candidate:
            try:
                result = subprocess.run([candidate, "--version"], capture_output=True, text=True)
                log.info(f"gen3-client found: {result.stdout.strip()}")
                return candidate
            except FileNotFoundError:
                log.warning(f"Provided gen3-client path not executable: {gen3_path}")

    # Fallback to PATH lookup
    candidate = shutil.which("gen3-client")
    if candidate:
        try:
            result = subprocess.run([candidate, "--version"], capture_output=True, text=True)
            log.info(f"gen3-client found: {result.stdout.strip()}")
            return candidate
        except FileNotFoundError:
            pass

    log.error(
        "gen3-client binary not found.\n"
        "Install it from: https://github.com/uc-cdis/cdis-data-client/releases\n"
        "Example (macOS): curl -L -o /tmp/gen3-client \"https://github.com/uc-cdis/cdis-data-client/releases/download/v4.27.7/gen3-client\" && sudo mv /tmp/gen3-client /usr/local/bin/gen3-client && sudo chmod +x /usr/local/bin/gen3-client\n"
        "Or run inside Docker. Use --gen3-path to point to a custom binary."
    )
    return None


def configure_gen3_profile(credentials_path: str, profile: str = "midrc", gen3_bin: str = "gen3-client") -> bool:
    """Configure a named gen3-client profile from credentials file."""
    cred_path = Path(credentials_path)
    if not cred_path.exists():
        log.error(
            f"Credentials not found: {cred_path}\n"
            "Download from: https://data.midrc.org/identity  →  'Create API key'"
        )
        return False

    cmd = [
        gen3_bin, "configure",
        "--profile",     profile,
        "--cred",        str(cred_path),
        "--apiendpoint", MIDRC_API,
    ]
    log.info(f"Configuring gen3-client profile '{profile}' …")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Configure failed: {result.stderr}")
        return False
    log.info("Profile configured.")
    return True


def merge_manifests(paths: list[str], out_path: str) -> int:
    """Merge multiple manifest JSONs (dedup by object_id) → single file."""
    seen = set()
    merged = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            log.warning(f"Manifest not found: {p}")
            continue
        with open(path) as f:
            records = json.load(f)
        for rec in records:
            oid = rec.get("object_id", "")
            if oid and oid not in seen:
                merged.append(rec)
                seen.add(oid)
    with open(out_path, "w") as f:
        json.dump(merged, f, indent=2)
    log.info(f"Merged manifest: {len(merged)} unique objects → {out_path}")
    return len(merged)


def download_manifest(
    manifest_path: str,
    output_dir: str,
    workers: int,
    profile: str = "midrc",
    dry_run: bool = False,
    gen3_bin: str = "gen3-client",
) -> bool:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        gen3_bin, "download-multiple",
        "--profile",      profile,
        "--manifest",     manifest_path,
        "--download-path", output_dir,
        "--numparallel",  str(workers),
        "--skip-completed",              # resume partial downloads
        "--protocol",     "s3",
    ]

    log.info(f"Download command:\n  {' '.join(cmd)}")

    if dry_run:
        log.info("[DRY RUN] — not executing.")
        return True

    result = subprocess.run(cmd)
    if result.returncode != 0:
        log.error(f"Download exited with code {result.returncode}")
        return False

    return True


def verify_downloads(manifest_path: str, output_dir: str) -> tuple[int, int]:
    """Check how many manifest objects exist on disk."""
    with open(manifest_path) as f:
        records = json.load(f)

    out_root = Path(output_dir)
    found = 0
    missing_ids = []

    for rec in records:
        oid = rec.get("object_id", "")
        # gen3-client creates: <output_dir>/<object_id>/<filename>
        obj_dir = out_root / oid
        if obj_dir.exists() and any(obj_dir.iterdir()):
            found += 1
        else:
            missing_ids.append(oid)

    total = len(records)
    log.info(f"Verification: {found}/{total} objects present on disk")

    if missing_ids:
        missing_log = Path(output_dir) / "_missing_objects.txt"
        with open(missing_log, "w") as f:
            f.write("\n".join(missing_ids))
        log.warning(f"{len(missing_ids)} missing — logged to {missing_log}")

    return found, total


def main():
    args = parse_args()

    gen3_bin = None

    if not args.skip_gen3_check:
        gen3_bin = check_gen3_client(args.gen3_path)
        if not gen3_bin:
            sys.exit(1)
    else:
        if args.gen3_path:
            gen3_bin = args.gen3_path
            log.info(f"Skipping check; will use provided gen3-client path: {gen3_bin}")
        else:
            gen3_bin = "gen3-client"
            log.warning("Skipping gen3-client check; script will attempt to run 'gen3-client' from PATH.")

    if not configure_gen3_profile(args.credentials, gen3_bin=gen3_bin):
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Download CT ──────────────────────────────────────────────────────────
    if not args.skip_ct:
        log.info("\n" + "─" * 60)
        log.info("Downloading CT series …")
        log.info("─" * 60)
        ok = download_manifest(
            manifest_path=args.manifest_ct,
            output_dir=str(out_dir / "ct"),
            workers=args.workers,
            dry_run=args.dry_run,
            gen3_bin=gen3_bin,
        )
        if ok and not args.dry_run:
            found, total = verify_downloads(args.manifest_ct, str(out_dir / "ct"))
            log.info(f"CT:  {found}/{total} series downloaded")

    # ── Download CXR ─────────────────────────────────────────────────────────
    if not args.skip_cxr:
        log.info("\n" + "─" * 60)
        log.info("Downloading CXR series …")
        log.info("─" * 60)
        ok = download_manifest(
            manifest_path=args.manifest_cxr,
            output_dir=str(out_dir / "cxr"),
            workers=args.workers,
            dry_run=args.dry_run,
            gen3_bin=gen3_bin,
        )
        if ok and not args.dry_run:
            found, total = verify_downloads(args.manifest_cxr, str(out_dir / "cxr"))
            log.info(f"CXR: {found}/{total} series downloaded")

    log.info("\nDone. Next step: python scripts/preprocess.py")


if __name__ == "__main__":
    main()
