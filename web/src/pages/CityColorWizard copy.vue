<template>
  <div class="wizard-page">
    <!-- 顶部说明 + 项目状态 -->
    <div class="wizard-header">
      <div>
        <h1 class="wizard-title">城市色彩地图向导</h1>
        <p class="wizard-subtitle">
          按照 5 个步骤，从 Mapillary 街景数据到城市色彩 GeoJSON 地图。
        </p>
      </div>
      <div class="wizard-status">
        <span class="status-chip" :class="{ 'is-on': projectReady }">
          ① 工程 {{ projectReady ? '已创建' : '未创建' }}
        </span>
        <span class="status-chip" :class="{ 'is-on': bboxReady }">
          ② BBOX {{ bboxReady ? '已设置' : '未设置' }}
        </span>
        <span class="status-chip" :class="{ 'is-on': metaReady }">
          ③ 元数据 {{ metaReady ? '已获取' : '待获取' }}
        </span>
        <span class="status-chip" :class="{ 'is-on': processReady }">
          ④ 照片 {{ processReady ? '已处理' : '待处理' }}
        </span>
        <span class="status-chip" :class="{ 'is-on': geojsonReady }">
          ⑤ GeoJSON {{ geojsonReady ? '已生成' : '待生成' }}
        </span>
      </div>
    </div>

    <div class="wizard-layout">
      <!-- 左侧：步骤条 -->
      <el-card class="wizard-steps-card" shadow="never">
        <template #header>
          <div class="steps-header">
            <span class="steps-title">流程进度</span>
            <span class="steps-label">Step {{ step + 1 }} / 5</span>
          </div>
        </template>

        <el-steps
          direction="vertical"
          :active="step"
          finish-status="success"
        >
          <el-step title="1. 选择工程名称" description="创建工程与目录结构" />
          <el-step title="2. 选择范围" description="使用 BBOX code 锁定区域" />
          <el-step title="3. 获取照片" description="调用 Mapillary API 获取元数据" />
          <el-step title="4. 处理照片" description="下载图片并做语义分割" />
          <el-step title="5. 生成地图" description="生成 GeoJSON 并在地图中查看" />
        </el-steps>
      </el-card>

      <!-- 右侧：各步骤内容 -->
      <div class="wizard-main">
        <!-- Step 1 -->
        <el-card v-if="step === 0" class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>① 选择工程名称</span>
              <span class="panel-tag">Project</span>
            </div>
          </template>

          <p class="panel-desc">
            为当前分析任务起一个工程名，将在本地创建对应文件夹，例如
            <code>data/enschede/...</code>。
          </p>

          <div class="panel-body">
            <el-input
              v-model="projectName"
              placeholder="请输入工程名称，例如：enschede"
              style="max-width: 320px"
            />
            <el-button
              type="primary"
              class="mt"
              :loading="isInitLoading"
              @click="initProject"
            >
              创建工程 / 初始化目录
            </el-button>
          </div>

          <p class="panel-hint">
            小提示：可以按城市或街区命名，例如 <code>enschede_center</code>，
            方便后面切换不同工程。
          </p>
        </el-card>

        <!-- Step 2 -->
        <el-card v-else-if="step === 1" class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>② 选择范围（BBOX）</span>
              <span class="panel-tag">Bounding Box</span>
            </div>
          </template>

          <p class="panel-desc">
            使用在线 BBOX 工具框选地图区域，并复制页面下方的
            <strong>BBOX code</strong>（形如 <code>$$d...$$e...$$f...$$g...</code>）。
          </p>

          <ol class="panel-steps">
            <li>
              打开
              <a
                href="https://boundingbox.klokantech.com/"
                target="_blank"
                rel="noopener"
              >
                BBOX 选择工具
              </a>
              ；
            </li>
            <li>框选目标区域，选择坐标系 <strong>WGS 84 (GPS)</strong>；</li>
            <li>复制 “&lt;Coordinate Box&gt;” 一行中的 BBOX code；</li>
            <li>粘贴到下方输入框中，点击解析。</li>
          </ol>

          <div class="panel-body">
            <el-input
              v-model="bboxCode"
              placeholder="例如：$$dE0065157$$eE0065504$$fN0521402$$gN0521219"
            />
            <el-button
              type="primary"
              class="mt"
              :loading="isBBoxLoading"
              :disabled="!projectReady"
              @click="setBBox"
            >
              解析并保存 BBOX
            </el-button>

            <div v-if="bbox" class="mt bbox-preview">
              <span class="bbox-label">解析结果：</span>
              <span class="bbox-value">{{ bbox }}</span>
            </div>
          </div>

          <p class="panel-hint">
            解析成功后，后台会自动将 BBOX 保存到该工程，供后续获取图片使用。
          </p>
        </el-card>

        <!-- Step 3 -->
        <el-card v-else-if="step === 2" class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>③ 获取照片元数据</span>
              <span class="panel-tag">Fetch Images</span>
            </div>
          </template>

          <p class="panel-desc">
            根据刚才设置的 BBOX 调用 Mapillary Graph API，批量获取该区域内的
            <strong>图片 ID、缩略图 URL 与坐标</strong>，并保存为 JSON / CSV。
          </p>

          <div class="panel-body">
            <el-button
              type="primary"
              :loading="isFetching"
              :disabled="!bboxReady"
              @click="fetchImages"
            >
              获取照片元数据
            </el-button>
            <p class="panel-hint mt">
              首次请求可能会稍慢（几百到上千条记录），请关注下方日志输出。
            </p>
          </div>
        </el-card>

        <!-- Step 4 -->
        <el-card v-else-if="step === 3" class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>④ 处理照片（下载 + 分割）</span>
              <span class="panel-tag">Segmentation</span>
            </div>
          </template>

          <p class="panel-desc">
            对已获取的图片进行批量处理：下载到本地、使用
            <strong>SegFormer</strong> 做语义分割，仅保留建筑区域，并提取主色调。
          </p>

          <div class="panel-body">
            <el-button
              type="primary"
              :loading="isProcessing"
              :disabled="!metaReady"
              @click="processImages"
            >
              处理照片（下载 + 分割）
            </el-button>
            <p class="panel-hint mt">
              建议先在小范围 BBOX 上试跑，确认效果与时间，再扩大范围。
            </p>
          </div>
        </el-card>

        <!-- Step 5 -->
        <el-card v-else-if="step === 4" class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>⑤ 生成城市色彩 GeoJSON</span>
              <span class="panel-tag">GeoJSON + Map</span>
            </div>
          </template>

          <p class="panel-desc">
            聚合处理结果，根据图片坐标生成
            <strong>GeoJSON 点集</strong>，每个点携带对应的主色、色卡等属性，并在下方地图中加载。
          </p>

          <div class="panel-body">
            <el-button
              type="primary"
              :loading="isBuilding"
              :disabled="!processReady"
              @click="buildGeojson"
            >
              生成 GeoJSON 地图数据
            </el-button>
          </div>

          <div v-if="geojsonReady" class="map-container">
            <CityMap :project-name="projectName" />
          </div>

          <p v-if="geojsonReady" class="panel-hint mt">
            可以在地图上点击点位，查看对应的街景图片、建筑 Mask 和提取的色卡。
          </p>
        </el-card>
      </div>
    </div>

    <!-- 底部：日志面板 -->
    <el-card class="log-card" shadow="never">
      <template #header>
        <div class="log-header">
          <span>运行日志</span>
          <span class="log-hint">后端每一步的状态与错误信息会显示在这里</span>
        </div>
      </template>
      <pre class="log custom-scroll">{{ log }}</pre>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import request from '../utils/request'
