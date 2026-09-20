#!/usr/bin/env python3
"""
Simplified download script for MIDRC CT and CXR images with limit support.
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
    p = argparse.ArgumentParser(description="Download MIDRC CXR images")
    p.add_argument("--manifest", default="data_hybrid/midrc_download_manifest.json", help="manifest file")
    p.add_argument("--output-dir", default="data_hybrid/midrc_dicoms", help="Output directory")
    p.add_argument("--credentials", default="credentials.json", help="Gen3 credentials JSON")
    p.add_argument("--workers", type=int, default=8, help="Parallel downloads")
    p.add_argument("--limit", type=int, default=None, help="Limit number of images to download per modality")
    p.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    return p.parse_args()

def check_gen3_client():
    """Check if gen3-client is available."""
    # Check both possible names
    for name in ["gen3-client", "dataclient"]:
        gen3_bin = shutil.which(name)
        if gen3_bin:
            try:
                result = subprocess.run([gen3_bin, "--version"], capture_output=True, text=True)
                log.info(f"{name} found: {result.stdout.strip()}")
                return gen3_bin
            except:
                pass
    
    log.error("gen3-client not found. Install from: https://github.com/uc-cdis/cdis-data-client/releases")
    return None

def configure_gen3_profile(credentials_path, gen3_bin):
    """Configure gen3-client with MIDRC credentials."""
    if not Path(credentials_path).exists():
        log.error(f"Credentials not found: {credentials_path}")
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
        log.error(f"Configure failed: {result.stderr}")
        return False
    
    log.info("Profile configured successfully")
    return True

def create_limited_manifest(manifest_path, limit):
    """Create a temporary manifest with only the first 'limit' entries."""
    if not Path(manifest_path).exists():
        log.error(f"Manifest not found: {manifest_path}")
        return None
    
    with open(manifest_path) as f:
        records = json.load(f)
    
    original_count = len(records)
    
    if limit and limit < original_count:
        limited_records = records[:limit]
        log.info(f"📊 Limiting {Path(manifest_path).name} from {original_count} to {limit} entries")
        
        # Create temporary manifest
        temp_path = Path(manifest_path).parent / f"{Path(manifest_path).stem}_limited.json"
        with open(temp_path, 'w') as f:
            json.dump(limited_records, f, indent=2)
        
        return str(temp_path)
    else:
        log.info(f"Using full manifest with {original_count} entries")
        return manifest_path

def download_manifest(manifest_path, output_dir, workers, gen3_bin, dry_run=False, limit=None):
    """Download images from a manifest file, optionally limited."""
    # Create limited manifest if needed
    manifest_to_use = create_limited_manifest(manifest_path, limit)
    if not manifest_to_use:
        return False
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        gen3_bin, "download-multiple",
        "--profile", "midrc",
        "--manifest", manifest_to_use,
        "--download-path", str(output_path),
        "--numparallel", str(workers),
        "--skip-completed",
        "--protocol", "s3",
    ]
    
    log.info(f"Downloading from: {manifest_to_use}")
    log.info(f"Output: {output_path}")
    
    if dry_run:
        log.info(f"[DRY RUN] Would run: {' '.join(cmd)}")
        return True
    
    result = subprocess.run(cmd)
    if result.returncode != 0:
        log.error(f"Download failed with code {result.returncode}")
        return False
    
    # Count downloaded files
    downloaded = sum(1 for _ in output_path.rglob("*") if _.is_file())
    log.info(f"Downloaded {downloaded} files to {output_path}")
    
    # Clean up temporary manifest
    if manifest_to_use != manifest_path and Path(manifest_to_use).exists():
        Path(manifest_to_use).unlink()
        log.info(f"🧹 Removed temporary manifest: {manifest_to_use}")
    
    return True

def main():
    args = parse_args()
    
    # If no limit specified, set a default of specified limit
    if args.limit is None:
        log.info("Kein Limit angegeben – lade alle verfügbaren Bilder herunter (Max)!")
    else:
        log.info(f"Limit manuell gesetzt auf: {args.limit} Bilder pro Modalität")
    
    # Check for gen3-client
    gen3_bin = check_gen3_client()
    if not gen3_bin:
        log.error("Cannot proceed without gen3-client")
        return 1
    
    # Configure profile
    if not configure_gen3_profile(args.credentials, gen3_bin):
        log.error("Profile configuration failed")
        return 1
    
    # Download 
    log.info("\n" + "="*60)
    log.info("DOWNLOADING IMAGES")
    log.info("="*60)
    ok = download_manifest(
        args.manifest,
        Path(args.output_dir),
        args.workers,
        gen3_bin,
        args.dry_run,
        args.limit
    )
    

    
    # Summary
    log.info("\n" + "="*60)
    log.info("DOWNLOAD SUMMARY")
    log.info("="*60)
    log.info(f" {'SUCCESS' if ok else 'FAILED'}")
    
    if ok :
        log.info("\nAll downloads complete!")
        log.info(f"Files in: {args.output_dir}")
        return 0
    else:
        log.error("\nSome downloads failed")
        return 1

if __name__ == "__main__":
    exit(main())