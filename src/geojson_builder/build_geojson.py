"""
build_geojson.py

功能：
    读取 images_meta.csv（id + 经纬度 + thumb_url）
    读取 color_summary.csv（每张图的主色列表 + 占比）
    通过 image_id 进行关联，生成给前端用的 GeoJSON 点图层。

两种使用方式：

A) 命令行模式（原来那种）：
    输入：
        PROJECT_ROOT/data/csv/images_meta.csv
        PROJECT_ROOT/data/csv/color_summary.csv
    输出：
        PROJECT_ROOT/web/public/data/city_colors.geojson
    运行：
        python src/geojson_builder/build_geojson.py

B) FastAPI 多项目模式：
    输入：
        projects/{project_name}/data/csv/images_meta.csv
        projects/{project_name}/data/csv/color_summary.csv
    输出：
        projects/{project_name}/data/geojson/facade_colors.geojson
    调用：
        build_geojson.run_build_geojson(project_dir)
"""

from pathlib import Path
import csv
import json
import ast

# 仓库根目录：.../city-color-map/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ====== 模式 A：命令行模式默认路径（全局） ======
DEFAULT_META_CSV = PROJECT_ROOT / "data" / "csv" / "images_meta.csv"
DEFAULT_COLOR_CSV = PROJECT_ROOT / "data" / "csv" / "color_summary.csv"
DEFAULT_OUT_GEOJSON = PROJECT_ROOT / "web" / "public" / "data" / "city_colors.geojson"
# =================================================


def load_metadata(path: Path):
    """
    读取 images_meta / image_metadata CSV
    返回 dict: image_id -> dict(lon=..., lat=..., thumb_url=...)

    兼容两种字段名：
        - id / image_id
        - thumb_2048_url / thumb_url
    """
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"[ERROR] 找不到元数据 CSV：{path}")

    meta = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 兼容字段名
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

    print(f"[INFO] 从 {path.name} 读取到 {len(meta)} 条元数据记录")
    return meta


def load_colors(path: Path):
    """
    读取 color_summary.csv
    返回 dict: image_id -> dict(palette_rgb=[ [r,g,b], ... ], ratios=[...])

    其中 image_id 由 file 字段去掉 '_building_shadowfree' 得到。
    """
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"[ERROR] 找不到颜色 CSV：{path}")

    color_map = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row.get("file")
            if not fname:
                continue

            # file 形如 "123456_building_shadowfree.png"
            if "_building_shadowfree" in fname:
                image_id = fname.split("_building_shadowfree", 1)[0]
            else:
                image_id = Path(fname).stem

            raw_palette = row.get("palette_rgb", "")
            raw_ratios = row.get("ratios", "")

            # CSV 里是 Python 风格字符串，需要解析成对象
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

    print(f"[INFO] 从 {path.name} 读取到 {len(color_map)} 条颜色记录")
    return color_map


def rgb_to_hex(rgb):
    """[R,G,B] -> '#rrggbb'"""
    r, g, b = [int(max(0, min(255, x))) for x in rgb]
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def build_features(meta_map, color_map):
    """
    合并两份数据，构建 GeoJSON Feature 列表
    """
    features = []
    common_ids = set(meta_map.keys()) & set(color_map.keys())
    print(f"[INFO] 可成功关联的 image_id 数量：{len(common_ids)}")

    for image_id in common_ids:
        m = meta_map[image_id]
        c = color_map[image_id]

        lon = m["lon"]
        lat = m["lat"]
        thumb_url = m.get("thumb_url")

        palette = c["palette_rgb"]
        ratios = c["ratios"]

        # 主色取第一个
        main_rgb = palette[0]
        main_ratio = float(ratios[0]) if ratios else None
        main_hex = rgb_to_hex(main_rgb)

        # 对应的色卡文件名（在 data/palettes 下）
        palette_image_name = f"{image_id}_palette.png"
        # 前端可以按这个相对路径访问（你前端怎么部署可以再调整）
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
    通用构建函数：
    - 读 meta_csv + color_csv
    - 写 out_geojson
    - 返回 out_geojson 路径
    """
    meta_map = load_metadata(meta_csv)
    color_map = load_colors(color_csv)
    features = build_features(meta_map, color_map)

    if not features:
        print("[WARN] 没有生成任何 Feature，请检查 image_id 是否能在两份 CSV 中匹配。")

    out_geojson = Path(out_geojson)
    out_dir = out_geojson.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    fc = {
        "type": "FeatureCollection",
        "features": features,
    }

    with out_geojson.open("w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 已生成 GeoJSON：{out_geojson}，共 {len(features)} 个点要素")
    return out_geojson


# ====== 给 FastAPI 用的入口（多项目） ======
def run_build_geojson(project_dir) -> Path:
    """
    FastAPI 模式：
        project_dir = projects/{project_name}

    输入：
        project_dir/data/csv/images_meta.csv
        project_dir/data/csv/color_summary.csv
    输出：
        project_dir/data/geojson/facade_colors.geojson
    """
    project_dir = Path(project_dir)
    meta_csv = project_dir / "data" / "csv" / "images_meta.csv"
    color_csv = project_dir / "data" / "csv" / "color_summary.csv"
    out_geojson = project_dir / "data" / "geojson" / "facade_colors.geojson"

    return build_geojson_from_paths(meta_csv, color_csv, out_geojson)
