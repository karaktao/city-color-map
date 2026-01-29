<template>
  <div class="map-panel">
    <div ref="mapRef" class="map-container"></div>

    <transition name="fade">
      <div class="bbox-card" v-if="bboxText">
        <div class="bbox-title">Current BBOX</div>
        <div class="bbox-code">{{ bboxText }}</div>
      </div>
    </transition>

    <div class="layer-control" v-if="hasData">
      <div class="control-header">
        <span class="icon">🎨</span> Analysis Controls
      </div>
      
      <div class="control-row">
        <label>Mode:</label>
        <div class="toggle-group">
          <button :class="{ active: viewMode === 'points' }" @click="viewMode = 'points'">Points</button>
          <button :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'">Grid</button>
        </div>
      </div>

      <div v-if="viewMode === 'grid'" class="grid-settings">
        <div class="control-row">
          <label>Density: {{ gridDensity }}</label>
          <input 
            type="range" 
            min="10" 
            max="100" 
            step="5" 
            v-model.number="gridDensity"
            @input="handleGridUpdate"
          >
        </div>
        <div class="control-row">
          <label>Opacity: {{ Math.round(gridOpacity * 100) }}%</label>
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.1" 
            v-model.number="gridOpacity"
          >
        </div>
      </div>
    </div>

    <div ref="popupRef" class="ol-popup" v-show="popupVisible">
      <a href="#" class="ol-popup-closer" @click.prevent="closePopup">✖</a>
      <div class="popup-content" v-if="selectedFeature">
        <div v-if="selectedFeature.get('image_id')">
          <div class="popup-header">
            <span class="popup-id">ID: {{ selectedFeature.get('image_id') }}</span>
          </div>
          <div class="color-row">
            <span class="label">Color:</span>
            <div class="color-badge" :style="{ backgroundColor: selectedFeature.get('main_color_hex') }">
              {{ selectedFeature.get('main_color_hex') }}
            </div>
          </div>
          <div class="img-container">
            <img :src="getImageUrl(selectedFeature.get('palette_image'))" class="popup-img" @error="handleImgError" />
          </div>
        </div>
        <div v-else>
          <div class="popup-header"><span class="popup-id">Grid Cell</span></div>
          <div class="color-row">
            <span class="label">Avg Color:</span>
            <div class="color-badge" :style="{ backgroundColor: selectedFeature.get('color') }">
              {{ selectedFeature.get('color') }}
            </div>
          </div>
          <div class="popup-hint">Contains {{ selectedFeature.get('count') }} points</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

// OpenLayers
import Map from 'ol/Map'
import View from 'ol/View'
import Overlay from 'ol/Overlay'
import Feature from 'ol/Feature'
import { transformExtent } from 'ol/proj'
import { Attribution } from 'ol/control'
import Polygon from 'ol/geom/Polygon'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import XYZ from 'ol/source/XYZ'
import VectorSource from 'ol/source/Vector'
import GeoJSON from 'ol/format/GeoJSON'
import { DragBox } from 'ol/interaction'
import { platformModifierKeyOnly } from 'ol/events/condition'
import { Style, Circle, Fill, Stroke } from 'ol/style'

// ================= 配置 =================
const API_BASE = 'http://127.0.0.1:8000'

const props = defineProps({
  geojsonUrl: { type: String, default: '' },
  initialBbox: { type: String, default: '' },
  activeBbox: { type: String, default: '' }
})

const emit = defineEmits(['bbox-change', 'image-click'])

// UI Refs
const mapRef = ref(null)
const popupRef = ref(null)
const bboxText = ref('')
const popupVisible = ref(false)
const selectedFeature = ref(null)
const hasData = ref(false)

// Grid Control Refs
const viewMode = ref('points') // 'points' | 'grid'
const gridDensity = ref(40)    // 网格密度 (NxN)
const gridOpacity = ref(0.8)   // 网格透明度

// OL Instances
let map = null
let vectorLayer = null  // 点图层
let gridLayer = null    // 🌟 网格图层
let bboxLayer = null    // 框图层
let dragBox = null
let overlay = null

