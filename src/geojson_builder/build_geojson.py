"""
build_geojson.py

Purpose:
    - Read images_meta.csv (id + longitude + latitude + thumb_url)
    - Read color_summary.csv (dominant color palette + ratios per image)
    - Join the two datasets by image_id
    - Generate a GeoJSON point layer for frontend visualization

Two usage modes:

A) Command-line mode (original mode):
    Input:
        PROJECT_ROOT/data/csv/images_meta.csv
        PROJECT_ROOT/data/csv/color_summary.csv
    Output:
        PROJECT_ROOT/web/public/data/city_colors.geojson
    Run:
        python src/geojson_builder/build_geojson.py

B) FastAPI multi-project mode:
    Input:
        projects/{project_name}/data/csv/images_meta.csv
        projects/{project_name}/data/csv/color_summary.csv
    Output:
        projects/{project_name}/data/geojson/facade_colors.geojson
    Call:
        build_geojson.run_build_geojson(project_dir)
"""

from pathlib import Path
import csv
import json
import ast

# Repository root directory: .../city-color-map/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ====== Mode A: default paths for command-line usage (global) ======
DEFAULT_META_CSV = PROJECT_ROOT / "data" / "csv" / "images_meta.csv"
DEFAULT_COLOR_CSV = PROJECT_ROOT / "data" / "csv" / "color_summary.csv"
DEFAULT_OUT_GEOJSON = PROJECT_ROOT / "web" / "public" / "data" / "city_colors.geojson"
# ==================================================================


def load_metadata(path: Path):
    """
    Read images_meta / image_metadata CSV.

    Returns:
        dict: image_id -> dict(lon=..., lat=..., thumb_url=...)

    Supports two possible field name conventions:
        - id / image_id
        - thumb_2048_url / thumb_url
    """
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"[ERROR] Metadata CSV not found: {path}")

    meta = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle alternative field names
            image_id = row.get("image_id") or row.get("id")
            thumb_url = row.get("thumb_url") or row.get("thumb_2048_url")
            lon = row.get("lon")
            lat = row.get("lat")

            if not image_id or lon is None or lat is None:
                continue
            try:
                lon_f = float(lon)
                lat_f = float(lat)
            except ValueError:
                continue

            meta[image_id] = {
                "lon": lon_f,
                "lat": lat_f,
                "thumb_url": thumb_url,
            }

    print(f"[INFO] Loaded {len(meta)} metadata records from {path.name}")
    return meta


def load_colors(path: Path):
    """
    Read color_summary.csv.

    Returns:
        dict: image_id -> dict(palette_rgb=[[r,g,b], ...], ratios=[...])

    The image_id is derived from the 'file' field by removing
    '_building_shadowfree'.
    """
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"[ERROR] Color CSV not found: {path}")

    color_map = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row.get("file")
            if not fname:
                continue

            # file example: "123456_building_shadowfree.png"
            if "_building_shadowfree" in fname:
                image_id = fname.split("_building_shadowfree", 1)[0]
            else:
                image_id = Path(fname).stem

            raw_palette = row.get("palette_rgb", "")
            raw_ratios = row.get("ratios", "")

            # Values are stored as Python-style strings in CSV
            try:
                palette = ast.literal_eval(raw_palette)
                ratios = ast.literal_eval(raw_ratios)
            except Exception:
                continue

            if not isinstance(palette, list) or not isinstance(ratios, list):
                continue
            if len(palette) == 0 or len(palette) != len(ratios):
                continue

            color_map[image_id] = {
                "palette_rgb": palette,
                "ratios": ratios,
            }

    print(f"[INFO] Loaded {len(color_map)} color records from {path.name}")
    return color_map


def rgb_to_hex(rgb):
    """Convert [R, G, B] to '#rrggbb'."""
    r, g, b = [int(max(0, min(255, x))) for x in rgb]
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def build_features(meta_map, color_map):
    """
    Merge metadata and color data to build a list of GeoJSON Features.
    """
    features = []
    common_ids = set(meta_map.keys()) & set(color_map.keys())
    print(f"[INFO] Number of matched image_id entries: {len(common_ids)}")

    for image_id in common_ids:
        m = meta_map[image_id]
        c = color_map[image_id]

        lon = m["lon"]
        lat = m["lat"]
        thumb_url = m.get("thumb_url")

        palette = c["palette_rgb"]
        ratios = c["ratios"]

        # Use the first color as the dominant color
        main_rgb = palette[0]
        main_ratio = float(ratios[0]) if ratios else None
        main_hex = rgb_to_hex(main_rgb)

        # Corresponding palette image filename (under data/palettes)
        palette_image_name = f"{image_id}_palette.png"
        # Relative path for frontend access (can be adjusted depending on deployment)
        palette_image_path = f"/data/palettes/{palette_image_name}"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "image_id": image_id,
                "lon": lon,
                "lat": lat,
                "thumb_url": thumb_url,
                "main_color_rgb": main_rgb,
                "main_color_hex": main_hex,
                "main_ratio": main_ratio,
                "palette_rgb": palette,
                "ratios": ratios,
                "palette_image": palette_image_path,
            },
        }
        features.append(feature)

    return features


def build_geojson_from_paths(meta_csv: Path,
                             color_csv: Path,
                             out_geojson: Path) -> Path:
    """
    Generic builder function:
        - Read meta_csv and color_csv
        - Write GeoJSON to out_geojson
        - Return the output path
    """
    meta_map = load_metadata(meta_csv)
    color_map = load_colors(color_csv)
    features = build_features(meta_map, color_map)

    if not features:
        print("[WARN] No Features generated. Check whether image_id values match in both CSV files.")

    out_geojson = Path(out_geojson)
    out_dir = out_geojson.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    fc = {
        "type": "FeatureCollection",
        "features": features,
    }

    with out_geojson.open("w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)

    print(f"[DONE] GeoJSON generated: {out_geojson}, total features: {len(features)}")
    return out_geojson


# ====== FastAPI entry point (multi-project mode) ======
def run_build_geojson(project_dir) -> Path:
    """
    FastAPI mode:
        project_dir = projects/{project_name}

    Input:
        project_dir/data/csv/images_meta.csv
        project_dir/data/csv/color_summary.csv
    Output:
        project_dir/data/geojson/facade_colors.geojson
    """
    project_dir = Path(project_dir)
    meta_csv = project_dir / "data" / "csv" / "images_meta.csv"
    color_csv = project_dir / "data" / "csv" / "color_summary.csv"
    out_geojson = project_dir / "data" / "geojson" / "facade_colors.geojson"

    return build_geojson_from_paths(meta_csv, color_csv, out_geojson)
