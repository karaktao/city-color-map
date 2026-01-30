# 🏙️ City Color Map

**Urban Façade Color Extraction & Visualization**

City Color Map is a web-based system for **extracting dominant building façade colors from street-level imagery** and **visualizing urban color patterns on an interactive map**.

It integrates **Mapillary street images**, **deep-learning-based semantic segmentation**, and **GIS visualization** for urban analysis and design research.

<p align="center">
  <img src="data/images/images.png" width="800">
</p>
---

## ✨ Features

* 📸 Fetch street-view images via Mapillary API (tile-based, resumable)
* 🧠 Building façade segmentation using SegFormer (ADE20K)
* 🎨 Dominant color extraction with KMeans clustering
* 🗺️ Interactive map visualization (point & grid modes)
* 📦 Multi-project, step-by-step processing pipeline

---

## 🧩 Architecture

```
Vue + OpenLayers (Frontend)
        ↓
FastAPI (Backend)
        ↓
Image Fetch → Segmentation → Color Extraction → GeoJSON
```

---

## 📁 Structure

```
src/          # Backend (FastAPI, ML pipeline)
web/          # Frontend (Vue + OpenLayers)
projects/     # Per-project data (auto-generated)
docker-compose.yml
```

---

## 🚀 Quick Start (Docker)

### 1. Configure environment

Create `.env`:

```env
MAPILLARY_TOKEN=your_token_here
```

### 2. Run

```bash
docker compose up --build
```

* Frontend: [http://localhost:8080](http://localhost:8080)
* Backend API: [http://localhost:8000](http://localhost:8000)

---

## 🔄 Workflow

1. Initialize project
2. Set bounding box
3. Fetch images
4. Segment buildings & extract colors
5. Generate GeoJSON
6. Visualize on map

Each step is persistent and can be resumed safely.

---

## 🧠 Model & Methods

* **Model**: SegFormer (ADE20K)
* **Target**: Building-related classes
* **Post-processing**:

  * Shadow filtering
  * White/black pixel removal
  * KMeans color clustering

---

## ⚠️ Notes

* CPU inference recommended for small–medium areas
* Requires Mapillary image coverage
* Intended for research and educational use

---

## 📄 License

For research and non-commercial use.
Please comply with Mapillary data usage policies.

---
