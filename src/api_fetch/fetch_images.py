"""
fetch_images.py
从 Mapillary Graph API 批量获取街景图片元数据，并把每一页的 JSON
保存到 data/raw/ 目录下。

本文件既可以：
1）被 FastAPI 调用：run_fetch_images(project_dir)
2）也可以单独运行：python src/api_fetch/fetch_images.py
"""

import json
import time
import re
from pathlib import Path

import requests

# ================== 配置区 ==================

ACCESS_TOKEN = "MLY|25127541310273769|fe32f1ed00dec71d413c5f9cb19005d7"

# 如果完全没有 bbox 配置时的“兜底默认值”
# west,south,east,north
DEFAULT_BBOX = "6.865833,52.205278,6.917778,52.233889"

FIELDS = "id,thumb_2048_url,computed_geometry"
LIMIT =3000
BASE_URL = "https://graph.mapillary.com/images"

# 仓库根目录（例如 D:/tommytao/city-color-map）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 单独脚本运行时使用的 data/raw 目录（不走多项目结构）
GLOBAL_RAW_DIR = PROJECT_ROOT / "data" / "raw"

REQUEST_INTERVAL = 0.2

# ===========================================


def dms_to_decimal(code: str) -> float:
    """将 E0065157 / N0521402 这类 DMS 编码转成十进制度数"""
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
    """
    支持两种格式：
    1) 四个角点直接给 d/e/f/g：
       $$dE0065157$$eE0065504$$fN0521402$$gN0521219
       -> west, east, north, south

    2) 多个 t/s 点（t=经度，s=纬度），例如：
       $$tE0065737$$sN0521230$$tE0065718$$sN0521231...
       从所有点里取 min/max 组成 bbox

    返回十进制 bbox 字符串: "west,south,east,north"
    """
    if not code:
        raise ValueError("空的 BBOX_CODE")

    # ---- 尝试 1：d/e/f/g 经典格式 ----
    pattern_defg = re.compile(r"\$\$([defg])([NSEW]\d{7})", re.IGNORECASE)
    values = {m.group(1).lower(): m.group(2) for m in pattern_defg.finditer(code)}

    if len(values) == 4:
        west = dms_to_decimal(values["d"])   # min_lon
        east = dms_to_decimal(values["e"])   # max_lon
        north = dms_to_decimal(values["f"])  # max_lat
        south = dms_to_decimal(values["g"])  # min_lat
        return f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}"

    # ---- 尝试 2：t/s 成对出现的多边形格式 ----
    # 形如 $$tE0065737$$sN0521230
    pattern_ts = re.compile(r"\$\$t([NSEW]\d{7})\$\$s([NSEW]\d{7})", re.IGNORECASE)
    lon_list = []
    lat_list = []

    for m in pattern_ts.finditer(code):
        lon_code = m.group(1)
        lat_code = m.group(2)
        lon_list.append(dms_to_decimal(lon_code))
        lat_list.append(dms_to_decimal(lat_code))

    if lon_list and lat_list:
        west = min(lon_list)
        east = max(lon_list)
        south = min(lat_list)
        north = max(lat_list)
        return f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}"

    # 两种格式都不符合，抛异常
    raise ValueError("BBOX_CODE 格式不完整或不支持的格式")


def _resolve_bbox_from_project(project_dir: Path) -> str:
    """
    从项目目录读取 config.json 中的 bbox / bbox_code，
    如果没有或解析失败，则回退到 DEFAULT_BBOX。
    """
    project_dir = Path(project_dir)
    config_path = project_dir / "config.json"

    # 先设一个兜底值
    bbox = DEFAULT_BBOX

    # 1. 看看 config.json 是否存在
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"[WARN] 无法读取 {config_path}，使用默认 bbox. 错误: {e}")
            return bbox

        # 优先使用已经解析好的十进制 bbox
        cfg_bbox = (config.get("bbox") or "").strip()
        cfg_code = (config.get("bbox_code") or "").strip()

        # 情况 A：有十进制 bbox，直接用
        if cfg_bbox:
            print(f"[INFO] 从 {config_path} 读取十进制 bbox = {cfg_bbox}")
            return cfg_bbox

        # 情况 B：十进制没有，但有 bbox_code，就尝试解析
        if cfg_code:
            print(f"[INFO] 从 {config_path} 读取 bbox_code，尝试解析...")
            try:
                parsed = parse_bbox_code(cfg_code)
                print(f"[INFO] bbox_code 解析成功: {parsed}")
                return parsed
            except Exception as e:
                print(f"[WARN] bbox_code 解析失败，将使用默认 bbox. 错误: {e}")

        # 两个都没有或解析失败，就走默认
        print(f"[INFO] config.json 中没有有效 bbox，使用默认 DEFAULT_BBOX = {bbox}")
        return bbox

    # 2. 没有 config.json，完全使用默认值
    print(f"[INFO] 未找到 {config_path}，使用默认 DEFAULT_BBOX = {bbox}")
    return bbox


def _fetch_images_core(raw_dir: Path, bbox: str):
    """
    实际抓取 Mapillary 数据的核心函数。
    raw_dir: JSON 输出目录
    bbox:   "west,south,east,north"
    """
    raw_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "access_token": ACCESS_TOKEN,
        "bbox": bbox,
        "fields": FIELDS,
        "limit": LIMIT,
    }

    page = 1
    total_count = 0
    after_cursor = None

    print(f"[INFO] 开始抓取 Mapillary 数据，bbox={bbox}")

    while True:
        if after_cursor:
            params["after"] = after_cursor
        elif "after" in params:
            params.pop("after")

        # —— 打印出 Python 实际请求的完整 URL —— 
        req = requests.Request("GET", BASE_URL, params=params).prepare()
        print("[DEBUG] 请求 URL:", req.url)

        resp = requests.get(BASE_URL, params=params, timeout=30)

        # —— 不要立刻 raise_for_status，先看看返回内容 —— 
        print("[DEBUG] 状态码:", resp.status_code)
        print("[DEBUG] 响应内容前 300 字符:", resp.text[:300])

        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        total_count += len(items)

        bbox_safe = bbox.replace(",", "_")
        out_path = raw_dir / f"images_bbox_{bbox_safe}_limit{LIMIT}_page{page}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[INFO] 第 {page} 页：保存 {len(items)} 条记录")

        paging = data.get("paging", {})
        after_cursor = paging.get("cursors", {}).get("after")

        if not after_cursor:
            print("[INFO] 抓取完成")
            break

        page += 1
        time.sleep(REQUEST_INTERVAL)

    print(f"[DONE] 共获取 {total_count} 条记录")


# ========= 提供给 FastAPI 调用的入口 =========
def run_fetch_images(project_dir):
    """
    给 FastAPI 用的函数：
    - project_dir: projects/{project_name} 目录
    - 从 config.json 读取 bbox/bbox_code
    - 输出到 project_dir/data/raw/
    """
    project_dir = Path(project_dir)
    data_dir = project_dir / "data"
    raw_dir = data_dir / "raw"

    bbox = _resolve_bbox_from_project(project_dir)
    _fetch_images_core(raw_dir, bbox)


# ========= 兼容命令行运行 =========
def _cli_default():
    """
    单独运行本文件时：
    - 使用仓库根目录下 data/raw/
    - 使用 DEFAULT_BBOX
    """
    print("[INFO] 以脚本方式运行 fetch_images.py，使用全局 RAW_DIR 和 DEFAULT_BBOX")
    _fetch_images_core(GLOBAL_RAW_DIR, DEFAULT_BBOX)


if __name__ == "__main__":
    _cli_default()
