# api_main.py
from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path

from src.preprocess import download_images
from src.preprocess import parse_json
from src.api_fetch import fetch_images
from src.segmentation import segment_building
from src.geojson_builder import build_geojson

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[1]  # city-color-map/src -> 回到项目根
PROJECT_ROOT = BASE_DIR / "projects"

class InitProjectBody(BaseModel):
    project_name: str

@app.post("/api/init-project")
def init_project(body: InitProjectBody):
    project_dir = PROJECT_ROOT / body.project_name
    data_dir = project_dir / "data"

    # 创建目录
    (data_dir / "images").mkdir(parents=True, exist_ok=True)
    (data_dir / "masks").mkdir(parents=True, exist_ok=True)
    (data_dir / "building_rgba").mkdir(parents=True, exist_ok=True)
    (data_dir / "palettes").mkdir(parents=True, exist_ok=True)
    (data_dir / "csv").mkdir(parents=True, exist_ok=True)
    (data_dir / "raw").mkdir(parents=True, exist_ok=True)
    (data_dir / "geojson").mkdir(parents=True, exist_ok=True)

    return {"ok": True, "project_dir": str(project_dir)}
