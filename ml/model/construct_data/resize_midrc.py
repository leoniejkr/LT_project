#!/usr/bin/env python3
"""
One-time preprocessing: downscale the huge orientation-fixed MIDRC PNGs
(up to ~4400x3610 px, up to 21 MB) to a small working size so DataLoader
workers don't re-decode 48 GB of full-res X-rays on every epoch.

Outputs geometry such that len(longer side) == TARGET_SIZE, aspect preserved.
train.py then applies ResizeLongest(RESOLUTION) + SquarePad as before; the only
difference is the model receives a slightly more aggressive 1024->384
downscale instead of 4400->384, which is visually negligible but ~30x cheaper
on memory and page cache.

Usage:
    python ml/model/construct_data/resize_midrc.py \
        --src data_hybrid/midrc_fixed_images \
        --dst data_hybrid/midrc_fixed_1024 \
        --size 1024
"""

import argparse
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # allow 4400px+ images (PIL safety limit)


def process_one(args):
    src, dst, size = args
    try:
        with Image.open(src) as img:
            w, h = img.size
            scale = size / max(w, h)
            if scale >= 1.0:
                shutil.copyfile(src, dst)
                return src, "copied (already small)", None
            new_w, new_h = round(w * scale), round(h * scale)
            img_resized = img.resize((new_w, new_h), Image.LANCZOS)
            img_resized.save(dst, format="PNG")
            return src, f"resized {w}x{h} -> {new_w}x{new_h}", None
    except Exception as e:
        return src, "", str(e)


def main():
    parser = argparse.ArgumentParser(description="Downscale MIDRC fixed PNGs once")
    parser.add_argument("--src", default="data_hybrid/midrc_fixed_images")
    parser.add_argument("--dst", default="data_hybrid/midrc_fixed_1024")
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    os.makedirs(args.dst, exist_ok=True)
    files = sorted(f for f in os.listdir(args.src) if f.endswith(".png"))
    print(f"Found {len(files)} PNGs in {args.src}")

    jobs = [
        (os.path.join(args.src, f), os.path.join(args.dst, f), args.size)
        for f in files
    ]
    ok = errors = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_one, j): j for j in jobs}
        for i, fut in enumerate(as_completed(futures), 1):
            src, msg, err = fut.result()
            if err:
                errors += 1
                print(f"  ERROR {os.path.basename(src)}: {err}")
            else:
                ok += 1
            if i % 100 == 0:
                print(f"  {i}/{len(jobs)} done ({ok} ok, {errors} errors)")

    print(f"\nDone: {ok} ok, {errors} failed -> {args.dst}")


if __name__ == "__main__":
    main()
