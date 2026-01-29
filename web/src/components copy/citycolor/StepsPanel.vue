<template>
  <div class="steps-panel">
    <!-- 顶部状态 chips -->
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

    <!-- 中间滚动区：5 个步骤卡片（每个卡片内部有自己的日志盒子） -->
    <div class="steps-scroll custom-scroll">
      <!-- Step 1 工程 -->
      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header" :class="{ 'is-active': step === 0 }">
            <span>① 选择工程名称</span>
            <span class="panel-tag">Project</span>
          </div>
        </template>

        <p class="panel-desc">
          为当前分析任务起一个工程名，将在
          <code>projects/&lt;name&gt;/data</code> 下创建目录结构。
        </p>

        <div class="panel-body">
          <el-input
            v-model="projectName"
            placeholder="请输入工程名称，例如：001 或 enschede"
            style="max-width: 260px"
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
          小提示：建议用城市名或任务名，例如 <code>enschede_center</code>。
        </p>

        <!-- Step1 日志 -->
        <div class="step-log-wrapper">
          <div class="step-log-header">步骤 1 运行日志</div>
          <pre class="step-log custom-scroll">{{ stepLogs[0] }}</pre>
        </div>
      </el-card>

      <!-- Step 2 BBOX -->
      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header" :class="{ 'is-active': step === 1 }">
            <span>② 选择范围（BBOX）</span>
            <span class="panel-tag">Bounding Box</span>
          </div>
        </template>

        <p class="panel-desc">
          可以在 <strong>boundingbox</strong> 网站上框选范围，也可以直接使用
          左侧地图框选得到的 BBOX 字符串（lon_min,lat_min,lon_max,lat_max）。
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
            框选地图范围，复制 BBOX code 粘贴到下方输入框，点击解析。
          </li>
        </ol>

        <div class="panel-body">
          <el-input
            v-model="bboxCode"
            type="textarea"
            rows="2"
            placeholder="例如：$$dE0065157$$eE0065504$$fN0521402$$gN0521219 或 6.84,52.22,6.92,52.26"
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
          解析成功后，BBOX 会保存到该工程的 <code>config.json</code> 中。
        </p>

        <!-- Step2 日志 -->
        <div class="step-log-wrapper">
          <div class="step-log-header">步骤 2 运行日志</div>
          <pre class="step-log custom-scroll">{{ stepLogs[1] }}</pre>
        </div>
      </el-card>

      <!-- Step 3 获取元数据 -->
      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header" :class="{ 'is-active': step === 2 }">
            <span>③ 获取照片元数据</span>
            <span class="panel-tag">Fetch Images</span>
          </div>
        </template>

        <p class="panel-desc">
          根据 BBOX 调用 Mapillary Graph API，批量获取该区域的
          <strong>图片 ID、缩略图 URL 和坐标</strong>，并保存到
          <code>data/csv/image_metadata.csv</code> 等文件中。
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
            首次获取可能稍慢，可以在本步骤日志中查看抓取情况。
          </p>
        </div>

        <!-- Step3 日志 -->
        <div class="step-log-wrapper">
          <div class="step-log-header">步骤 3 运行日志</div>
          <pre class="step-log custom-scroll">{{ stepLogs[2] }}</pre>
        </div>
      </el-card>

      <!-- Step 4 处理照片 -->
      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header" :class="{ 'is-active': step === 3 }">
            <span>④ 处理照片（下载 + 分割）</span>
            <span class="panel-tag">Segmentation</span>
          </div>
        </template>

        <p class="panel-desc">
          下载图片到本地，使用 <strong>SegFormer</strong> 做语义分割，仅保留建筑区域，
          并提取主色调，生成带色卡的 PNG 和 <code>color_summary.csv</code>。
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
            建议先用小范围 BBOX 测试，确认速度与效果，再扩大范围。
          </p>
        </div>

        <!-- Step4 日志 -->
        <div class="step-log-wrapper">
          <div class="step-log-header">步骤 4 运行日志</div>
          <pre class="step-log custom-scroll">{{ stepLogs[3] }}</pre>
        </div>
      </el-card>

      <!-- Step 5 生成 GeoJSON -->
      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header" :class="{ 'is-active': step === 4 }">
            <span>⑤ 生成城市色彩 GeoJSON</span>
            <span class="panel-tag">GeoJSON + Map</span>
          </div>
        </template>

        <p class="panel-desc">
          聚合元数据与颜色统计，根据图片坐标生成
          <strong>GeoJSON 点图层</strong>，每个点包含主色、色卡图片路径等属性，
          供左侧地图加载。
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

          <p v-if="geojsonReady" class="panel-hint mt">
            已生成 <code>data/geojson/facade_colors.geojson</code>，
            左侧地图可以通过 <code>/api/geojson/&lt;project&gt;</code> 加载。
          </p>
        </div>

        <!-- Step5 日志 -->
        <div class="step-log-wrapper">
          <div class="step-log-header">步骤 5 运行日志</div>
          <pre class="step-log custom-scroll">{{ stepLogs[4] }}</pre>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import request from '../../utils/request'

