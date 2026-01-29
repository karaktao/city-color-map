<template>
  <div class="steps-panel">
    <div class="panel-top-bar">
      <div class="section-title">WORKFLOW PROGRESS</div>
      <div class="progress-dots">
        <div class="dot" :class="{ completed: projectReady, active: step===0 }">1</div>
        <div class="line" :class="{ completed: projectReady }"></div>
        <div class="dot" :class="{ completed: bboxReady, active: step===1 }">2</div>
        <div class="line" :class="{ completed: bboxReady }"></div>
        <div class="dot" :class="{ completed: metaReady, active: step===2 }">3</div>
        <div class="line" :class="{ completed: metaReady }"></div>
        <div class="dot" :class="{ completed: processReady, active: step===3 }">4</div>
        <div class="line" :class="{ completed: processReady }"></div>
        <div class="dot" :class="{ completed: geojsonReady, active: step===4 }">5</div>
      </div>
    </div>

    <div class="steps-scroll custom-scroll">
      
      <div class="step-card" :class="{ 'is-focus': step === 0 }">
        <div class="card-header">
          <div class="step-icon">1</div>
          <div class="step-title">Project Selection / Creation</div>
          <span v-if="projectReady" class="badge-success">Loaded</span>
        </div>
        <div class="card-content">
          <p class="desc">Select an existing project to resume progress, or enter a new name to create a project.</p>
          <div class="form-row">
            <el-select
              v-model="projectName"
              filterable
              allow-create
              default-first-option
              placeholder="Select or enter project name..."
              size="large"
              :disabled="projectReady && step > 0"
              style="width: 100%"
            >
              <el-option
                v-for="item in projectList"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
            
            <el-button type="primary" size="large" :loading="isInitLoading" @click="initAndLoadProject">
              {{ isHistoryProject ? 'Load' : 'Create' }}
            </el-button>
          </div>
          
          <div class="console-label" v-if="stepLogs[0]">System Message:</div>
          <div class="console-box custom-scroll" v-if="stepLogs[0]" ref="logBox0">
            <pre>{{ stepLogs[0] }}</pre>
          </div>
        </div>
      </div>

      <div class="step-card" :class="{ 'is-focus': step === 1, 'is-disabled': !projectReady }">
         <div class="card-header">
           <div class="step-icon">2</div>
           <div class="step-title">Set BBOX</div>
           <span v-if="bboxReady" class="badge-success">Set</span>
         </div>
         <div class="card-content">
            <p class="desc">
            <li>
            Open
            <a
              href="https://boundingbox.klokantech.com/"
              target="_blank"
              rel="noopener"
            >
              BBOX Selection Tool
            </a>
            select the map area, copy the BBOX code, paste it into the input field below, then click 'Parse'.
          </li>
            </p>
            <el-input v-model="bboxCode" type="textarea" :rows="2" placeholder="Paste BBOX code..." class="mb-2" />
            <el-button class="action-btn" type="primary" :loading="isBBoxLoading" :disabled="!projectReady" @click="setBBox" plain>Parse & Save BBOX</el-button>
            <div v-if="bbox" class="result-box">
              <span class="label">Current BBOX:</span><code class="value">{{ bbox }}</code>
            </div>
            <div class="console-box custom-scroll" v-if="stepLogs[1]" ref="logBox1"><pre>{{ stepLogs[1] }}</pre></div>
         </div>
      </div>

      <div class="step-card" :class="{ 'is-focus': step === 2, 'is-disabled': !bboxReady }">
        <div class="card-header">
           <div class="step-icon">3</div>
           <div class="step-title">Fetch Metadata</div>
           <span v-if="metaReady" class="badge-success">Fetched</span>
        </div>
        <div class="card-content">
           <p class="desc">Call Mapillary API to fetch image coordinates within the BBOX area.</p>
           <el-button class="action-btn" type="primary" :loading="isFetching" :disabled="!bboxReady" @click="fetchImages">Start Fetching Data</el-button>
           <div class="console-label" v-if="stepLogs[2]">Terminal Output:</div>
           <div class="console-box custom-scroll" v-if="stepLogs[2]" ref="logBox2"><pre>{{ stepLogs[2] }}</pre></div>
        </div>
      </div>

      <div class="step-card" :class="{ 'is-focus': step === 3, 'is-disabled': !metaReady }">
        <div class="card-header">
           <div class="step-icon">4</div>
           <div class="step-title">Segmentation & Extraction</div>
           <span v-if="processReady" class="badge-success">Done</span>
        </div>
        <div class="card-content">
           <p class="desc">Download images -> SegFormer segmentation -> Extract dominant building colors.</p>
           <el-button class="action-btn" type="primary" :loading="isProcessing" :disabled="!metaReady" @click="processImages">Run Processing Task</el-button>
           <div class="console-label" v-if="stepLogs[3]">Terminal Output:</div>
           <div class="console-box custom-scroll" v-if="stepLogs[3]" ref="logBox3"><pre>{{ stepLogs[3] }}</pre></div>
        </div>
      </div>

      <div class="step-card" :class="{ 'is-focus': step === 4, 'is-disabled': !processReady }">
        <div class="card-header">
           <div class="step-icon">5</div>
           <div class="step-title">Generate Map Data</div>
           <span v-if="geojsonReady" class="badge-success">Ready</span>
        </div>
        <div class="card-content">
           <p class="desc">Aggregate all data and generate GeoJSON point layer for rendering.</p>
           <el-button class="action-btn" type="success" :loading="isBuilding" :disabled="!processReady" @click="buildGeojson">Generate GeoJSON</el-button>
           <div class="console-box custom-scroll" v-if="stepLogs[4]" ref="logBox4"><pre>{{ stepLogs[4] }}</pre></div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, computed } from 'vue' // 引入 onMounted, computed