import CityMap from '../map/CityMap.vue'

const step = ref(0)
const projectName = ref('enschede')
const bboxCode = ref('')
const bbox = ref('')
const log = ref('')

const geojsonReady = ref(false)

// 状态控制
const projectReady = ref(false)
const bboxReady = ref(false)
const metaReady = ref(false)
const processReady = ref(false)

// loading 状态
const isInitLoading = ref(false)
const isBBoxLoading = ref(false)
const isFetching = ref(false)
const isProcessing = ref(false)
const isBuilding = ref(false)

function addLog(msg) {
  log.value += `[${new Date().toLocaleTimeString()}] ${msg}\n`
}

async function initProject() {
  if (!projectName.value.trim()) {
    addLog('请先输入工程名称。')
    return
  }
  try {
    isInitLoading.value = true
    await request.post('/api/init-project', { project_name: projectName.value })
    projectReady.value = true
    geojsonReady.value = false
    bboxReady.value = false
    metaReady.value = false
    processReady.value = false
    addLog('工程初始化完成。')
    step.value = 1
  } catch (e) {
    addLog('工程初始化失败：' + (e?.message || e))
  } finally {
    isInitLoading.value = false
  }
}

async function setBBox() {
  if (!bboxCode.value.trim()) {
    addLog('请先粘贴 BBOX code。')
    return
  }
  try {
    isBBoxLoading.value = true
    const res = await request.post('/api/set-bbox', {
      project_name: projectName.value,
      bbox_code: bboxCode.value
    })
    bbox.value = res.data.bbox
    bboxReady.value = true
    addLog('BBOX 设置成功：' + res.data.bbox)
    step.value = 2
  } catch (e) {
    addLog('设置 BBOX 失败：' + (e?.message || e))
  } finally {
    isBBoxLoading.value = false
  }
}

