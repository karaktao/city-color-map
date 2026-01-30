"""
download_images.py

Modified version:
    Supports generator-based (yield) log output,
    designed for FastAPI streaming responses.
"""

from pathlib import Path
import csv
import requests
import numpy as np
import cv2
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Maximum length of the longest image side after resizing (pixels)
MAX_LONG_SIDE = 512


def _resize_keep_ratio(img_bgr, max_long_side=MAX_LONG_SIDE):
    """
    Resize the image while keeping aspect ratio,
    ensuring the longest side does not exceed max_long_side.
    """
    h, w = img_bgr.shape[:2]
    long_side = max(h, w)
    if long_side <= max_long_side:
        return img_bgr  # Already small enough

    scale = max_long_side / long_side
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized


def run_download_images(project_dir):
    """
    Generator function:
    Gradually yields log strings instead of executing everything at once.
    Intended for FastAPI streaming output.
    """
    project_dir = Path(project_dir)
    csv_path = project_dir / "data" / "csv" / "images_meta.csv"
    img_dir = project_dir / "data" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        yield f"[WARN] CSV file not found: {csv_path}. Please run parse_json first.\n"
        return

    # 1. Read all rows first to get total count (for progress display)
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_count = len(rows)
    yield f"[INFO] Found {total_count} image records. Starting processing...\n"

    # 2. Iterate and download images
    for index, row in enumerate(rows):
        img_id = row.get("id")
        url = row.get("thumb_2048_url")

        # Progress prefix, e.g. [1/50]
        prefix = f"[{index + 1}/{total_count}]"

        if not img_id or not url:
            continue

        out_path = img_dir / f"{img_id}.jpg"
        if out_path.exists():
            # yield f"[INFO] {prefix} Already exists, skipping {img_id}\n"
            # To avoid flooding logs, skip messages can be commented out
            continue

        yield f"[INFO] {prefix} Downloading {img_id} ...\n"

        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            # ---- 1. Decode bytes into a BGR image ----
            data = np.frombuffer(resp.content, np.uint8)
            img_bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)

            if img_bgr is None:
                yield f"[WARN] {prefix} Failed to decode image, skipping {img_id}\n"
                continue

            # ---- 2. Resize: reduce resolution ----
            img_small = _resize_keep_ratio(img_bgr, MAX_LONG_SIDE)

            # ---- 3. Save resized image ----
            cv2.imwrite(str(out_path), img_small)

            # (Optional) Small delay to avoid overwhelming the frontend renderer
            # time.sleep(0.05)

        except Exception as e:
            yield f"[WARN] {prefix} Failed to download or save {img_id}: {e}\n"

    yield "[SUCCESS] ✅ All images have been processed.\n"


def _cli_default():
    """
    Compatibility mode for direct script execution:
    Iterates through the generator and prints logs,
    preserving the original CLI behavior.
    """
    print("Running download_images in CLI mode...")
    for log in run_download_images(PROJECT_ROOT):
        print(log, end="")  # log already contains '\n'


if __name__ == "__main__":
    _cli_default()
