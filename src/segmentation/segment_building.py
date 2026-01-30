"""
segment_building.py (Streaming Log Version)

Purpose:
1. Run semantic segmentation on street-view images using a SegFormer model
2. Detect shadows inside building regions
3. Extract dominant colors from building pixels
4. Export color statistics CSV

Notes:
- tqdm has been removed
- Uses generator (yield) logs for real-time progress display in the frontend
"""

import sys
import glob
import csv
from pathlib import Path

import cv2
import numpy as np
# from tqdm import tqdm  <-- tqdm removed
from sklearn.cluster import KMeans

from mmseg.apis import init_model, inference_model
from mmseg.utils import register_all_modules
import torch

# ================== Path configuration ==================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CFG_PATH = PROJECT_ROOT / "segformer_mit-b0_8xb2-160k_ade20k-512x512.py"
CKPT_GLOB = str(PROJECT_ROOT / "segformer_mit-b0_*ade20k*.pth")

# Default paths
DEFAULT_IN_DIR = PROJECT_ROOT / "data" / "images"
DEFAULT_OUT_MASK_DIR = PROJECT_ROOT / "data" / "masks"
DEFAULT_OUT_ONLY_DIR = PROJECT_ROOT / "data" / "building_rgba"
DEFAULT_OUT_PALETTE_DIR = PROJECT_ROOT / "data" / "palettes"
DEFAULT_CSV_OUT = PROJECT_ROOT / "data" / "csv" / "color_summary.csv"

# ================== Parameter configuration ==================
KL = 1.0
KB = 0.5
MORPH_KERNEL = 3
TOPK = 5
PALETTE_W = 120
WHITE_TH = 240
BLACK_TH = 20
MIN_SAMPLES = 500


def find_ckpt():
    """Find the checkpoint file. Return None if not found (caller handles the error)."""
    cands = sorted(glob.glob(CKPT_GLOB))
    if not cands:
        return None
    return cands[0]


def pick_building_ids(classes):
    STRICT = {"building", "house", "skyscraper", "garage", "roof", "windowpane", "door", "balcony"}
    EXCLUDE = {"fence", "railing", "wall", "arch", "column", "beam"}
    name2id = {n: i for i, n in enumerate(classes)}
    ids = [i for n, i in name2id.items() if n in STRICT and n not in EXCLUDE]
    if "building" in name2id and name2id["building"] not in ids:
        ids.append(name2id["building"])
    return sorted(set(ids))


def ensure_dirs(*dirs: Path):
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def shadow_mask_lab(img_bgr, valid_mask255):
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, _, B = lab[..., 0], lab[..., 1], lab[..., 2]
    m = valid_mask255 == 255
    if not np.any(m):
        return np.zeros_like(L, dtype=np.uint8)
    Lm, Bm = L[m], B[m]
    L_mean, L_std = float(Lm.mean()), float(Lm.std() + 1e-6)
    B_mean, B_std = float(Bm.mean()), float(Bm.std() + 1e-6)
    shadow = ((L < (L_mean - KL * L_std)) & (B < (B_mean - KB * B_std)) & m).astype(np.uint8) * 255
    if MORPH_KERNEL > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL, MORPH_KERNEL))
        shadow = cv2.morphologyEx(shadow, cv2.MORPH_OPEN, k, iterations=1)
    return shadow


def save_building_only_shadowfree(img_bgr, mask255, out_path: Path):
    bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
    bgra[mask255 == 0, 3] = 0
    sh_mask = shadow_mask_lab(img_bgr, mask255)
    bgra[sh_mask == 255, 3] = 0
    cv2.imwrite(str(out_path), bgra)


