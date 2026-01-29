<template>
  <div class="wizard-page">
    <div class="wizard-header-wrapper">
      <TopIntro />
    </div>

    <div class="wizard-main">
      <div class="left-column">
        <div class="panel-container map-wrapper">
          <MapPanel 
            :geojson-url="currentGeojsonUrl" 
            :active-bbox="currentBbox"
            @image-click="handleImageClick" />
        </div>
        <div class="panel-container thumbs-wrapper">
          <ThumbsPanel 
            :selected="selectedFeature"
            :project-name="currentProjectName" />
        </div>
      </div>

      <div class="right-column">
        <div class="panel-container steps-wrapper">
          <StepsPanel 
            @load-map="handleLoadMap" 
            @bbox-set="handleBboxSet"
            @project-change="handleProjectChange" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TopIntro from '../components/citycolor/TopIntro.vue'
import MapPanel from '../components/citycolor/MapPanel.vue'
import ThumbsPanel from '../components/citycolor/ThumbsPanel.vue'
import StepsPanel from '../components/citycolor/StepsPanel.vue'

// 1. 定义响应式变量
const currentGeojsonUrl = ref('')
const currentBbox = ref('')
const currentProjectName = ref('')
const selectedFeature = ref(null)

// 2. 定义处理函数
function handleLoadMap(projectName) {
  currentGeojsonUrl.value = `/api/geojson/${projectName}?t=${Date.now()}`
  currentProjectName.value = projectName
  selectedFeature.value = null
  console.log('父组件收到加载请求，更新 URL:', currentGeojsonUrl.value)
}
function handleBboxSet(bboxStr) {
  console.log('父组件收到 BBOX 更新:', bboxStr)
  currentBbox.value = bboxStr
}
function handleProjectChange(projectName) {
  currentProjectName.value = projectName
  selectedFeature.value = null
}
function handleImageClick(featureProps) {
  selectedFeature.value = featureProps
}
</script>

<style scoped>
.wizard-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f3f4f6; /* 整体浅灰背景 */
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.wizard-header-wrapper {
  flex: 0 0 auto;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  z-index: 10;
}

.wizard-main {
  flex: 1 1 auto;
  display: flex;
  overflow: hidden;
  padding: 16px; /* 给整个主区域加一点内边距 */
  gap: 16px;     /* 左右列之间的间距 */
}

/* 左列 */
.left-column {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  min-width: 0;
}

/* 右列 */
.right-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 350px; /* 防止右侧太窄 */
}

/* 通用面板容器：白底、圆角、阴影 */
.panel-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 
              0 2px 4px -1px rgba(0, 0, 0, 0.03);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 具体高度分配 */
.map-wrapper {
  flex: 1; /* 地图占满剩余空间 */
  min-height: 0;
  position: relative;
}

.thumbs-wrapper {
  height: 260px; /* 固定缩略图高度 */
  flex-shrink: 0;
}

.steps-wrapper {
  height: 100%; /* 右侧占满 */
}
</style>