import request from '../../utils/request'

const emit = defineEmits(['load-map', 'bbox-set', 'project-change'])

// 状态变量
const step = ref(0)
const projectName = ref('') // 默认为空，等待用户选择
const projectList = ref([]) // 项目列表
const bboxCode = ref('')
const bbox = ref('')

// 日志内容
const stepLogs = ref({ 0: '', 1: '', 2: '', 3: '', 4: '' })
const logBox0 = ref(null); const logBox1 = ref(null); const logBox2 = ref(null); const logBox3 = ref(null); const logBox4 = ref(null)

// 流程状态
const projectReady = ref(false)
const bboxReady = ref(false)
const metaReady = ref(false)
const processReady = ref(false)
const geojsonReady = ref(false)

// Loading 状态
const isInitLoading = ref(false)
const isBBoxLoading = ref(false)
const isFetching = ref(false)
const isProcessing = ref(false)
const isBuilding = ref(false)

// 计算属性：判断当前输入的是否是历史项目
const isHistoryProject = computed(() => {
  return projectList.value.includes(projectName.value)
})

// === 1. 初始化时获取项目列表 ===
onMounted(async () => {
  try {
    const res = await request.get('/api/projects')
    if (res.data && res.data.projects) {
      projectList.value = res.data.projects
    }
  } catch (e) {
    console.error('Failed to load project list', e)
  }
})

// === 2. 修改后的“初始化/加载”逻辑 ===
async function initAndLoadProject() {
  if (!projectName.value.trim()) return addStepLog(0, 'Please enter or select a project name')
  
  try {
    isInitLoading.value = true
    stepLogs.value[0] = '' 
    
    const action = isHistoryProject.value ? 'Loading history project' : 'Initializing new project'
    addStepLog(0, `${action}: ${projectName.value}...`)
    
    // 1. 无论新建还是加载，都调用 init-project 确保目录结构存在
    await request.post('/api/init-project', { project_name: projectName.value })
    projectReady.value = true
    emit('project-change', projectName.value)
    
    // 2. 检查项目状态，恢复进度
    await restoreProjectStatus()
    
    // 如果是新建的，刷新列表
    if (!projectList.value.includes(projectName.value)) {
        projectList.value.unshift(projectName.value)
    }

  } catch (e) {
    addStepLog(0, '❌ Operation failed: ' + (e.message || e))
  } finally {
    isInitLoading.value = false
  }
}

