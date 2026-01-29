<template>
  <div ref="mapRef" class="map-root"></div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import request from '../utils/request'

import Map from 'ol/Map'
import View from 'ol/View'
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer'
import { OSM } from 'ol/source'
import VectorSource from 'ol/source/Vector'
import { Fill, Stroke, Style } from 'ol/style'
import GeoJSON from 'ol/format/GeoJSON'

const props = defineProps({
  projectName: {
    type: String,
    required: true
  }
})

const mapRef = ref(null)
let map
let vectorLayer

async function loadGeojson() {
  const res = await request.get(`/api/geojson/${props.projectName}`)
  const data = res.data

  const source = new VectorSource({
    features: new GeoJSON().readFeatures(data, {
      featureProjection: 'EPSG:3857'
    })
  })

  if (!vectorLayer) {
    vectorLayer = new VectorLayer({
      source,
      style: new Style({
        fill: new Fill(),
        stroke: new Stroke()
      })
    })
    map.addLayer(vectorLayer)
  } else {
    vectorLayer.setSource(source)
  }

  map.getView().fit(source.getExtent(), { padding: [20, 20, 20, 20] })
}

onMounted(() => {
  map = new Map({
    target: mapRef.value,
    layers: [
      new TileLayer({
        source: new OSM()
      })
    ],
    view: new View({
      center: [0, 0],
      zoom: 2
    })
  })

  loadGeojson()
})

watch(
  () => props.projectName,
  () => {
    loadGeojson()
  }
)
</script>

<style scoped>
.map-root {
  width: 100%;
  height: 100%;
}
</style>