// ================= 样式函数 =================

// 点样式
const pointStyleFunction = (feature) => {
  const colorHex = feature.get('main_color_hex') || '#9ca3af'
  return new Style({
    image: new Circle({
      radius: 5,
      fill: new Fill({ color: colorHex }),
      stroke: new Stroke({ color: '#ffffff', width: 1.5 })
    })
  })
}

// BBOX 样式 (灰色空心)
const bboxStyle = new Style({
  stroke: new Stroke({ color: '#9ca3af', width: 2, lineDash: [5, 5] }),
  fill: new Fill({ color: 'rgba(0,0,0,0)' })
})

// 🌟 网格样式 (动态颜色)
const gridStyleFunction = (feature) => {
  const color = feature.get('color')
  return new Style({
    fill: new Fill({ color: color }), // 颜色本身已包含透明度逻辑，或者由图层透明度控制
    stroke: new Stroke({ 
      color: 'rgba(255,255,255,0.1)', // 极淡的白边
      width: 1 
    })
  })
}

// ================= 辅助函数 =================

function getImageUrl(path) {
  if (!path) return ''
  return path.startsWith('/') ? `${API_BASE}${path}` : path
}

function handleImgError(e) { e.target.style.display = 'none' }

function closePopup() {
  if (overlay) overlay.setPosition(undefined)
  popupVisible.value = false
}

// 🌟 核心算法：生成色彩网格
// 1. 将 BBOX 切分为 density * density 个格子
// 2. 统计每个格子内的点，计算平均 RGB
function updateGrid() {
  if (!vectorLayer || !gridLayer) return
  
  const source = vectorLayer.getSource()
  const features = source.getFeatures()
  if (features.length === 0) return

  const extent = source.getExtent() // [minX, minY, maxX, maxY]
  const [minX, minY, maxX, maxY] = extent
  const width = maxX - minX
  const height = maxY - minY
  
  // 计算步长
  const stepX = width / gridDensity.value
  const stepY = height / gridDensity.value

  // 初始化网格容器: grid[xIndex][yIndex] = { r, g, b, count }
  const grid = {}

  // 1. 遍历所有点，归入格子
  features.forEach(f => {
    const coords = f.getGeometry().getCoordinates()
    const x = coords[0]
    const y = coords[1]
    
    // 计算索引
    const col = Math.floor((x - minX) / stepX)
    const row = Math.floor((y - minY) / stepY)
    
    // 边界检查
    if (col < 0 || col >= gridDensity.value || row < 0 || row >= gridDensity.value) return

    const key = `${col},${row}`
    
    // 获取颜色 (假设 props 里有 rgb 数组，或者解析 hex)
    // 这里为了简便，解析 hex
    const hex = f.get('main_color_hex') || '#888888'
    const rgb = hexToRgb(hex)

    if (!grid[key]) grid[key] = { r:0, g:0, b:0, count:0, col, row }
    
    grid[key].r += rgb.r
    grid[key].g += rgb.g
    grid[key].b += rgb.b
    grid[key].count++
  })

  // 2. 生成网格要素
  const gridFeatures = []
  
  Object.values(grid).forEach(cell => {
    const avgR = Math.round(cell.r / cell.count)
    const avgG = Math.round(cell.g / cell.count)
    const avgB = Math.round(cell.b / cell.count)
    const color = `rgb(${avgR},${avgG},${avgB})` // 纯色，透明度由图层控制

    // 构造矩形几何
    const cellMinX = minX + cell.col * stepX
    const cellMinY = minY + cell.row * stepY
    const cellMaxX = cellMinX + stepX
    const cellMaxY = cellMinY + stepY

    const polygon = new Polygon([[
      [cellMinX, cellMinY],
      [cellMaxX, cellMinY],
      [cellMaxX, cellMaxY],
      [cellMinX, cellMaxY],
      [cellMinX, cellMinY]
    ]])

    const feature = new Feature({
      geometry: polygon,
      color: color,
      count: cell.count
    })
    gridFeatures.push(feature)
  })

  // 3. 更新图层
  const gridSource = new VectorSource({ features: gridFeatures })
  gridLayer.setSource(gridSource)
}