async function fetchImages() {
  try {
    isFetching.value = true
    await request.post('/api/fetch-images', { project_name: projectName.value })
    metaReady.value = true
    addLog('图片元数据获取完成。')
    step.value = 3
  } catch (e) {
    addLog('获取图片失败：' + (e?.message || e))
  } finally {
    isFetching.value = false
  }
}

async function processImages() {
  try {
    isProcessing.value = true
    await request.post('/api/process-images', { project_name: projectName.value })
    processReady.value = true
    addLog('图片处理完成。')
    step.value = 4
  } catch (e) {
    addLog('处理图片失败：' + (e?.message || e))
  } finally {
    isProcessing.value = false
  }
}

async function buildGeojson() {
  try {
    isBuilding.value = true
    await request.post('/api/build-geojson', { project_name: projectName.value })
    addLog('GeoJSON 生成完成。')
    geojsonReady.value = true
  } catch (e) {
    addLog('生成 GeoJSON 失败：' + (e?.message || e))
  } finally {
    isBuilding.value = false
  }
}
</script>

<style scoped>
.wizard-page {
  padding: 24px;
  background: #f5f5f4;
  min-height: 100vh;
}

/* 顶部区域 */
.wizard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
}

.wizard-title {
  font-size: 24px;
  font-weight: 700;
  color: #1c1917; /* stone-900 */
  margin: 0;
}

.wizard-subtitle {
  margin-top: 4px;
  color: #78716c; /* stone-500 */
  font-size: 13px;
}

.wizard-status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-chip {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  color: #6b7280;
  background: #f9fafb;
}

.status-chip.is-on {
  border-color: #0f766e;
  background: #ecfdf5;
  color: #047857;
}

/* 布局 */
.wizard-layout {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.wizard-steps-card {
  max-width: 320px;
}

.wizard-main {
  flex: 1;
}

/* 响应式：宽屏左右布局 */
@media (min-width: 960px) {
  .wizard-layout {
    flex-direction: row;
    align-items: flex-start;
  }
}

/* 步骤卡片 */
.steps-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps-title {
  font-weight: 600;
  font-size: 14px;
  color: #374151;
}

.steps-label {
  font-size: 12px;
  color: #9ca3af;
}

/* 右侧面板 */
.panel-card {
  width: 100%;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #374151;
}

.panel-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
}

.panel-desc {
  font-size: 13px;
  color: #4b5563;
  margin-bottom: 12px;
}

.panel-body {
  margin-top: 8px;
}

.panel-steps {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #4b5563;
}

.panel-steps li + li {
  margin-top: 4px;
}

.panel-hint {
  font-size: 12px;
  color: #9ca3af;
}

.mt {
  margin-top: 12px;
}

/* bbox 显示 */
.bbox-preview {
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: baseline;
}

.bbox-label {
  color: #6b7280;
}

.bbox-value {
  font-family: monospace;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f3f4f6;
  color: #111827;
}

/* 地图容器 */
.map-container {
  margin-top: 16px;
  height: 420px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

/* 日志 */
.log-card {
  margin-top: 24px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.log-header span:first-child {
  font-weight: 600;
  color: #374151;
}

.log-hint {
  font-size: 11px;
  color: #9ca3af;
}

.log {
  max-height: 220px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.4;
  background: #0b1120;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 6px;
}

/* 自定义滚动条（与 Demo 保持一致感觉） */
.custom-scroll::-webkit-scrollbar {
  width: 6px;
}
.custom-scroll::-webkit-scrollbar-track {
  background: #111827;
}
.custom-scroll::-webkit-scrollbar-thumb {
  background: #6b7280;
  border-radius: 3px;
}
.custom-scroll::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
