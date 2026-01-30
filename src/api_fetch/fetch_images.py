"""
fetch_images.py

Batch fetch street-level image metadata from the Mapillary Graph API
and save each page of JSON results into the data/raw/ directory.

This file can be used in two ways:
1) Called by FastAPI: run_fetch_images(project_dir)
2) Run as a standalone script: python src/api_fetch/fetch_images.py
"""

import json
import time
import re
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ================== Configuration ==================

ACCESS_TOKEN = "MLY|25127541310273769|fe32f1ed00dec71d413c5f9cb19005d7"

# Fallback default bbox when no bbox configuration is provided
# west,south,east,north
DEFAULT_BBOX = "6.865833,52.205278,6.917778,52.233889"

FIELDS = "id,thumb_2048_url,computed_geometry"

# ✅ Mapillary max limit per request
LIMIT = 2000

BASE_URL = "https://graph.mapillary.com/images"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GLOBAL_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# ✅ Required request interval 0.3~0.6s, default 0.4s
# Smaller = faster, but more likely to trigger rate limiting or timeouts
REQUEST_INTERVAL = 0.4

# ====== Tile slicing configuration ======
TILE_SIZE_DEG = 0.01        # Use 0.005 if tiles are too dense and time out (more requests)
TILE_OVERLAP_RATIO = 0.05

# ====== Retry configuration ======
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 1.0

# ✅ Request timeout (seconds)
REQUEST_TIMEOUT = 120

# ✅ Tile-level concurrency
MAX_TILE_WORKERS = 3

# ✅ Record failed tiles
WRITE_FAILED_TILES = True

# ✅ Resume mode: only retry failed tiles (recommended True)
ONLY_FAILED_TILES = True

# ✅ Reuse HTTP connections (faster and more stable)
SESSION = requests.Session()

# ===========================================


def dms_to_decimal(code: str) -> float:
    hemi = code[0].upper()
    digits = code[1:]
    deg = int(digits[0:3])
    minute = int(digits[3:5])
    second = int(digits[5:7])
    decimal = deg + minute / 60 + second / 3600
    if hemi in ("S", "W"):
        decimal = -decimal
    return decimal


def parse_bbox_code(code: str) -> str:
    if not code:
        raise ValueError("Empty BBOX_CODE")

    pattern_defg = re.compile(r"\$\$([defg])([NSEW]\d{7})", re.IGNORECASE)
    values = {m.group(1).lower(): m.group(2) for m in pattern_defg.finditer(code)}
    if len(values) == 4:
        west = dms_to_decimal(values["d"])
        east = dms_to_decimal(values["e"])
        north = dms_to_decimal(values["f"])
        south = dms_to_decimal(values["g"])
        return f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}"

    pattern_ts = re.compile(r"\$\$t([NSEW]\d{7})\$\$s([NSEW]\d{7})", re.IGNORECASE)
    lon_list, lat_list = [], []
    for m in pattern_ts.finditer(code):
        lon_list.append(dms_to_decimal(m.group(1)))
        lat_list.append(dms_to_decimal(m.group(2)))

    if lon_list and lat_list:
        west = min(lon_list)
        east = max(lon_list)
        south = min(lat_list)
        north = max(lat_list)
        return f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}"

    raise ValueError("Unsupported or incomplete BBOX_CODE format")


def _resolve_bbox_from_project(project_dir: Path) -> str:
    project_dir = Path(project_dir)
    config_path = project_dir / "config.json"
    bbox = DEFAULT_BBOX

    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read {config_path}, using default bbox. Error: {e}")
            return bbox

        cfg_bbox = (config.get("bbox") or "").strip()
        cfg_code = (config.get("bbox_code") or "").strip()

        if cfg_bbox:
            print(f"[INFO] Decimal bbox loaded from {config_path}: {cfg_bbox}")
            return cfg_bbox

        if cfg_code:
            print(f"[INFO] bbox_code found in {config_path}, attempting to parse...")
            try:
                parsed = parse_bbox_code(cfg_code)
                print(f"[INFO] bbox_code parsed successfully: {parsed}")
                return parsed
            except Exception as e:
                print(f"[WARN] Failed to parse bbox_code, using default bbox. Error: {e}")

        print(f"[INFO] No valid bbox in config.json, using DEFAULT_BBOX = {bbox}")
        return bbox

    print(f"[INFO] {config_path} not found, using DEFAULT_BBOX = {bbox}")
    return bbox


def _parse_bbox_str(bbox: str):
    w, s, e, n = [float(x.strip()) for x in bbox.split(",")]
    if e <= w or n <= s:
        raise ValueError(f"Invalid bbox: {bbox}")
    return w, s, e, n


