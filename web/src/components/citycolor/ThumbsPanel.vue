<template>
  <div class="thumbs-panel">
    <div class="thumbs-header">
      <span class="title">Split Result Preview</span>
      <span class="count" v-if="selected && selected.image_id">ID: {{ selected.image_id }}</span>
    </div>

    <div class="thumbs-content" v-if="selected && selected.image_id">
      <div class="preview-grid">
        <div class="preview-card">
          <div class="preview-title">Original</div>
          <div class="img-wrapper">
            <img :src="originalUrl" @error="handleOriginalError" />
          </div>
        </div>

        <div class="preview-card">
          <div class="preview-title">Segmentation</div>
          <div class="img-wrapper">
            <img :src="segmentationUrl" @error="handleSegmentationError" />
          </div>
        </div>

        <div class="preview-card">
          <div class="preview-title">
            Dominant Colors
            <span
              v-if="selected.main_color_hex"
              class="color-chip"
              :style="{ backgroundColor: selected.main_color_hex }"
            >
              {{ selected.main_color_hex }}
            </span>
          </div>
          <div class="img-wrapper">
            <img :src="paletteUrl" class="palette-img" />
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-hint">
      Click a colored point on the map to preview its images.
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const API_BASE = 'http://127.0.0.1:8000'

const props = defineProps({
  selected: Object,
  projectName: String
})

const imageId = computed(() => props.selected?.image_id || '')

const originalUrl = computed(() => {
  if (imageId.value && props.projectName) {
    return `${API_BASE}/static/projects/${props.projectName}/data/images/${imageId.value}.jpg`
  }
  return props.selected?.thumb_url || ''
})

const segmentationUrl = computed(() => {
  if (!imageId.value || !props.projectName) return ''
  return `${API_BASE}/static/projects/${props.projectName}/data/building_rgba/${imageId.value}_building_shadowfree.png`
})

const maskUrl = computed(() => {
  if (!imageId.value || !props.projectName) return ''
  return `${API_BASE}/static/projects/${props.projectName}/data/masks/${imageId.value}_building.png`
})

const paletteUrl = computed(() => {
  if (imageId.value && props.projectName) {
    return `${API_BASE}/static/projects/${props.projectName}/data/palettes/${imageId.value}_palette.png`
  }
  if (props.selected?.palette_image) {
    return `${API_BASE}${props.selected.palette_image}`
  }
  return ''
})

function handleOriginalError(e) {
  if (props.selected?.thumb_url) {
    e.target.src = props.selected.thumb_url
  } else {
    e.target.style.display = 'none'
  }
}

function handleSegmentationError(e) {
  if (maskUrl.value) {
    e.target.src = maskUrl.value
  } else {
    e.target.style.display = 'none'
  }
}
</script>

<style scoped>
.thumbs-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.thumbs-header {
  padding: 10px 16px;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
}

.title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.count {
  font-size: 12px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
}

.thumbs-content {
  flex: 1;
  padding: 12px 16px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  height: 100%;
}

.preview-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.preview-title {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  padding: 6px 10px;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  align-items: center;
  gap: 6px;
}

.color-chip {
  font-size: 10px;
  color: #fff;
  padding: 2px 6px;
  border-radius: 999px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
}

.img-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9fafb;
}

.img-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.palette-img {
  object-fit: contain;
}

.empty-hint {
  width: 100%;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
  padding: 20px;
}
</style>
