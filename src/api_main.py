# api_main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json

# Import your script modules
# NOTE: segmentation is imported lazily to avoid loading torch/mmcv at startup
from src.preprocess import download_images
from src.preprocess import parse_json
from src.api_fetch import fetch_images
from src.geojson_builder import build_geojson


app = FastAPI()

# ==========================================================
# ✅ Projects root directory:
# Use "projects" under the repository root for both local and container environments.
# In Docker, if you put projects into .dockerignore, this directory may not exist,
# but the server can still start normally.
# ==========================================================
BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR / "projects"

# Mount static resources only if the directory exists
# (otherwise the container may crash on startup)
if PROJECT_ROOT.exists():
    app.mount(
        "/static/projects",
        StaticFiles(directory=str(PROJECT_ROOT)),
        name="projects_static",
    )

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # allow all frontend origins (e.g., localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],      # allow all methods (GET, POST, etc.)
    allow_headers=["*"],      # allow all headers
)

# ---------- Request body models ----------
class InitProjectBody(BaseModel):
    project_name: str

class BBoxBody(BaseModel):
    project_name: str
    bbox_code: str

class ProjectBody(BaseModel):
    project_name: str

# ---------- List all projects ----------
@app.get("/api/projects")
def list_projects():
    """List all folder names under the projects directory."""
    if not PROJECT_ROOT.exists():
        return {"projects": []}

    projects = [
        d.name for d in PROJECT_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]
    projects.sort(key=lambda x: (PROJECT_ROOT / x).stat().st_mtime, reverse=True)
    return {"projects": projects}

# ---------- Check project status (for progress recovery) ----------
@app.get("/api/project-status/{project_name}")
def check_project_status(project_name: str):
    """Determine current progress based on whether output files exist."""
    project_dir = PROJECT_ROOT / project_name
    data_dir = project_dir / "data"

    status = {
        "exists": project_dir.exists(),
        "bbox": None,
        "bbox_code": None,
        "meta_ready": False,
        "process_ready": False,
        "geojson_ready": False
    }

    if not status["exists"]:
        return status

    # 1) Check BBOX (config.json)
    config_path = project_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                status["bbox"] = cfg.get("bbox")
                status["bbox_code"] = cfg.get("bbox_code")
        except Exception:
            pass

    # 2) Check metadata (images_meta.csv)
    meta_csv = data_dir / "csv" / "images_meta.csv"
    if meta_csv.exists() and meta_csv.stat().st_size > 10:
        status["meta_ready"] = True

    # 3) Check processing result (color_summary.csv)
    color_csv = data_dir / "csv" / "color_summary.csv"
    if color_csv.exists() and color_csv.stat().st_size > 10:
        status["process_ready"] = True

    # 4) Check GeoJSON
    geojson_path = data_dir / "geojson" / "facade_colors.geojson"
    if geojson_path.exists() and geojson_path.stat().st_size > 10:
        status["geojson_ready"] = True

    return status

# ---------- API 1: Initialize project ----------
@app.post("/api/init-project")
def init_project(body: InitProjectBody):
    project_dir = PROJECT_ROOT / body.project_name
    data_dir = project_dir / "data"
    for folder in ["images", "masks", "building_rgba", "palettes", "csv", "raw", "geojson"]:
        (data_dir / folder).mkdir(parents=True, exist_ok=True)
    return {"ok": True, "project_dir": str(project_dir)}

# ---------- API 2: Parse BBOX code ----------
@app.post("/api/set-bbox")
def set_bbox(body: BBoxBody):
    project_dir = PROJECT_ROOT / body.project_name
    config_path = project_dir / "config.json"
    bbox = fetch_images.parse_bbox_code(body.bbox_code)
    config = {"bbox_code": body.bbox_code, "bbox": bbox}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return {"ok": True, "bbox": bbox}

# ---------- API 3: Fetch image metadata & download ----------
@app.post("/api/fetch-images")
async def api_fetch_images(body: ProjectBody):
    project_dir = PROJECT_ROOT / body.project_name

    def fetch_pipeline():
        yield "[INFO] 🚀 Starting Mapillary API request to fetch metadata...\n"
        try:
            fetch_images.run_fetch_images(project_dir)
            yield "[SUCCESS] Metadata API request completed.\n"
        except Exception as e:
            yield f"[ERROR] API request failed: {e}\n"
            return

        yield "[INFO] Parsing raw JSON data...\n"
        try:
            parse_json.run_parse_json(project_dir)
            yield "[SUCCESS] JSON parsing completed. Preparing to download images.\n"
        except Exception as e:
            yield f"[ERROR] JSON parsing failed: {e}\n"
            return

        yield "[INFO] Starting downloader...\n"
        try:
            for log in download_images.run_download_images(project_dir):
                yield log
        except Exception as e:
            yield f"[ERROR] Download interrupted: {e}\n"
            return

        yield "[DONE] ✅ All steps completed.\n"

    return StreamingResponse(fetch_pipeline(), media_type="text/plain")

# ---------- API 4: Process images (segmentation + color extraction) ----------
@app.post("/api/process-images")
async def api_process_images(body: ProjectBody):
    project_dir = PROJECT_ROOT / body.project_name

    def process_pipeline():
        yield "[INFO] 🚀 Starting semantic segmentation and color extraction...\n"
        try:
            # ✅ Lazy import: avoid loading torch/mmcv at server startup
            from src.segmentation import segment_building
            for log in segment_building.run_segment_building(project_dir):
                yield log
        except Exception as e:
            yield f"[ERROR] Segmentation processing failed: {e}\n"
            return

        yield "[SUCCESS] ✅ Image processing completed. Please proceed to generate the map.\n"

    return StreamingResponse(process_pipeline(), media_type="text/plain")

# ---------- API 5: Build GeoJSON ----------
@app.post("/api/build-geojson")
async def api_build_geojson(body: ProjectBody):
    project_dir = PROJECT_ROOT / body.project_name

    def build_pipeline():
        yield "[INFO] Starting GeoJSON generation...\n"
        try:
            path = build_geojson.run_build_geojson(project_dir)
            yield f"[SUCCESS] GeoJSON generated successfully: {path}\n"
            yield "[INFO] Map data is ready.\n"
        except Exception as e:
            yield f"[ERROR] Generation failed: {e}\n"

    return StreamingResponse(build_pipeline(), media_type="text/plain")

# ---------- API 6: Provide GeoJSON for frontend map ----------
@app.get("/api/geojson/{project_name}")
def get_geojson(project_name: str):
    geojson_file = PROJECT_ROOT / project_name / "data/geojson/facade_colors.geojson"

    if not geojson_file.exists():
        return JSONResponse({"error": "GeoJSON not found"}, status_code=404)

    with open(geojson_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)