// === 3. 恢复进度的核心逻辑 ===
async function restoreProjectStatus() {
  try {
    const res = await request.get(`/api/project-status/${projectName.value}`)
    const status = res.data
    
    // 恢复 BBOX
    if (status.bbox) {
        bbox.value = status.bbox
        bboxReady.value = true
        bboxCode.value = status.bbox_code || '' // 回填输入框
        addStepLog(1, `[RESTORE] Existing BBOX detected: ${status.bbox}`, false)
        emit('bbox-set', status.bbox)
    } else {
        bboxReady.value = false
    }

    // 恢复元数据状态
    if (status.meta_ready) {
        metaReady.value = true
        addStepLog(2, `[RESTORE] Existing metadata detected (images_meta.csv).`, false)
    } else {
        metaReady.value = false
    }

    // 恢复处理状态
    if (status.process_ready) {
        processReady.value = true
        addStepLog(3, `[RESTORE] Existing processing results detected (Color Summary / Masks).`, false)
    } else {
        processReady.value = false
    }

    // 恢复 GeoJSON 状态
    if (status.geojson_ready) {
        geojsonReady.value = true
        addStepLog(4, `[RESTORE] Existing GeoJSON map data detected.`, false)
        // 自动加载地图
        emit('load-map', projectName.value)
    } else {
        geojsonReady.value = false
    }

    // 智能跳转到下一步
    if (geojsonReady.value) step.value = 4 // 全都好了，停在最后
    else if (processReady.value) step.value = 4 // 等待生成地图
    else if (metaReady.value) step.value = 3    // 等待处理图片
    else if (bboxReady.value) step.value = 2    // 等待获取元数据
    else step.value = 1                         // 等待设置 BBOX

    addStepLog(0, `✅ Project loaded successfully, restored to step ${step.value + 1}.`)

  } catch (e) {
    console.error("Restore failed", e)
    addStepLog(0, "⚠️ Exception during status restore, please check steps manually.")
  }
}

// -------------------------------------------------------------
// 以下工具函数保持不变
// -------------------------------------------------------------
async function fetchStream(url, payload, onChunk, onError) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      if (onChunk) onChunk(chunk)
    }
  } catch (e) {
    if (onError) onError(e)
    else console.error(e)
  }
}

function addStepLog(stepIndex, msg, isAppend = true) {
  const timestamp = `[${new Date().toLocaleTimeString()}] `
  const text = timestamp + msg + '\n'
  if (isAppend) stepLogs.value[stepIndex] += text
  else stepLogs.value[stepIndex] = text
  scrollToBottom(stepIndex)
}

