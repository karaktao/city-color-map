# api_main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles  
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json

# 导入你的脚本模块
from src.preprocess import download_images
from src.preprocess import parse_json
from src.api_fetch import fetch_images
from src.segmentation import segment_building
from src.geojson_builder import build_geojson
import os


app = FastAPI()

# 确定项目根目录
BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR / "projects"

# 允许所有来源访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有前端来源 (localhost:5173 等)
    allow_credentials=True,
    allow_methods=["*"],      # 允许所有方法 (GET, POST 等)
    allow_headers=["*"],      # 允许所有 Header
)

# ==========================================================
# ❗关键修复：挂载静态资源目录
# 前端访问 http://localhost:8000/static/projects/xxx/data/palettes/xxx.png
# 实际上读取的是 D:/.../projects/xxx/data/palettes/xxx.png
# ==========================================================
app.mount("/static/projects", StaticFiles(directory=PROJECT_ROOT), name="projects_static")


# ---------- Body 模型 ----------
class InitProjectBody(BaseModel):
    project_name: str

class BBoxBody(BaseModel):
    project_name: str
    bbox_code: str

class ProjectBody(BaseModel):
    project_name: str

# ---------- 获取所有项目列表 ----------
@app.get("/api/projects")
def list_projects():
    """列出 projects 目录下所有的文件夹名称"""
    if not PROJECT_ROOT.exists():
        return {"projects": []}
    
    # 扫描目录下所有文件夹
    projects = [
        d.name for d in PROJECT_ROOT.iterdir() 
        if d.is_dir() and not d.name.startswith(".")
    ]
    # 按修改时间倒序排列（最近用的排前面）
    projects.sort(key=lambda x: (PROJECT_ROOT / x).stat().st_mtime, reverse=True)
    
    return {"projects": projects}


# ---------- 检查项目状态 (用于恢复进度) ----------
@app.get("/api/project-status/{project_name}")
def check_project_status(project_name: str):
    """根据文件是否存在，判断当前进度"""
    project_dir = PROJECT_ROOT / project_name
    data_dir = project_dir / "data"
    
    # 状态标记
    status = {
        "exists": project_dir.exists(),
        "bbox": None,
        "bbox_code": None,
        "meta_ready": False,    # 是否有 images_meta.csv
        "process_ready": False, # 是否有 masks 或 palettes
        "geojson_ready": False  # 是否有 geojson
    }

    if not status["exists"]:
        return status

    # 1. 检查 BBOX (config.json)
    config_path = project_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                status["bbox"] = cfg.get("bbox")
                status["bbox_code"] = cfg.get("bbox_code")
        except:
            pass

    # 2. 检查元数据 (images_meta.csv)
    meta_csv = data_dir / "csv" / "images_meta.csv"
    if meta_csv.exists() and meta_csv.stat().st_size > 10:
        status["meta_ready"] = True

    # 3. 检查处理结果 (查看 color_summary.csv 或 palettes 文件夹)
    color_csv = data_dir / "csv" / "color_summary.csv"
    if color_csv.exists() and color_csv.stat().st_size > 10:
        status["process_ready"] = True

    # 4. 检查 GeoJSON
    geojson_path = data_dir / "geojson" / "facade_colors.geojson"
    if geojson_path.exists() and geojson_path.stat().st_size > 10:
        status["geojson_ready"] = True

    return status


# ---------- API 1：初始化项目 ----------
@app.post("/api/init-project")
def init_project(body: InitProjectBody):
    project_dir = PROJECT_ROOT / body.project_name
    data_dir = project_dir / "data"
    for folder in ["images", "masks", "building_rgba", "palettes", "csv", "raw", "geojson"]:
        (data_dir / folder).mkdir(parents=True, exist_ok=True)
    return {"ok": True, "project_dir": str(project_dir)}


# ---------- API 2：解析 BBOX code ----------
@app.post("/api/set-bbox")
def set_bbox(body: BBoxBody):
    project_dir = PROJECT_ROOT / body.project_name
    config_path = project_dir / "config.json"
    bbox = fetch_images.parse_bbox_code(body.bbox_code)
    config = {"bbox_code": body.bbox_code, "bbox": bbox}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return {"ok": True, "bbox": bbox}


# ---------- API 3：获取照片元数据 & 下载 ----------
@app.post("/api/fetch-images")
async def api_fetch_images(body: ProjectBody):
    project_dir = PROJECT_ROOT / body.project_name

    def fetch_pipeline():
        yield f"[INFO] 🚀 开始请求 Mapillary API 获取元数据...\n"
        try:
            fetch_images.run_fetch_images(project_dir) 
            yield f"[SUCCESS] 元数据 API 请求完成。\n"
        except Exception as e:
            yield f"[ERROR] API 请求失败: {e}\n"
            return

        yield f"[INFO] 正在解析原始 JSON 数据...\n"
        try:
            parse_json.run_parse_json(project_dir)
            yield f"[SUCCESS] JSON 解析完成，准备下载图片。\n"
        except Exception as e:
            yield f"[ERROR] JSON 解析失败: {e}\n"
            return

        yield f"[INFO] 启动下载器...\n"
        try:
            # 这里的 run_download_images 已经是 generator
            for log in download_images.run_download_images(project_dir):
                yield log
        except Exception as e:
            yield f"[ERROR] 下载过程中断: {e}\n"
            return

        yield f"[DONE] ✅ 所有步骤执行完毕。\n"

    return StreamingResponse(fetch_pipeline(), media_type="text/plain")


# ---------- API 4：处理图片（语义分割 + 提取色彩） ----------
# 修正说明：移除了 GeoJSON 生成逻辑，让它只专注于处理图片
# --------------------------------------------------------
@app.post("/api/process-images")
async def api_process_images(body: ProjectBody):
    project_dir = PROJECT_ROOT / body.project_name

    def process_pipeline():
        yield f"[INFO] 🚀 开始语义分割与色彩提取任务...\n"
        
        try:
            # 这里的 run_segment_building 已经是 generator
            for log in segment_building.run_segment_building(project_dir):
                yield log
        except Exception as e:
            yield f"[ERROR] 分割处理失败: {e}\n"
            return

        # ❗这里不再调用 build_geojson，保持逻辑纯粹
        yield f"[SUCCESS] ✅ 图片处理完成。请点击下一步生成地图。\n"

    return StreamingResponse(process_pipeline(), media_type="text/plain")


# ---------- API 5：生成 GeoJSON ----------
# 修正说明：这才是真正生成地图的地方
# ------------------------------------
@app.post("/api/build-geojson")
async def api_build_geojson(body: ProjectBody):
    project_dir = PROJECT_ROOT / body.project_name

    def build_pipeline():
        yield f"[INFO] 开始生成 GeoJSON 数据...\n"
        try:
            # 调用 build_geojson 生成文件
            path = build_geojson.run_build_geojson(project_dir)
            yield f"[SUCCESS] GeoJSON 生成成功: {path}\n"
            yield f"[INFO] 地图数据已准备就绪。\n"
        except Exception as e:
            yield f"[ERROR] 生成失败: {e}\n"

    return StreamingResponse(build_pipeline(), media_type="text/plain")


# ---------- API 6：给前端地图读取 GeoJSON ----------
@app.get("/api/geojson/{project_name}")
def get_geojson(project_name: str):
    geojson_file = PROJECT_ROOT / project_name / "data/geojson/facade_colors.geojson"

    if not geojson_file.exists():
        return JSONResponse({"error": "GeoJSON not found"}, status_code=404)

    with open(geojson_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)