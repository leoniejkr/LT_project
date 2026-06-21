#!/usr/bin/env python3
"""
Simplified download script for MIDRC CT and CXR images.
"""
import argparse
import json
import logging
import subprocess
from pathlib import Path
import shutil

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MIDRC_API = "https://data.midrc.org"

def parse_args():
    p = argparse.ArgumentParser(description="Download MIDRC CT and CXR images")
    p.add_argument("--manifest-ct", default="data/manifest_ct.json", help="CT manifest file")
    p.add_argument("--manifest-cxr", default="data/manifest_cxr.json", help="CXR manifest file")
    p.add_argument("--output-dir", default="images/", help="Output directory")
    p.add_argument("--credentials", default="credentials.json", help="Gen3 credentials JSON")
    p.add_argument("--workers", type=int, default=8, help="Parallel downloads")
    p.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    return p.parse_args()

def check_gen3_client():
    """Check if gen3-client is available."""
    gen3_bin = shutil.which("gen3-client")
    if gen3_bin:
        try:
            result = subprocess.run([gen3_bin, "--version"], capture_output=True, text=True)
            log.info(f"✅ gen3-client found: {result.stdout.strip()}")
            return gen3_bin
        except:
            pass
    
    log.error("❌ gen3-client not found. Install from: https://github.com/uc-cdis/cdis-data-client/releases")
    return None

def configure_gen3_profile(credentials_path, gen3_bin):
    """Configure gen3-client with MIDRC credentials."""
    if not Path(credentials_path).exists():
        log.error(f"❌ Credentials not found: {credentials_path}")
        log.error("Download from: https://data.midrc.org/identity → 'Create API key'")
        return False
    
    cmd = [
        gen3_bin, "configure",
        "--profile", "midrc",
        "--cred", credentials_path,
        "--apiendpoint", MIDRC_API,
    ]
    log.info("Configuring gen3-client profile...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"❌ Configure failed: {result.stderr}")
        return False
    
    log.info("✅ Profile configured successfully")
    return True

def download_manifest(manifest_path, output_dir, workers, gen3_bin, dry_run=False):
    """Download images from a manifest file."""
    if not Path(manifest_path).exists():
        log.warning(f"⚠️ Manifest not found: {manifest_path}")
        return False
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        gen3_bin, "download-multiple",
        "--profile", "midrc",
        "--manifest", manifest_path,
        "--download-path", str(output_path),
        "--numparallel", str(workers),
        "--skip-completed",
        "--protocol", "s3",
    ]
    
    log.info(f"📥 Downloading from: {manifest_path}")
    log.info(f"📁 Output: {output_path}")
    
    if dry_run:
        log.info(f"[DRY RUN] Would run: {' '.join(cmd)}")
        return True
    
    result = subprocess.run(cmd)
    if result.returncode != 0:
        log.error(f"❌ Download failed with code {result.returncode}")
        return False
    
    # Count downloaded files
    downloaded = sum(1 for _ in output_path.rglob("*") if _.is_file())
    log.info(f"✅ Downloaded {downloaded} files to {output_path}")
    return True

def main():
    args = parse_args()
    
    # Check for gen3-client
    gen3_bin = check_gen3_client()
    if not gen3_bin:
        log.error("Cannot proceed without gen3-client")
        return 1
    
    # Configure profile
    if not configure_gen3_profile(args.credentials, gen3_bin):
        log.error("Profile configuration failed")
        return 1
    
    # Download CT
    log.info("\n" + "="*60)
    log.info("📊 DOWNLOADING CT IMAGES")
    log.info("="*60)
    ct_ok = download_manifest(
        args.manifest_ct,
        Path(args.output_dir) / "ct",
        args.workers,
        gen3_bin,
        args.dry_run
    )
    
    # Download CXR
    log.info("\n" + "="*60)
    log.info("📊 DOWNLOADING CXR IMAGES")
    log.info("="*60)
    cxr_ok = download_manifest(
        args.manifest_cxr,
        Path(args.output_dir) / "cxr",
        args.workers,
        gen3_bin,
        args.dry_run
    )
    
    # Summary
    log.info("\n" + "="*60)
    log.info("📊 DOWNLOAD SUMMARY")
    log.info("="*60)
    log.info(f"CT:  {'✅ SUCCESS' if ct_ok else '❌ FAILED'}")
    log.info(f"CXR: {'✅ SUCCESS' if cxr_ok else '❌ FAILED'}")
    
    if ct_ok and cxr_ok:
        log.info("\n✅ All downloads complete!")
        log.info(f"📁 Files in: {args.output_dir}")
        return 0
    else:
        log.error("\n❌ Some downloads failed")
        return 1

if __name__ == "__main__":
    exit(main())