// 当前步骤（仅用于高亮）
const step = ref(0)

// 工程 / 参数
const projectName = ref('001')
const bboxCode = ref('')
const bbox = ref('')

// 每个步骤的日志
const stepLogs = ref({
  0: '',
  1: '',
  2: '',
  3: '',
  4: ''
})

// 状态控制
const projectReady = ref(false)
const bboxReady = ref(false)
const metaReady = ref(false)
const processReady = ref(false)
const geojsonReady = ref(false)

// loading 状态
const isInitLoading = ref(false)
const isBBoxLoading = ref(false)
const isFetching = ref(false)
const isProcessing = ref(false)
const isBuilding = ref(false)

function addStepLog(stepIndex, msg) {
  const prefix = `[${new Date().toLocaleTimeString()}] `
  stepLogs.value[stepIndex] += prefix + msg + '\n'
}

// Step 1：初始化工程
async function initProject() {
  if (!projectName.value.trim()) {
    addStepLog(0, '请先输入工程名称。')
    return
  }
  try {
    isInitLoading.value = true
    await request.post('/api/init-project', {
      project_name: projectName.value
    })
    projectReady.value = true
    // 重置后续状态
    bboxReady.value = false
    metaReady.value = false
    processReady.value = false
    geojsonReady.value = false

    // 清空后续步骤日志
    stepLogs.value[1] = ''
    stepLogs.value[2] = ''
    stepLogs.value[3] = ''
    stepLogs.value[4] = ''

    addStepLog(0, `工程 "${projectName.value}" 初始化完成。`)
    step.value = 1
  } catch (e) {
    addStepLog(0, '工程初始化失败：' + (e?.message || e))
  } finally {
    isInitLoading.value = false
  }
}

// Step 2：设置 BBOX
async function setBBox() {
  if (!bboxCode.value.trim()) {
    addStepLog(1, '请先粘贴 BBOX code 或十进制 bbox。')
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
    addStepLog(1, 'BBOX 设置成功：' + res.data.bbox)
    step.value = 2
  } catch (e) {
    addStepLog(1, '设置 BBOX 失败：' + (e?.message || e))
  } finally {
    isBBoxLoading.value = false
  }
}

// Step 3：获取图片元数据
async function fetchImages() {
  try {
    isFetching.value = true
    await request.post('/api/fetch-images', {
      project_name: projectName.value
    })
    metaReady.value = true
    addStepLog(2, '图片元数据获取完成。')
    step.value = 3
  } catch (e) {
    addStepLog(2, '获取图片失败：' + (e?.message || e))
  } finally {
    isFetching.value = false
  }
}

// Step 4：下载 + 分割
async function processImages() {
  try {
    isProcessing.value = true
    await request.post('/api/process-images', {
      project_name: projectName.value
    })
    processReady.value = true
    addStepLog(3, '图片下载与语义分割完成。')
    step.value = 4
  } catch (e) {
    addStepLog(3, '处理图片失败：' + (e?.message || e))
  } finally {
    isProcessing.value = false
  }
}

// Step 5：生成 GeoJSON
async function buildGeojson() {
  try {
    isBuilding.value = true
    await request.post('/api/build-geojson', {
      project_name: projectName.value
    })
    geojsonReady.value = true
    addStepLog(4, 'GeoJSON 生成完成。')
  } catch (e) {
    addStepLog(4, '生成 GeoJSON 失败：' + (e?.message || e))
  } finally {
    isBuilding.value = false
  }
}
</script>

<style scoped>
.steps-panel {
  display: flex;
  flex-direction: column;
  height: 100%;     /* ✅ 父容器给多高，就占多高 */
}

/* 顶部状态 chips */
.wizard-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.status-chip {
  font-size: 12px;
  padding: 3px 8px;
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

/* 中间滚动区：卡片纵向排列 */
.steps-scroll {
  flex: 1;
  min-height: 0;    /* ✅ 允许内部滚动，而不是把父容器撑高 */
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 每个步骤卡片 */
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

.panel-header.is-active {
  color: #0f766e;
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
  margin-bottom: 10px;
}

.panel-body {
  margin-top: 4px;
}

.panel-steps {
  margin: 0 0 8px;
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
  margin-top: 10px;
}

/* bbox 预览 */
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

/* 步骤内日志盒子：高度固定、内部滚动 */
.step-log-wrapper {
  margin-top: 10px;
}

.step-log-header {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 4px;
}

.step-log {
  max-height: 120px;
  min-height: 80px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.4;
  background: #0b1120;
  color: #e5e7eb;
  padding: 6px;
  border-radius: 6px;
}

/* 自定义滚动条（面板和日志共用） */
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