function scrollToBottom(index) {
  nextTick(() => {
    const refs = [logBox0, logBox1, logBox2, logBox3, logBox4]
    const el = refs[index]?.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// Step 2, 3, 4, 5 的函数逻辑保持不变，直接复用你原来的即可
async function setBBox() {
  if (!bboxCode.value.trim()) return addStepLog(1, 'Please paste BBOX first')
  try {
    isBBoxLoading.value = true
    stepLogs.value[1] = ''
    addStepLog(1, 'Parsing BBOX...')
    const res = await request.post('/api/set-bbox', { project_name: projectName.value, bbox_code: bboxCode.value })
    bbox.value = res.data.bbox; bboxReady.value = true; addStepLog(1, `✅ BBOX set successfully: ${bbox.value}`); step.value = 2; emit('bbox-set', bbox.value)
  } catch (e) { addStepLog(1, '❌ Set failed: ' + (e.message || e)) } finally { isBBoxLoading.value = false }
}
async function fetchImages() {
  isFetching.value = true; stepLogs.value[2] = ''
  await fetchStream('/api/fetch-images', { project_name: projectName.value }, (chunk) => { stepLogs.value[2] += chunk; scrollToBottom(2) }, (err) => { addStepLog(2, '❌ Interrupted: ' + err.message) })
  isFetching.value = false; metaReady.value = true; addStepLog(2, '✅ Metadata fetch process completed.'); step.value = 3
}
async function processImages() {
  isProcessing.value = true; stepLogs.value[3] = ''
  await fetchStream('/api/process-images', { project_name: projectName.value }, (chunk) => { stepLogs.value[3] += chunk; scrollToBottom(3) }, (err) => { addStepLog(3, '❌ Interrupted: ' + err.message) })
  isProcessing.value = false; processReady.value = true; addStepLog(3, '✅ Image processing completed.'); step.value = 4
}
async function buildGeojson() {
  isBuilding.value = true; stepLogs.value[4] = ''
  await fetchStream('/api/build-geojson', { project_name: projectName.value }, (chunk) => { stepLogs.value[4] += chunk; scrollToBottom(4) }, (err) => { addStepLog(4, '❌ Interrupted: ' + err.message) })
  isBuilding.value = false; geojsonReady.value = true; addStepLog(4, '✅ GeoJSON generation completed, loading map...'); emit('load-map', projectName.value)
}
</script>

<style scoped>
.steps-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* 顶部状态栏 */
.panel-top-bar {
  padding: 16px 20px;
  border-bottom: 1px solid #f3f4f6;
  background: #fff;
  z-index: 2;
  flex-shrink: 0;
}

.section-title {
  font-size: 11px;
  text-transform: uppercase;
  color: #94a3b8;
  margin-bottom: 12px;
  font-weight: 700;
  letter-spacing: 0.8px;
}

.progress-dots {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  transition: all 0.3s;
}

.dot.completed { background: #10b981; color: white; }
.dot.active { box-shadow: 0 0 0 2px #0f766e; color: #0f766e; background: #fff; }

.line {
  flex: 1;
  height: 2px;
  background: #f1f5f9;
  margin: 0 6px;
  border-radius: 2px;
}
.line.completed { background: #a7f3d0; }

/* 滚动列表 */
.steps-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f8fafc; /* 很浅的背景色 */
}

/* 步骤卡片 */
.step-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
  transition: all 0.25s ease;
  position: relative;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}

.step-card.is-focus {
  border-color: #0f766e;
  box-shadow: 0 0 0 1px #0f766e, 0 8px 20px -6px rgba(15, 118, 110, 0.15);
  transform: translateY(-2px);
}

.step-card.is-disabled {
  opacity: 0.6;
  pointer-events: none;
  filter: grayscale(0.9);
  background: #f9fafb;
}

.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.step-icon {
  font-size: 20px;
  font-weight: 800;
  color: #e2e8f0;
  margin-right: 12px;
  line-height: 1;
}
.is-focus .step-icon { color: #0f766e; }

.step-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}

.badge-success {
  font-size: 11px;
  background: #d1fae5;
  color: #047857;
  padding: 3px 8px;
  border-radius: 99px;
  font-weight: 600;
}

.card-content {
  padding-left: 32px; /* 对齐标题下方 */
}

.desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 16px;
  line-height: 1.5;
}

/* 表单元素 */
.form-row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  align-items: center;
}

.action-btn {
  width: 100%;
  justify-content: center;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.mb-2 { margin-bottom: 10px; }

/* BBOX 结果框 */
.result-box {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.result-box .label { color: #64748b; font-weight: 500; }
.result-box .value { color: #334155; font-family: monospace; word-break: break-all; }

/* 终端风格日志框 */
.console-label {
  margin-top: 16px;
  margin-bottom: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
}

.console-box {
  background: #0f172a; /* 深色背景 */
  border-radius: 6px;
  padding: 12px;
  height: 80px; /* 固定高度 */
  overflow-y: auto;
  border: 1px solid #1e293b;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
}

.console-box pre {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 11px;
  line-height: 1.6;
  color: #e2e8f0;
  white-space: pre-wrap; /* 允许换行 */
  margin: 0;
}

/* 滚动条美化 */
.custom-scroll::-webkit-scrollbar { width: 6px; }
.custom-scroll::-webkit-scrollbar-track { background: transparent; }
.custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
.custom-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* 日志框内部深色滚动条 */
.console-box.custom-scroll::-webkit-scrollbar-thumb { background: #334155; }
.console-box.custom-scroll::-webkit-scrollbar-thumb:hover { background: #475569; }
</style>
