"""
parse_json.py

Extract image id, url, coordinates, etc. from data/raw/*.json,
perform deduplication + spatial thinning (keep at most 1 image per 50m),
and export to data/csv/images_meta.csv for download_images.py to use.
"""

from pathlib import Path
import json
import csv
import math

# Repository root directory, e.g. D:/tommytao/city-color-map
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ===== Spatial sampling parameters =====
GRID_SIZE_M = 50  # Keep at most 1 image per 50 meters
EARTH_RADIUS_M = 6378137.0  # WGS84

# ===== Utility functions =====

def _lonlat_to_meter(lon, lat):
    """
    Approximate lon/lat to meters (local approximation, suitable for city scale).
    """
    x = math.radians(lon) * EARTH_RADIUS_M * math.cos(math.radians(lat))
    y = math.radians(lat) * EARTH_RADIUS_M
    return x, y


def _grid_cell_id(lon, lat, grid_size_m):
    """
    Compute the grid cell ID for the given point (e.g., 50m grid).
    """
    x, y = _lonlat_to_meter(lon, lat)
    gx = int(x // grid_size_m)
    gy = int(y // grid_size_m)
    return gx, gy


# ===== Single-file parsing =====
def _parse_one_file(json_path: Path, writer: csv.DictWriter, seen_ids: set, used_cells: set, stats: dict):
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data.get("data", []):
        img_id = item.get("id")
        if not img_id:
            stats["skip_no_id"] += 1
            continue

        # ---- Global deduplication (by image id) ----
        if img_id in seen_ids:
            stats["skip_dup_id"] += 1
            continue

        url = item.get("thumb_2048_url")
        if not url:
            stats["skip_no_url"] += 1
            continue

        geom = item.get("computed_geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            stats["skip_no_coord"] += 1
            continue

        lon, lat = coords[0], coords[1]
        if lon is None or lat is None:
            stats["skip_no_coord"] += 1
            continue

        # ---- Spatial thinning: keep at most 1 per 50m grid ----
        cell_id = _grid_cell_id(lon, lat, GRID_SIZE_M)
        if cell_id in used_cells:
            stats["skip_dense"] += 1
            continue

        # ---- Passed filters, write to CSV ----
        seen_ids.add(img_id)
        used_cells.add(cell_id)

        writer.writerow(
            {
                "id": img_id,
                "thumb_2048_url": url,
                "lon": lon,
                "lat": lat,
            }
        )
        stats["written"] += 1


# ===== FastAPI entry point =====
def run_parse_json(project_dir):
    """
    Parse all JSON files under projects/{project_name}/data/raw,
    extract fields -> deduplicate -> spatial thinning (50m),
    and write to projects/{project_name}/data/csv/images_meta.csv
    """
    project_dir = Path(project_dir)
    raw_dir = project_dir / "data" / "raw"
    csv_dir = project_dir / "data" / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    out_csv = csv_dir / "images_meta.csv"

    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print(f"[WARN] No JSON files found under {raw_dir}. Please run fetch_images first.")
        return

    print(f"[INFO] Found {len(json_files)} raw JSON files. Start parsing (50m thinning)...")

    seen_ids = set()
    used_cells = set()
    stats = {
        "written": 0,
        "skip_dup_id": 0,
        "skip_dense": 0,
        "skip_no_id": 0,
        "skip_no_url": 0,
        "skip_no_coord": 0,
    }

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "thumb_2048_url", "lon", "lat"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for jf in json_files:
            print(f"[INFO] Parsing {jf.name}")
            _parse_one_file(jf, writer, seen_ids, used_cells, stats)

    print(f"[DONE] Output written to {out_csv}")
    print(
        f"[STATS] written {stats['written']} | "
        f"dedup_skipped {stats['skip_dup_id']} | "
        f"density_skipped {stats['skip_dense']} | "
        f"missing_id {stats['skip_no_id']} | "
        f"missing_url {stats['skip_no_url']} | "
        f"missing_coord {stats['skip_no_coord']}"
    )


# ===== Command-line compatibility =====
def _cli_default():
    """
    When running parse_json.py directly:
    Default input:  PROJECT_ROOT/data/raw
    Default output: PROJECT_ROOT/data/csv/images_meta.csv
    """
    raw_dir = PROJECT_ROOT / "data" / "raw"
    csv_dir = PROJECT_ROOT / "data" / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    out_csv = csv_dir / "images_meta.csv"

    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print(f"[WARN] No JSON files found under {raw_dir}")
        return

    print(f"[INFO] (CLI) Found {len(json_files)} raw JSON files. Start parsing (50m thinning)...")

    seen_ids = set()
    used_cells = set()
    stats = {
        "written": 0,
        "skip_dup_id": 0,
        "skip_dense": 0,
        "skip_no_id": 0,
        "skip_no_url": 0,
        "skip_no_coord": 0,
    }

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "thumb_2048_url", "lon", "lat"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for jf in json_files:
            print(f"[INFO] (CLI) Parsing {jf.name}")
            _parse_one_file(jf, writer, seen_ids, used_cells, stats)

    print(f"[DONE] (CLI) Output written to {out_csv}")
    print(
        f"[STATS] written {stats['written']} | "
        f"dedup_skipped {stats['skip_dup_id']} | "
        f"density_skipped {stats['skip_dense']}"
    )


if __name__ == "__main__":
    _cli_default()
