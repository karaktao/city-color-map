<template>
  <div class="map-panel">
    <div ref="mapRef" class="map-container"></div>

    <!-- 右上角小提示 -->
    <div class="map-hint">
      按住 <b>Shift</b> 键并拖动鼠标，即可框选范围（BBOX）
    </div>

    <!-- 左下角显示当前 BBOX -->
    <div class="bbox-display" v-if="bboxText">
      <div>BBOX (lon_min, lat_min, lon_max, lat_max)</div>
      <code>{{ bboxText }}</code>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import OSM from 'ol/source/OSM'
import { DragBox } from 'ol/interaction'
import { transformExtent } from 'ol/proj'
import GeoJSON from 'ol/format/GeoJSON'

const props = defineProps({
  // 可选：用于加载你的城市色彩 GeoJSON
  geojsonUrl: {
    type: String,
    default: ''
  },
  // 可选：如果外面已经有一个 bbox，可以传进来让地图自动 zoomTo
  initialBbox: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['bbox-change', 'image-click'])

const mapRef = ref(null)
const bboxText = ref('')

// OpenLayers 实例引用
let map = null
let vectorLayer = null
let dragBox = null

// 把 "minLon,minLat,maxLon,maxLat" 转成视图范围
function zoomToBbox(bboxStr) {
  if (!map || !bboxStr) return
  const parts = bboxStr.split(',').map((v) => parseFloat(v))
  if (parts.length !== 4 || parts.some((v) => Number.isNaN(v))) return
  const extent4326 = parts
  const extent3857 = transformExtent(
    extent4326,
    'EPSG:4326',
    'EPSG:3857'
  )
  map.getView().fit(extent3857, {
    padding: [40, 40, 40, 40],
    duration: 500
  })
}

onMounted(() => {
  // 1. 创建底图（OpenStreetMap）
  const baseLayer = new TileLayer({
    source: new OSM()
  })

  // 2. 空的矢量图层，后面用来加载 GeoJSON（城市色彩点）
  vectorLayer = new VectorLayer({
    source: new VectorSource()
  })

  map = new Map({
    target: mapRef.value,
    layers: [baseLayer, vectorLayer],
    view: new View({
      center: [0, 0],              // 初始中心（会自动调整）
      zoom: 2
    })
  })

  // 如果有 initialBbox，则自动缩放过去
  if (props.initialBbox) {
    zoomToBbox(props.initialBbox)
    bboxText.value = props.initialBbox
  } else {
    // 默认缩放到欧洲，这样你在 Enschede 比较方便看
    map.getView().setCenter([6.9 * 111319.49, 52.2 * 111319.49])
    map.getView().setZoom(12)
  }

  // 3. 添加 DragBox，用来框选 BBOX（按住 Shift 拖动）
  dragBox = new DragBox()
  map.addInteraction(dragBox)

  dragBox.on('boxend', () => {
    const extent3857 = dragBox.getGeometry().getExtent()
    // 转成 WGS84 经纬度
    const extent4326 = transformExtent(
      extent3857,
      'EPSG:3857',
      'EPSG:4326'
    )
    const [minX, minY, maxX, maxY] = extent4326
    const bboxStr = [
      minX.toFixed(6),
      minY.toFixed(6),
      maxX.toFixed(6),
      maxY.toFixed(6)
    ].join(',')

    bboxText.value = bboxStr
    emit('bbox-change', bboxStr)
  })
})

// 监听 geojsonUrl，加载 / 更新城市色彩点图层
watch(
  () => props.geojsonUrl,
  (url) => {
    if (!map || !url) return
    const source = new VectorSource({
      url,
      format: new GeoJSON()
    })
    vectorLayer.setSource(source)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
})
</script>

<style scoped>
.map-panel {
  position: relative;
  border: 1px solid #444;
  border-radius: 4px;
  height: 600px;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

/* 右上角提示 */
.map-hint {
  position: absolute;
  right: 8px;
  top: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: #eee;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 4px;
}

/* 左下角 BBOX 显示 */
.bbox-display {
  position: absolute;
  left: 8px;
  bottom: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #eee;
  padding: 6px 8px;
  font-size: 12px;
  border-radius: 4px;
  max-width: 80%;
}

.bbox-display code {
  display: block;
  margin-top: 2px;
  font-family: monospace;
  font-size: 11px;
  word-break: break-all;
}
</style>
