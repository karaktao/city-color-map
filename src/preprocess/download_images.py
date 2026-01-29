"""
download_images.py
修改版：支持 yield 生成器日志输出，供 FastAPI 流式传输使用。
"""

from pathlib import Path
import csv
import requests
import numpy as np
import cv2
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 设置缩放后的最长边（像素）
MAX_LONG_SIDE = 512


def _resize_keep_ratio(img_bgr, max_long_side=MAX_LONG_SIDE):
    """按比例缩放，使最长边不超过 max_long_side"""
    h, w = img_bgr.shape[:2]
    long_side = max(h, w)
    if long_side <= max_long_side:
        return img_bgr  # 已经够小了

    scale = max_long_side / long_side
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized


def run_download_images(project_dir):
    """
    生成器函数：
    逐步 yield 日志字符串，而不是一次性执行完毕。
    """
    project_dir = Path(project_dir)
    csv_path = project_dir / "data" / "csv" / "images_meta.csv"
    img_dir = project_dir / "data" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        yield f"[WARN] 未找到 {csv_path}，请先运行 parse_json\n"
        return

    # 1. 先读取所有行，获取总数（为了显示进度条）
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    total_count = len(rows)
    yield f"[INFO] 共发现 {total_count} 张图片记录，准备开始处理...\n"

    # 2. 遍历下载
    for index, row in enumerate(rows):
        img_id = row.get("id")
        url = row.get("thumb_2048_url")
        
        # 进度前缀，例如 [1/50]
        prefix = f"[{index + 1}/{total_count}]"

        if not img_id or not url:
            continue

        out_path = img_dir / f"{img_id}.jpg"
        if out_path.exists():
            # yield f"[INFO] {prefix} 已存在，跳过 {img_id}\n"
            # 如果不想刷屏，可以注释掉跳过的日志，或者只 yield 简短信息
            continue

        yield f"[INFO] {prefix} 正在下载 {img_id} ...\n"
        
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()

            # ---- 1. 把字节解码成 BGR 图像 ----
            data = np.frombuffer(resp.content, np.uint8)
            img_bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
            
            if img_bgr is None:
                yield f"[WARN] {prefix} 解码失败，跳过 {img_id}\n"
                continue

            # ---- 2. 压缩：缩小分辨率 ----
            img_small = _resize_keep_ratio(img_bgr, MAX_LONG_SIDE)

            # ---- 3. 保存压缩后的图片 ----
            cv2.imwrite(str(out_path), img_small)
            
            # (可选) 稍微停顿一下，防止下载太快让前端来不及渲染（通常网络IO已经够慢了，不需要sleep）
            # time.sleep(0.05) 

        except Exception as e:
            yield f"[WARN] {prefix} 下载或保存 {img_id} 失败: {e}\n"

    yield f"[SUCCESS] ✅ 所有图片处理完成。\n"


def _cli_default():
    """
    直接运行本脚本时的兼容处理：
    遍历生成器并打印，保持原本的 CLI 体验。
    """
    print("正在运行 download_images CLI 模式...")
    for log in run_download_images(PROJECT_ROOT):
        print(log, end="") # log 已经包含了 \n，所以 end=""


if __name__ == "__main__":
    _cli_default()