def _format_bbox(w: float, s: float, e: float, n: float) -> str:
    return f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}"


def _tile_bboxes(big_bbox: str, tile_size: float, overlap_ratio: float):
    w, s, e, n = _parse_bbox_str(big_bbox)
    step = tile_size * (1.0 - overlap_ratio)
    if step <= 0:
        raise ValueError("overlap_ratio too large, resulting in step <= 0")

    tiles = []
    y = s
    while y < n:
        y2 = min(y + tile_size, n)
        x = w
        while x < e:
            x2 = min(x + tile_size, e)
            tiles.append(_format_bbox(x, y, x2, y2))
            x += step
        y += step
    return tiles


# ================== Global rate limiter (shared across threads) ==================

_rate_lock = threading.Lock()
_last_request_ts = 0.0


def _global_rate_limit_sleep(min_interval: float):
    """Ensure a shared minimum request interval across all threads."""
    global _last_request_ts
    with _rate_lock:
        now = time.time()
        wait = (_last_request_ts + min_interval) - now
        if wait > 0:
            time.sleep(wait)
        _last_request_ts = time.time()


# ================== Request with retry (429 / 5xx / timeout with backoff) ==================

_PRINTED_VERSION = False
_print_lock = threading.Lock()


def _request_with_retry(url: str, params: dict, timeout: int):
    global _PRINTED_VERSION
    with _print_lock:
        if not _PRINTED_VERSION:
            print(f"[FETCH_IMAGES_VERSION] timeout={timeout} LIMIT={params.get('limit')} file={__file__}")
            print(f"[FETCH_IMAGES_VERSION] workers={MAX_TILE_WORKERS} interval={REQUEST_INTERVAL}s tile={TILE_SIZE_DEG} overlap={TILE_OVERLAP_RATIO}")
            print(f"[FETCH_IMAGES_VERSION] ONLY_FAILED_TILES={ONLY_FAILED_TILES}")
            _PRINTED_VERSION = True

    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _global_rate_limit_sleep(REQUEST_INTERVAL)

            resp = SESSION.get(url, params=params, timeout=timeout)

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                retry_after = resp.headers.get("Retry-After")
                sleep_s = float(retry_after) if retry_after else (BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
                print(f"[WARN] Status {resp.status_code}, retry {attempt}/{MAX_RETRIES} after {sleep_s:.1f}s")
                time.sleep(sleep_s)
                continue

            resp.raise_for_status()
            return resp

        except Exception as e:
            last_err = e
            sleep_s = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            print(f"[WARN] Request failed: {e}, retry {attempt}/{MAX_RETRIES} after {sleep_s:.1f}s")
            time.sleep(sleep_s)

    raise RuntimeError(f"Request failed after {MAX_RETRIES} retries: {last_err}")


# ================== Concurrent tile fetching (pagination per tile is sequential) ==================

_page_lock = threading.Lock()


def _next_page(counter: dict) -> int:
    with _page_lock:
        counter["page"] += 1
        return counter["page"]


def _process_one_tile(
    tile_index: int,
    tile_bbox: str,
    big_bbox_safe: str,
    raw_dir: Path,
    page_counter: dict,
    failed_tiles: list,
    failed_lock: threading.Lock,
):
    """Fetch one tile. Pagination inside a tile must remain sequential."""
    after_cursor = None

    params = {
        "access_token": ACCESS_TOKEN,
        "bbox": tile_bbox,
        "fields": FIELDS,
        "limit": LIMIT,
    }

    print(f"[INFO] TILE {tile_index} bbox={tile_bbox}")

    while True:
        if after_cursor:
            params["after"] = after_cursor
        elif "after" in params:
            params.pop("after")

        req = requests.Request("GET", BASE_URL, params=params).prepare()
        print(f"[DEBUG] TILE {tile_index} request URL: {req.url}")

        try:
            resp = _request_with_retry(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            print(f"[ERROR] TILE {tile_index} failed, skipping tile. Error: {e}")
            with failed_lock:
                failed_tiles.append({"tile_index": tile_index, "tile_bbox": tile_bbox, "error": str(e)})
            break

        data = resp.json()
        items = data.get("data", [])
        current_page = _next_page(page_counter)

        out_path = raw_dir / f"images_bbox_{big_bbox_safe}_limit{LIMIT}_page{current_page}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        print(f"[INFO] Page {current_page}: saved {len(items)} records (from tile {tile_index})")

        paging = data.get("paging", {})
        after_cursor = paging.get("cursors", {}).get("after")
        if not after_cursor:
            break


# ================== Resume support: pages + failed tiles ==================

def _resume_page_from_raw(raw_dir: Path, big_bbox_safe: str) -> int:
    pages = []
    pattern = f"images_bbox_{big_bbox_safe}_limit{LIMIT}_page*.json"
    for p in raw_dir.glob(pattern):
        try:
            num = int(p.stem.split("_page")[-1])
            pages.append(num)
        except Exception:
            pass
    return max(pages) if pages else 0


def _failed_tiles_path(raw_dir: Path, big_bbox_safe: str) -> Path:
    return raw_dir / f"failed_tiles_bbox_{big_bbox_safe}.json"


def _load_failed_tiles(raw_dir: Path, big_bbox_safe: str) -> list:
    p = _failed_tiles_path(raw_dir, big_bbox_safe)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _merge_failed_tiles(old_list: list, new_list: list) -> list:
    """
    Deduplicate by tile_bbox.
    Keep the most recent error record.
    """
    merged = {}
    for x in old_list:
        bbox = x.get("tile_bbox")
        if bbox:
            merged[bbox] = x
    for x in new_list:
        bbox = x.get("tile_bbox")
        if bbox:
            merged[bbox] = x

    def _key(v):
        return (v.get("tile_index") is None, v.get("tile_index", 10**9))

    return sorted(merged.values(), key=_key)


def _fetch_images_core(raw_dir: Path, bbox: str):
    raw_dir.mkdir(parents=True, exist_ok=True)

    big_bbox = bbox
    big_bbox_safe = big_bbox.replace(",", "_")

    all_tiles = _tile_bboxes(big_bbox, tile_size=TILE_SIZE_DEG, overlap_ratio=TILE_OVERLAP_RATIO)

    resume_from = _resume_page_from_raw(raw_dir, big_bbox_safe)
    page_counter = {"page": resume_from}
    print(f"[RESUME] Resuming from page {page_counter['page'] + 1} (max existing page={resume_from})")

    prev_failed = _load_failed_tiles(raw_dir, big_bbox_safe)
    if prev_failed:
        print(f"[RESUME] Found {len(prev_failed)} previously failed tiles")

    if ONLY_FAILED_TILES and prev_failed:
        tiles = [x["tile_bbox"] for x in prev_failed if x.get("tile_bbox")]
        print(f"[RESUME] ONLY_FAILED_TILES=True, retrying {len(tiles)} / {len(all_tiles)} tiles")
    else:
        tiles = all_tiles
        if ONLY_FAILED_TILES and not prev_failed:
            print("[RESUME] ONLY_FAILED_TILES=True, but no failed tiles found. Fetching all tiles.")

    print(f"[INFO] Starting Mapillary fetch (tile concurrency mode), big_bbox={big_bbox}")
    print(f"[INFO] Processing {len(tiles)} tiles (tile_size={TILE_SIZE_DEG}, overlap={TILE_OVERLAP_RATIO}), workers={MAX_TILE_WORKERS}")

    failed_tiles = []
    failed_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=MAX_TILE_WORKERS) as ex:
        futures = []
        for idx, tile_bbox in enumerate(tiles, start=1):
            futures.append(
                ex.submit(
                    _process_one_tile,
                    idx,
                    tile_bbox,
                    big_bbox_safe,
                    raw_dir,
                    page_counter,
                    failed_tiles,
                    failed_lock,
                )
            )

        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                print(f"[ERROR] Tile worker exception: {e}")

    if WRITE_FAILED_TILES:
        merged_failed = _merge_failed_tiles(prev_failed, failed_tiles)
        if merged_failed:
            fail_path = _failed_tiles_path(raw_dir, big_bbox_safe)
            with fail_path.open("w", encoding="utf-8") as f:
                json.dump(merged_failed, f, ensure_ascii=False, indent=2)
            print(f"[WARN] Failed tile records written ({len(merged_failed)} entries): {fail_path}")
        else:
            print("[INFO] No failed tiles in this run")

    print(f"[DONE] Fetch completed. Total pages: {page_counter['page']} "
          f"(IDs may overlap across tiles; deduplicate by id during parsing)")


def run_fetch_images(project_dir):
    project_dir = Path(project_dir)
    raw_dir = project_dir / "data" / "raw"
    bbox = _resolve_bbox_from_project(project_dir)
    _fetch_images_core(raw_dir, bbox)


def _cli_default():
    print("[INFO] Running fetch_images.py as a standalone script using GLOBAL_RAW_DIR and DEFAULT_BBOX")
    _fetch_images_core(GLOBAL_RAW_DIR, DEFAULT_BBOX)


if __name__ == "__main__":
    _cli_default()
