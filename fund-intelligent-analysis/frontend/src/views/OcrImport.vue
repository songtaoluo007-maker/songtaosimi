<template>
  <div class="ocr-import">
    <header class="page-head">
      <div>
        <h2>截图导入持仓</h2>
        <p>上传天天基金或支付宝持仓截图，自动识别并导入</p>
      </div>
    </header>

    <!-- 步骤指示器 -->
    <div class="steps-bar">
      <div class="step" :class="{ active: step === 1, done: step > 1 }">
        <div class="step-num">1</div>
        <span>上传识别</span>
      </div>
      <div class="step-line" :class="{ done: step > 1 }" />
      <div class="step" :class="{ active: step === 2, done: step > 2 }">
        <div class="step-num">2</div>
        <span>核对修正</span>
      </div>
      <div class="step-line" :class="{ done: step > 2 }" />
      <div class="step" :class="{ active: step === 3, done: step > 3 }">
        <div class="step-num">3</div>
        <span>确认导入</span>
      </div>
    </div>

    <!-- Step 1: 上传 -->
    <section v-show="step === 1">
      <el-card shadow="hover">
        <el-form :inline="true" style="margin-bottom: 12px;">
          <el-form-item label="截图来源">
            <el-radio-group v-model="source">
              <el-radio value="alipay">支付宝</el-radio>
              <el-radio value="tiantian">同花顺 / 天天基金</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>

        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          accept="image/*"
          multiple
          drag
          :limit="10"
        >
          <el-icon :size="48" color="#c0c4cc"><UploadFilled /></el-icon>
          <div style="margin-top: 8px;">拖拽或点击上传截图（支持多张分页截图）</div>
          <template #tip>
            <div style="color: #909399; font-size: 12px;">
              支持 PNG/JPG 格式，{{ source === 'alipay' ? '支付宝' : '同花顺/天天基金' }}持仓页面截图
            </div>
          </template>
        </el-upload>

        <div style="margin-top: 16px; text-align: center;">
          <el-button type="primary" size="large" :loading="recognizing" :disabled="fileList.length === 0" @click="handleRecognize">
            <el-icon><Camera /></el-icon> 开始识别
          </el-button>
        </div>
      </el-card>
    </section>

    <!-- Step 2: 核对修正 -->
    <section v-show="step === 2">
      <!-- 导入概览卡片 -->
      <div class="import-summary" v-if="editableResults.length > 0">
        <div class="summary-card">
          <span>识别基金</span>
          <strong>{{ editableResults.length }} 只</strong>
        </div>
        <div class="summary-card">
          <span>总市值</span>
          <strong>¥{{ formatMoney(totalImportValue) }}</strong>
        </div>
        <div class="summary-card">
          <span>总盈亏</span>
          <strong :class="totalImportPnl >= 0 ? 'up' : 'down'">
            {{ totalImportPnl >= 0 ? '+' : '' }}¥{{ formatMoney(totalImportPnl) }}
          </strong>
        </div>
        <div class="summary-card">
          <span>收益率</span>
          <strong :class="totalImportPnlRatio >= 0 ? 'up' : 'down'">
            {{ totalImportPnlRatio >= 0 ? '+' : '' }}{{ totalImportPnlRatio.toFixed(1) }}%
          </strong>
        </div>
        <div class="summary-card" v-if="duplicateCount > 0" style="border-color: var(--warning-400); background: #fffbeb;">
          <span>重复基金</span>
          <strong style="color: var(--warning-600);">{{ duplicateCount }} 只</strong>
        </div>
      </div>

      <el-card shadow="hover">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: bold;">识别结果 — 可编辑修正后导入</span>
            <div>
              <el-button @click="step = 1">返回重新上传</el-button>
              <el-button type="primary" :disabled="editableResults.length === 0" @click="step = 3">
                下一步：确认导入
              </el-button>
            </div>
          </div>
        </template>

        <el-table :data="editableResults" stripe style="width: 100%;">
          <el-table-column label="状态" width="70">
            <template #default="{ row }">
              <el-tag v-if="row._duplicate" type="warning" size="small" effect="dark">合并</el-tag>
              <el-tag v-else type="success" size="small">新增</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="基金代码" width="110">
            <template #default="{ row }">
              <el-input v-model="row.fund_code" size="small" placeholder="6位代码" maxlength="6" />
            </template>
          </el-table-column>
          <el-table-column label="基金名称" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.fund_name" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="市值/金额" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.amount" size="small" :min="0" :precision="2" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="成本" width="110">
            <template #default="{ row }">
              <el-input-number v-model="row.cost_amount" size="small" :min="0" :precision="2" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="持有收益" width="120">
            <template #default="{ row }">
              <span :style="{ color: (row._pnl || 0) >= 0 ? '#67C23A' : '#F56C6C', fontWeight: 'bold' }">
                {{ (row._pnl || 0) >= 0 ? '+' : '' }}{{ (row._pnl || 0).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="收益率" width="100">
            <template #default="{ row }">
              <span :style="{ color: (row._pnlRatio || 0) >= 0 ? '#67C23A' : '#F56C6C', fontWeight: 'bold' }">
                {{ (row._pnlRatio || 0) >= 0 ? '+' : '' }}{{ (row._pnlRatio || 0).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="140">
            <template #default="{ row }">
              <span v-if="row._duplicate" style="color: var(--warning-600); font-size: 12px;">
                已有持仓，将合并
              </span>
              <span v-else style="color: #909399; font-size: 12px;">{{ row.note || row.error || '' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button size="small" type="danger" @click="editableResults.splice($index, 1); recalcSummary()">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-alert
        v-if="ocrErrors.length"
        style="margin-top: 14px;"
        type="warning"
        :closable="false"
        show-icon
        title="部分截图未识别到有效基金信息"
      >
        <template #default>
          <div v-for="(err, idx) in ocrErrors" :key="idx">{{ err }}</div>
        </template>
      </el-alert>
    </section>

    <!-- Step 3: 确认导入 -->
    <section v-show="step === 3">
      <el-card shadow="hover">
        <template #header>
          <span style="font-weight: bold;">确认导入 — 共 {{ editableResults.length }} 只基金</span>
        </template>

        <div class="confirm-grid">
          <div class="confirm-stat">
            <span>新增加</span>
            <strong style="color: var(--success-600);">{{ newCount }} 只</strong>
          </div>
          <div class="confirm-stat">
            <span>合并更新</span>
            <strong style="color: var(--warning-600);">{{ duplicateCount }} 只</strong>
          </div>
          <div class="confirm-stat">
            <span>总市值</span>
            <strong>¥{{ formatMoney(totalImportValue) }}</strong>
          </div>
          <div class="confirm-stat">
            <span>总盈亏</span>
            <strong :class="totalImportPnl >= 0 ? 'up' : 'down'">
              {{ totalImportPnl >= 0 ? '+' : '' }}¥{{ formatMoney(totalImportPnl) }}
            </strong>
          </div>
        </div>

        <el-divider />

        <el-table :data="editableResults" stripe size="small" max-height="360">
          <el-table-column label="" width="50">
            <template #default="{ row }">
              <el-tag v-if="row._duplicate" type="warning" size="small">合并</el-tag>
              <el-tag v-else type="success" size="small">新增</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="fund_code" label="代码" width="90" />
          <el-table-column prop="fund_name" label="名称" min-width="140" />
          <el-table-column label="金额" width="110">
            <template #default="{ row }">¥{{ (row.amount || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="收益" width="120">
            <template #default="{ row }">
              <span :style="{ color: (row._pnl || 0) >= 0 ? '#67C23A' : '#F56C6C' }">
                {{ (row._pnl || 0) >= 0 ? '+' : '' }}{{ (row._pnl || 0).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <div style="margin-top: 20px; text-align: center;">
          <el-button @click="step = 2">返回修改</el-button>
          <el-button type="primary" size="large" :loading="confirming" @click="handleConfirm">
            <el-icon><CircleCheck /></el-icon> 确认导入 {{ editableResults.length }} 只基金
          </el-button>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { uploadOcr, confirmOcr } from '../api'

const step = ref(1)
const source = ref('tiantian')
const fileList = ref<File[]>([])
const recognizing = ref(false)
const confirming = ref(false)
const ocrResults = ref<any[]>([])
const editableResults = ref<any[]>([])
const ocrErrors = ref<string[]>([])

// 已有持仓的基金代码（用于重复检测）
const existingCodes = ref<Set<string>>(new Set())

// 计算属性
const totalImportValue = computed(() =>
  editableResults.value.reduce((s, r) => s + (Number(r.amount) || 0), 0)
)
const totalImportCost = computed(() =>
  editableResults.value.reduce((s, r) => s + (Number(r.cost_amount) || 0), 0)
)
const totalImportPnl = computed(() => totalImportValue.value - totalImportCost.value)
const totalImportPnlRatio = computed(() =>
  totalImportCost.value > 0 ? (totalImportPnl.value / totalImportCost.value) * 100 : 0
)
const duplicateCount = computed(() =>
  editableResults.value.filter(r => r._duplicate).length
)
const newCount = computed(() => editableResults.value.length - duplicateCount.value)

function formatMoney(val: number) {
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function recalcSummary() {
  editableResults.value.forEach(r => {
    r._pnl = Number(r.amount || 0) - Number(r.cost_amount || 0)
    r._pnlRatio = r.cost_amount > 0 ? (r._pnl / r.cost_amount) * 100 : 0
    r._duplicate = existingCodes.value.has(r.fund_code?.trim())
  })
}

function handleFileChange(file: UploadFile) {
  if (file.raw && !fileList.value.some(f => f.name === file.raw!.name && f.size === file.raw!.size)) {
    fileList.value.push(file.raw)
  }
}

function handleFileRemove(file: UploadFile) {
  if (!file.raw) return
  fileList.value = fileList.value.filter(f => !(f.name === file.raw!.name && f.size === file.raw!.size))
}

async function handleRecognize() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先上传截图')
    return
  }

  recognizing.value = true
  try {
    // 先获取已有持仓代码用于重复检测
    try {
      const { getHoldings } = await import('../api')
      const holdings = await getHoldings() as any[]
      existingCodes.value = new Set(holdings.map((h: any) => h.fund_code))
    } catch { /* ignore */ }

    const formData = new FormData()
    fileList.value.forEach(f => formData.append('files', f))

    const res = await uploadOcr(formData, source.value) as any
    ocrResults.value = res.results || []
    ocrErrors.value = ocrResults.value
      .filter((r: any) => r.error || r.note)
      .map((r: any) => r.error || r.note)
      .filter(Boolean)
    editableResults.value = ocrResults.value
      .filter((r: any) => !r.error)
      .map((r: any) => {
        const amount = Number(r.amount) || 0
        const cost = Number(r.cost_amount) || 0
        const pnl = Number(r.holding_pnl) || (amount - cost)
        const pnlPct = Number(r.holding_pnl_pct) || (cost > 0 ? (pnl / cost) * 100 : 0)
        const code = (r.fund_code || '').trim()
        return {
          ...r,
          source: source.value,
          shares: Number(r.shares) || 0,
          amount,
          cost_amount: cost,
          holding_pnl: pnl,
          holding_pnl_pct: pnlPct,
          _pnl: pnl,
          _pnlRatio: pnlPct,
          _duplicate: existingCodes.value.has(code),
        }
      })

    if (editableResults.value.length === 0) {
      if (ocrErrors.value.length > 0) {
        ElMessage.error(`识别失败：${ocrErrors.value[0]}`)
      } else {
        ElMessage.warning('未识别到有效的基金信息')
      }
    } else {
      const dupes = editableResults.value.filter(r => r._duplicate).length
      let msg = `识别到 ${editableResults.value.length} 条持仓`
      if (dupes > 0) msg += `（${dupes} 只与现有持仓重复，将合并）`
      ElMessage.success(msg)
      step.value = 2
    }
  } catch (e: any) {
    ElMessage.error('识别失败: ' + (e.message || '未知错误'))
  } finally {
    recognizing.value = false
  }
}

async function handleConfirm() {
  const validItems = editableResults.value.filter(r => r.fund_code)
  if (validItems.length === 0) {
    ElMessage.warning('没有可导入的有效数据，请补充基金代码')
    return
  }

  confirming.value = true
  try {
    const res = await confirmOcr(validItems) as any
    ElMessage.success(res.message || `成功导入 ${validItems.length} 只基金`)
    ocrResults.value = []
    editableResults.value = []
    ocrErrors.value = []
    fileList.value = []
    step.value = 1
  } catch (e: any) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail?.[0]?.msg || e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
.ocr-import { max-width: var(--content-max-width); }

.page-head { margin-bottom: 24px; }
.page-head h2 { margin: 0 0 4px; font-size: 24px; font-weight: 700; }
.page-head p { margin: 0; color: var(--gray-500); font-size: 14px; }

/* 步骤指示器 */
.steps-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 28px;
  padding: 16px 0;
}
.step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-400);
  font-size: 14px;
}
.step.active { color: var(--brand-600); font-weight: 600; }
.step.done { color: var(--success-500); }
.step-num {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  border: 2px solid currentColor;
}
.step.active .step-num { background: var(--brand-600); color: #fff; border-color: var(--brand-600); }
.step.done .step-num { background: var(--success-500); color: #fff; border-color: var(--success-500); }
.step-line {
  width: 80px; height: 2px;
  background: var(--gray-200);
  margin: 0 12px;
}
.step-line.done { background: var(--success-400); }

/* 概览卡片 */
.import-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.summary-card {
  background: #fff;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg);
  padding: 14px 18px;
}
.summary-card span { font-size: 12px; color: var(--gray-400); display: block; }
.summary-card strong { font-size: 20px; font-weight: 700; color: var(--gray-900); margin-top: 4px; display: block; }
.summary-card .up { color: var(--danger-500); }
.summary-card .down { color: var(--success-500); }

/* 确认页面 */
.confirm-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.confirm-stat {
  text-align: center;
  padding: 16px;
}
.confirm-stat span { font-size: 13px; color: var(--gray-400); display: block; margin-bottom: 8px; }
.confirm-stat strong { font-size: 24px; font-weight: 700; display: block; }
.confirm-stat .up { color: var(--danger-500); }
.confirm-stat .down { color: var(--success-500); }
</style>