// Hex 转 RGB
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : { r: 128, g: 128, b: 128 }
}

// BBOX 渲染
function renderBbox(bboxStr) {
  if (!map || !bboxLayer || !bboxStr) return
  const parts = bboxStr.split(',').map(v => parseFloat(v))
  if (parts.length !== 4) return
  const [minX, minY, maxX, maxY] = parts
  const coords4326 = [[[minX, minY],[maxX, minY],[maxX, maxY],[minX, maxY],[minX, minY]]]
  const polygon = new Polygon(coords4326).transform('EPSG:4326', 'EPSG:3857')
  bboxLayer.getSource().clear()
  bboxLayer.getSource().addFeature(new Feature({ geometry: polygon }))
}

function zoomToBbox(bboxStr) {
  if (!map || !bboxStr) return
  const parts = bboxStr.split(',').map(v => parseFloat(v))
  if (parts.length !== 4) return
  const extent = transformExtent(parts, 'EPSG:4326', 'EPSG:3857')
  map.getView().fit(extent, { padding: [50, 50, 50, 50], duration: 800 })
}

// ================= 生命周期 =================

onMounted(() => {
  // 1. CartoDB 底图
  const baseLayer = new TileLayer({
    source: new XYZ({
      url: 'https://{a-c}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      attributions: '&copy; CartoDB'
    })
  })

  // 2. 图层初始化
  bboxLayer = new VectorLayer({ source: new VectorSource(), style: bboxStyle, zIndex: 100 })
  
  vectorLayer = new VectorLayer({ 
    source: new VectorSource(), 
    style: pointStyleFunction, 
    zIndex: 10 
  })
  
  gridLayer = new VectorLayer({ 
    source: new VectorSource(), 
    style: gridStyleFunction, 
    zIndex: 5,
    opacity: gridOpacity.value,
    visible: false // 默认隐藏
  })

  // 3. 地图实例
  map = new Map({
    target: mapRef.value,
    layers: [baseLayer, gridLayer, vectorLayer, bboxLayer],
    view: new View({ center: [0, 0], zoom: 2 }),
    controls: [new Attribution({ collapsible: false })]
  })

  // 4. 弹窗
  overlay = new Overlay({
    element: popupRef.value,
    autoPan: { animation: { duration: 250 } },
    positioning: 'bottom-center',
    offset: [0, -10]
  })
  map.addOverlay(overlay)

  // 5. 点击交互 (兼容 Grid 和 Points)
  map.on('singleclick', (evt) => {
    // 优先点击点，如果点没点到且是grid模式，再点网格
    let feature = map.forEachFeatureAtPixel(evt.pixel, f => f, { layerFilter: l => l === vectorLayer })
    
    if (!feature && viewMode.value === 'grid') {
      feature = map.forEachFeatureAtPixel(evt.pixel, f => f, { layerFilter: l => l === gridLayer })
    }

    if (feature) {
      selectedFeature.value = feature
      popupVisible.value = true
      overlay.setPosition(evt.coordinate)
      if (feature.get('image_id')) emit('image-click', feature.getProperties())
    } else {
      closePopup()
    }
  })

  map.on('pointermove', (evt) => {
    const hit = map.hasFeatureAtPixel(evt.pixel, { 
      layerFilter: l => (viewMode.value === 'grid' ? l === gridLayer : l === vectorLayer) 
    })
    map.getTarget().style.cursor = hit ? 'pointer' : ''
  })

  // 6. 拖拽框选
  dragBox = new DragBox({ condition: platformModifierKeyOnly })
  map.addInteraction(dragBox)
  dragBox.on('boxend', () => {
    const ext = dragBox.getGeometry().getExtent()
    const ext4326 = transformExtent(ext, 'EPSG:3857', 'EPSG:4326')
    const bboxStr = ext4326.map(v => v.toFixed(6)).join(',')
    bboxText.value = bboxStr
    renderBbox(bboxStr)
    emit('bbox-change', bboxStr)
  })

  if (props.initialBbox) {
    bboxText.value = props.initialBbox
    renderBbox(props.initialBbox)
    zoomToBbox(props.initialBbox)
  }
})

