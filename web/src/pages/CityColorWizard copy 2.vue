<template>
  <div class="wizard-page">
    <!-- 顶部说明 -->
    <TopIntro class="top-intro" />

    <!-- 中间：左地图 + 右步骤 -->
    <div class="wizard-main">
      <!-- 左边：地图 + 缩略图 -->
      <div class="left-column">
        <MapPanel class="map-panel" />
        <ThumbsPanel class="thumbs-panel" />
      </div>

      <!-- 右边：步骤面板（内部自己滚动） -->
      <div class="right-column">
        <StepsPanel />
      </div>
    </div>
  </div>
</template>

<script setup>
import TopIntro from '../components/citycolor/TopIntro.vue'
import MapPanel from '../components/citycolor/MapPanel.vue'
import ThumbsPanel from '../components/citycolor/ThumbsPanel.vue'
import StepsPanel from '../components/citycolor/StepsPanel.vue'
</script>

<style scoped>
.wizard-page {
  display: flex;
  flex-direction: column;
  height: 100vh;          /* 整个页面固定为一屏高 */
  background:rgb(255, 255, 255);    /* 随便一个背景色 */
}

/* 顶部说明占固定高度，下面用剩余空间 */
.top-intro {
  flex: 0 0 auto;
}

/* 中间主区域：左右两列，高度占满剩余空间 */
.wizard-main {
  flex: 1 1 auto;
  display: flex;
  overflow: hidden;       /* 不让主区域产生额外滚动条 */
}

/* 左列：地图 + 缩略图竖向排列 */
.left-column {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 8px 8px 16px;
  overflow: hidden;       /* 左列内部如果超出交给子元素处理 */
}

/* 地图区域尽量大 */
.map-panel {
  flex: 3;
  min-height: 0;          /* 关键：配合 flex 允许内部再滚动 */
}

/* 缩略图区固定一块高度，也可以用 flex 比例 */
.thumbs-panel {
  flex: 1;
  min-height: 0;
}

/* 右列：只负责给 StepsPanel 一个固定高度的容器 */
.right-column {
  flex: 1;
  padding: 8px 16px 8px 8px;
  overflow: hidden;       /* 右列本身不滚动 */
}

/* 让 StepsPanel 高度 = 右列高度 */
.right-column > * {
  height: 100%;
}
</style>
