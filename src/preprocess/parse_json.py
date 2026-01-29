"""
parse_json.py
从 data/raw/*.json 中提取图片 id、url、坐标等，
汇总到 data/csv/images_meta.csv，供 download_images.py 使用。
"""

from pathlib import Path
import json
import csv

# 仓库根目录，例如 D:/tommytao/city-color-map
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ===== 单文件解析 =====
def _parse_one_file(json_path: Path, writer: csv.DictWriter):
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data.get("data", []):
        img_id = item.get("id")
        url = item.get("thumb_2048_url")

        geom = item.get("computed_geometry") or {}
        coords = geom.get("coordinates") or [None, None]
        # Mapillary 一般是 [lon, lat]
        lon = coords[0] if len(coords) > 0 else None
        lat = coords[1] if len(coords) > 1 else None

        writer.writerow(
            {
                "id": img_id,
                "thumb_2048_url": url,
                "lon": lon,
                "lat": lat,
            }
        )


# ===== 给 FastAPI 用的入口 =====
def run_parse_json(project_dir):
    """
    从 projects/{project_name}/data/raw 下的所有 JSON 中
    提取字段写入 projects/{project_name}/data/csv/images_meta.csv
    """
    project_dir = Path(project_dir)
    raw_dir = project_dir / "data" / "raw"
    csv_dir = project_dir / "data" / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    out_csv = csv_dir / "images_meta.csv"

    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print(f"[WARN] 未在 {raw_dir} 找到任何 JSON 文件，请先调用 fetch_images")
        return

    print(f"[INFO] 共找到 {len(json_files)} 个原始 JSON，开始解析...")
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "thumb_2048_url", "lon", "lat"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for jf in json_files:
            print(f"[INFO] 解析 {jf.name}")
            _parse_one_file(jf, writer)

    print(f"[DONE] 已输出解析结果到 {out_csv}")


# ===== 兼容命令行运行（可选） =====
def _cli_default():
    """
    直接运行 parse_json.py 时：
    默认从 仓库根目录 /data/raw → /data/csv
    方便你单独调试。
    """
    raw_dir = PROJECT_ROOT / "data" / "raw"
    csv_dir = PROJECT_ROOT / "data" / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    out_csv = csv_dir / "images_meta.csv"

    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print(f"[WARN] 未在 {raw_dir} 找到任何 JSON 文件")
        return

    print(f"[INFO] (CLI) 共找到 {len(json_files)} 个原始 JSON，开始解析...")
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "thumb_2048_url", "lon", "lat"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for jf in json_files:
            print(f"[INFO] (CLI) 解析 {jf.name}")
            _parse_one_file(jf, writer)

    print(f"[DONE] (CLI) 已输出解析结果到 {out_csv}")


if __name__ == "__main__":
    _cli_default()