def load_rgba(path: Path):
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None, None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    if img.shape[2] == 3:
        a = np.full(img.shape[:2], 255, np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        img[..., 3] = a
    return img[..., :3], img[..., 3]


def get_dominant_colors(bgr, alpha, k=TOPK):
    mask = alpha > 0
    if mask.sum() < MIN_SAMPLES:
        return []
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    sel = rgb[mask].astype(np.uint8)
    keep = ~((sel >= WHITE_TH).all(axis=1) | (sel <= BLACK_TH).all(axis=1))
    sel = sel[keep]
    if sel.shape[0] < MIN_SAMPLES:
        return []
    uniq = np.unique(sel, axis=0)
    n_clusters = int(min(k, max(1, len(uniq))))
    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    km.fit(sel.astype(np.float32))
    centers = km.cluster_centers_.clip(0, 255).astype(np.uint8)
    counts = np.bincount(km.labels_, minlength=n_clusters).astype(np.float64)
    ratios = counts / counts.sum()
    order = np.argsort(-ratios)
    return [(centers[i].tolist(), float(ratios[i])) for i in order]


def compose_with_palette_keep_alpha(bgra, colors, palette_w=PALETTE_W):
    h, w = bgra.shape[:2]
    card = np.zeros((h, palette_w, 4), np.uint8)
    card[..., 3] = 255
    if colors:
        y = 0
        for rgb, ratio in colors:
            bh = max(1, int(round(ratio * h)))
            bgr = (rgb[2], rgb[1], rgb[0], 255)
            card[y:y + bh, :] = bgr
            y += bh
        if y < h:
            card[y:h, :] = card[y - 1, :] if y > 0 else (60, 60, 60, 255)
    return np.concatenate([bgra, card], axis=1)


def _segment_pipeline(in_dir: Path, out_mask_dir: Path, out_only_dir: Path, out_palette_dir: Path, csv_out: Path):
    """
    Core generator pipeline:
    Includes three major steps and yields logs for each processed image.
    """
    in_dir = Path(in_dir)
    out_mask_dir = Path(out_mask_dir)
    out_only_dir = Path(out_only_dir)
    out_palette_dir = Path(out_palette_dir)
    csv_out = Path(csv_out)

    if not in_dir.exists():
        yield f"[ERROR] Input directory does not exist: {in_dir}\n"
        return

    # Collect image files
    imgs = [p for p in in_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}]
    total_imgs = len(imgs)

    if not imgs:
        yield f"[WARN] No image files found in {in_dir}.\n"
        return

    ensure_dirs(out_mask_dir, out_only_dir, out_palette_dir, csv_out.parent)
    yield f"[INFO] Found {total_imgs} images. Starting pipeline...\n"

    # ================= Step 1: Semantic segmentation =================
    need_infer = any(not (out_mask_dir / f\"{p.stem}_building.png\").exists() for p in imgs)

    if need_infer:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        yield f"[INFO] Loading SegFormer model (Device: {device})...\n"

        try:
            register_all_modules(init_default_scope=False)
            ckpt = find_ckpt()
            if ckpt is None:
                yield f"[ERROR] Checkpoint not found: {CKPT_GLOB}\n"
                return

            model = init_model(str(CFG_PATH), ckpt, device=device)
            classes = model.dataset_meta.get("classes")
            building_ids = pick_building_ids(classes) if classes else [1]

            yield "[INFO] Model loaded. Starting [Step 1/3] semantic segmentation...\n"

            # --- Step 1 loop ---
            for i, p in enumerate(imgs):
                out_path = out_mask_dir / f"{p.stem}_building.png"

                # Progress log, e.g. [Step 1/3] (1/33) Segmenting: 12345.jpg ...
                yield f"[INFO] [Step 1/3] ({i+1}/{total_imgs}) Segmenting: {p.name} ...\n"

                if out_path.exists():
                    continue

                img_bgr = cv2.imread(str(p))
                if img_bgr is None:
                    continue

                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                result = inference_model(model, img_rgb)
                seg = result.pred_sem_seg.data.squeeze().cpu().numpy().astype(np.int32)
                mask255 = (np.isin(seg, building_ids)).astype(np.uint8) * 255
                cv2.imwrite(str(out_path), mask255)

            yield "[SUCCESS] ✅ Step 1 completed: semantic segmentation done.\n"

        except Exception as e:
            yield f"[ERROR] Segmentation inference failed: {e}\n"
            return
    else:
        yield "[INFO] Existing building masks detected. Skipping [Step 1].\n"

    # ================= Step 2: Shadow removal =================
    yield "[INFO] Starting [Step 2/3] shadow removal and alpha masking...\n"
    count = 0
    for i, p in enumerate(imgs):
        out_path = out_only_dir / f"{p.stem}_building_shadowfree.png"

        yield f"[INFO] [Step 2/3] ({i+1}/{total_imgs}) Removing shadow: {p.name} ...\n"

        if out_path.exists():
            count += 1
            continue

        mask_path = out_mask_dir / f"{p.stem}_building.png"
        if not mask_path.exists():
            continue

        mask255 = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        img_bgr = cv2.imread(str(p))
        if mask255 is None or img_bgr is None:
            continue

        save_building_only_shadowfree(img_bgr, mask255, out_path)
        count += 1

    yield f"[SUCCESS] ✅ Step 2 completed. Generated {count} transparent PNGs.\n"

    # ================= Step 3: Color extraction =================
    files = sorted(out_only_dir.glob("*.png"))
    total_files = len(files)

    if not files:
        yield "[WARN] No transparent PNGs found. Skipping Step 3.\n"
        return

    yield "[INFO] Starting [Step 3/3] dominant color extraction and palette generation...\n"

    with csv_out.open("w", newline="", encoding="utf-8") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["file", "palette_rgb", "ratios"])

        for i, fp in enumerate(files):
            yield f"[INFO] [Step 3/3] ({i+1}/{total_files}) Extracting colors: {fp.name} ...\n"

            bgr, alpha = load_rgba(fp)
            if bgr is None:
                continue

            colors = get_dominant_colors(bgr, alpha, k=TOPK)
            bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
            bgra[alpha == 0, 3] = 0
            out_img = compose_with_palette_keep_alpha(bgra, colors, PALETTE_W)

            out_name = f"{fp.stem.replace('_building_shadowfree', '')}_palette.png"
            cv2.imwrite(str(out_palette_dir / out_name), out_img)

            writer.writerow([fp.name, [c for c, _ in colors], [r for _, r in colors]])

    yield "[SUCCESS] ✅ Step 3 completed. CSV saved.\n"


# =========================================================

def run_segment_building(project_dir):
    """
    FastAPI entry point (Generator).
    """
    project_dir = Path(project_dir)
    in_dir = project_dir / "data" / "images"
    out_mask_dir = project_dir / "data" / "masks"
    out_only_dir = project_dir / "data" / "building_rgba"
    out_palette_dir = project_dir / "data" / "palettes"
    csv_out = project_dir / "data" / "csv" / "color_summary.csv"

    # Return the iterator from _segment_pipeline
    return _segment_pipeline(in_dir, out_mask_dir, out_only_dir, out_palette_dir, csv_out)


def main():
    """
    Script CLI mode.
    """
    print("Running segment_building in CLI mode...")
    # Simulate how the API would consume the generator
    gen = _segment_pipeline(
        DEFAULT_IN_DIR,
        DEFAULT_OUT_MASK_DIR,
        DEFAULT_OUT_ONLY_DIR,
        DEFAULT_OUT_PALETTE_DIR,
        DEFAULT_CSV_OUT,
    )
    for log in gen:
        # Print directly in terminal; keep end="" to simulate log streaming
        print(log, end="")


if __name__ == "__main__":
    main()