// ================= Watchers =================

// GeoJSON 加载
watch(() => props.geojsonUrl, (url) => {
  if (!map || !url) return
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`
  const source = new VectorSource({ url: fullUrl, format: new GeoJSON() })
  
  source.on('featuresloadend', () => {
    const extent = source.getExtent()
    if (!source.isEmpty()) {
      map.getView().fit(extent, { padding: [50, 50, 50, 50], duration: 800 })
      hasData.value = true
      // 如果当前是 Grid 模式，自动生成网格
      if (viewMode.value === 'grid') updateGrid()
    }
  })
  vectorLayer.setSource(source)
})

// BBOX 外部更新
watch(() => props.activeBbox, (val) => {
  if (val && map) {
    bboxText.value = val
    renderBbox(val)
    zoomToBbox(val)
  }
})

// 🌟 视图模式切换
watch(viewMode, (mode) => {
  if (mode === 'points') {
    vectorLayer.setVisible(true)
    gridLayer.setVisible(false)
  } else {
    vectorLayer.setVisible(false) // 隐藏点
    gridLayer.setVisible(true)    // 显示网格
    updateGrid()                  // 重新计算网格
  }
})

// 🌟 密度更新 (防抖优化可自行添加，这里直接更新)
const handleGridUpdate = () => {
  if (viewMode.value === 'grid') updateGrid()
}

// 🌟 透明度更新
watch(gridOpacity, (val) => {
  if (gridLayer) gridLayer.setOpacity(val)
})

onBeforeUnmount(() => { if (map) map.setTarget(null) })
</script>

<style scoped>
.map-panel {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: #f5f5f5;
}
.map-container { width: 100%; height: 100%; }

/* 控制面板样式 */
.layer-control {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 12px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 20;
  width: 200px;
  font-family: -apple-system, sans-serif;
}

.control-header {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
}

.control-row {
  margin-bottom: 12px;
}

.control-row label {
  display: block;
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 4px;
  font-weight: 500;
}

/* 切换按钮 */
.toggle-group {
  display: flex;
  background: #f3f4f6;
  border-radius: 6px;
  padding: 2px;
}

.toggle-group button {
  flex: 1;
  border: none;
  background: transparent;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  color: #6b7280;
  transition: all 0.2s;
}

.toggle-group button.active {
  background: #fff;
  color: #0f766e;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
  font-weight: 600;
}

/* 滑块样式 */
input[type=range] {
  width: 100%;
  height: 4px;
  border-radius: 2px;
  background: #e5e7eb;
  outline: none;
  -webkit-appearance: none;
}
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  background: #0f766e;
  border-radius: 50%;
  cursor: pointer;
  transition: transform 0.1s;
}
input[type=range]::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

/* OL 控件覆盖 */
:deep(.ol-zoom) { display: none !important; }
:deep(.ol-attribution) {
  bottom: 0 !important; right: 0 !important; left: auto !important; top: auto !important;
  background: rgba(255,255,255,0.6) !important;
  border-radius: 4px 0 0 0 !important;
}

/* BBOX & Popup 样式同前 (略) */
.bbox-card { position: absolute; left: 16px; bottom: 24px; background: rgba(15,23,42,0.9); color: #fff; padding: 10px; border-radius: 8px; z-index: 5; font-size: 12px; }
.bbox-code { font-family: monospace; color: #38bdf8; margin-top: 4px; }

.ol-popup { position: absolute; background: white; padding: 12px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-width: 180px; bottom: 12px; left: -50%; }
.popup-id { font-weight: bold; font-size: 12px; }
.color-badge { width: 100%; height: 20px; border-radius: 4px; color: white; text-align: center; font-size: 11px; line-height: 20px; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }
.img-container { width: 100%; height: 60px; margin-top: 8px; display: flex; justify-content: center; background: #f9fafb; }
.popup-img { height: 100%; object-fit: contain; }
</style>