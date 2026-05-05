<template>
  <div class="ocr-import">
    <el-tabs v-model="activeTab" type="card">
      <!-- Tab 1: 一键导入持仓 -->
      <el-tab-pane label="一键导入持仓" name="holdings">
        <el-card shadow="hover" style="margin-bottom: 20px;">
          <el-form :inline="true">
            <el-form-item label="截图来源">
              <el-radio-group v-model="source">
                <el-radio value="alipay">支付宝</el-radio>
                <el-radio value="tiantian">同花顺</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleFileChange"
            accept="image/*"
            multiple
            drag
            :limit="10"
          >
            <el-icon :size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <div style="margin-top: 8px;">拖拽或点击上传截图（支持多张分页截图）</div>
            <template #tip>
              <div style="color: #909399; font-size: 12px;">
                支持 PNG/JPG 格式，从{{ source === 'alipay' ? '支付宝' : '同花顺' }}APP持仓页面截图
              </div>
            </template>
          </el-upload>

          <div style="margin-top: 16px; text-align: center;">
            <el-button type="primary" :loading="recognizing" :disabled="fileList.length === 0" @click="handleRecognize">
              <el-icon><Camera /></el-icon> 开始识别
            </el-button>
          </div>
        </el-card>

        <!-- 持仓识别结果 -->
        <el-card v-if="ocrResults.length > 0" shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: bold;">识别结果预览（可编辑修正）</span>
              <el-button type="primary" :loading="confirming" @click="handleConfirm">
                确认导入
              </el-button>
            </div>
          </template>

          <el-table :data="editableResults" stripe style="width: 100%;">
            <el-table-column label="基金代码" width="120">
              <template #default="{ row }">
                <el-input v-model="row.fund_code" size="small" placeholder="6位代码" maxlength="6" />
              </template>
            </el-table-column>
            <el-table-column label="基金名称" min-width="180">
              <template #default="{ row }">
                <el-input v-model="row.fund_name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="份额" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.shares" size="small" :min="0" :precision="2" style="width: 100%;" />
              </template>
            </el-table-column>
            <el-table-column label="市值/金额" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.amount" size="small" :min="0" :precision="2" style="width: 100%;" />
              </template>
            </el-table-column>
            <el-table-column label="成本金额" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.cost_amount" size="small" :min="0" :precision="2" style="width: 100%;" />
              </template>
            </el-table-column>
            <el-table-column label="持有收益" width="110">
              <template #default="{ row }">
                <span :style="{ color: (row.holding_pnl || 0) >= 0 ? '#67C23A' : '#F56C6C', fontWeight: 'bold' }">
                  {{ row.holding_pnl ? (row.holding_pnl >= 0 ? '+' : '') + Number(row.holding_pnl).toFixed(2) : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="收益率" width="90">
              <template #default="{ row }">
                <span :style="{ color: (row.holding_pnl_pct || 0) >= 0 ? '#67C23A' : '#F56C6C', fontWeight: 'bold' }">
                  {{ row.holding_pnl_pct ? (row.holding_pnl_pct >= 0 ? '+' : '') + Number(row.holding_pnl_pct).toFixed(2) + '%' : '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备注" width="160">
              <template #default="{ row }">
                <span style="color: #909399; font-size: 12px;">{{ row.note || row.error || '' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button size="small" type="danger" @click="editableResults.splice($index, 1)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: 一键导入加减仓 -->
      <el-tab-pane label="一键导入加减仓" name="trades">
        <el-card shadow="hover" style="margin-bottom: 20px;">
          <el-upload
            ref="tradeUploadRef"
            :auto-upload="false"
            :on-change="handleTradeFileChange"
            accept="image/*"
            multiple
            drag
            :limit="10"
          >
            <el-icon :size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <div style="margin-top: 8px;">拖拽或点击上传截图（支持多张分页截图）</div>
            <template #tip>
              <div style="color: #909399; font-size: 12px;">
                请上传同花顺APP的交易记录页面截图
              </div>
            </template>
          </el-upload>

          <div style="margin-top: 16px; text-align: center;">
            <el-button type="primary" :loading="tradeRecognizing" :disabled="tradeFileList.length === 0" @click="handleTradeRecognize">
              <el-icon><Camera /></el-icon> 开始识别
            </el-button>
          </div>
        </el-card>

        <!-- 交易识别结果 -->
        <el-card v-if="tradeResults.length > 0" shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: bold;">识别结果预览（可编辑修正）</span>
              <el-button type="primary" :loading="tradeConfirming" @click="handleTradeConfirm">
                确认导入 ({{ tradeSelectedCount }}条)
              </el-button>
            </div>
          </template>

          <el-table
            :data="tradeResults"
            stripe
            style="width: 100%;"
            :row-class-name="tradeRowClassName"
          >
            <el-table-column label="" width="50">
              <template #header>
                <el-checkbox v-model="tradeSelectAll" @change="handleTradeSelectAll" />
              </template>
              <template #default="{ row }">
                <el-checkbox v-model="row.selected" />
              </template>
            </el-table-column>
            <el-table-column label="交易类型" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.trade_type === '买入'" type="success" size="small">买入</el-tag>
                <el-tag v-else-if="row.trade_type === '卖出'" type="danger" size="small">卖出</el-tag>
                <span v-else>{{ row.trade_type || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="基金名称" min-width="160">
              <template #default="{ row }">
                <el-input v-model="row.fund_name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="基金代码" width="110">
              <template #default="{ row }">
                <el-input v-model="row.fund_code" size="small" placeholder="6位代码" maxlength="6" />
              </template>
            </el-table-column>
            <el-table-column label="金额(元)" width="130">
              <template #default="{ row }">
                <el-input-number v-model="row.amount" size="small" :min="0" :precision="2" style="width: 100%;" />
              </template>
            </el-table-column>
            <el-table-column label="份额(份)" width="130">
              <template #default="{ row }">
                <el-input-number v-model="row.shares" size="small" :min="0" :precision="2" style="width: 100%;" />
              </template>
            </el-table-column>
            <el-table-column label="交易日期" width="120">
              <template #default="{ row }">
                <el-date-picker
                  v-model="row.trade_date"
                  type="date"
                  size="small"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  style="width: 100%;"
                />
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <span :style="{ color: row.status && row.status.includes('撤') ? '#F56C6C' : '' }">
                  {{ row.status || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备注" width="120">
              <template #default="{ row }">
                <span style="color: #909399; font-size: 12px;">{{ row.note || '' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70">
              <template #default="{ $index }">
                <el-button size="small" type="danger" @click="tradeResults.splice($index, 1)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { uploadOcr, confirmOcr, uploadOcrTrades, confirmOcrTrades } from '../api'

// ============ Tab 切换 ============
const activeTab = ref('holdings')

// ============ Tab 1: 持仓导入 ============
const source = ref('alipay')
const fileList = ref<File[]>([])
const recognizing = ref(false)
const confirming = ref(false)
const ocrResults = ref<any[]>([])
const editableResults = ref<any[]>([])

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    fileList.value.push(file.raw)
  }
}

async function handleRecognize() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先上传截图')
    return
  }

  recognizing.value = true
  try {
    const formData = new FormData()
    fileList.value.forEach(f => formData.append('files', f))

    const res = await uploadOcr(formData, source.value) as any
    ocrResults.value = res.results || []
    editableResults.value = ocrResults.value
      .filter((r: any) => !r.error)
      .map((r: any) => ({
        ...r,
        source: source.value,
        shares: Number(r.shares) || 0,
        amount: Number(r.amount) || 0,
        cost_amount: Number(r.cost_amount) || 0,
        holding_pnl: Number(r.holding_pnl) || 0,
        holding_pnl_pct: Number(r.holding_pnl_pct) || 0,
      }))

    if (editableResults.value.length === 0) {
      const errors = ocrResults.value
        .filter((r: any) => r.error)
        .map((r: any) => r.error)
        .filter(Boolean)
      if (errors.length > 0) {
        ElMessage.error(`识别失败：${errors[0]}`)
      } else {
        ElMessage.warning('未识别到有效的基金信息，请检查截图质量或手动录入')
      }
    } else {
      ElMessage.success(`识别到 ${editableResults.value.length} 条持仓信息`)
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
    ElMessage.success(res.message || '导入成功')
    ocrResults.value = []
    editableResults.value = []
    fileList.value = []
  } catch (e: any) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail?.[0]?.msg || e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    confirming.value = false
  }
}

// ============ Tab 2: 交易记录导入 ============
const tradeFileList = ref<File[]>([])
const tradeRecognizing = ref(false)
const tradeConfirming = ref(false)
const tradeResults = ref<any[]>([])

const tradeSelectedCount = computed(() => tradeResults.value.filter(r => r.selected).length)

const tradeSelectAll = computed({
  get: () => tradeResults.value.length > 0 && tradeResults.value.every(r => r.selected),
  set: () => {},
})

function handleTradeSelectAll(val: boolean) {
  tradeResults.value.forEach(r => { r.selected = val })
}

function tradeRowClassName({ row }: { row: any }) {
  if (row.status && row.status.includes('撤')) return 'trade-row-cancelled'
  return ''
}

function handleTradeFileChange(file: UploadFile) {
  if (file.raw) {
    tradeFileList.value.push(file.raw)
  }
}

async function handleTradeRecognize() {
  if (tradeFileList.value.length === 0) {
    ElMessage.warning('请先上传交易记录截图')
    return
  }
  tradeRecognizing.value = true
  try {
    const formData = new FormData()
    tradeFileList.value.forEach(f => formData.append('files', f))
    const res = await uploadOcrTrades(formData) as any
    tradeResults.value = (res.data?.results || res.results || [])
      .map((r: any) => ({
        ...r,
        selected: !r.status || !r.status.includes('撤'),
        amount: Number(r.amount) || 0,
        shares: Number(r.shares) || 0,
      }))

    if (tradeResults.value.length === 0) {
      ElMessage.warning('未识别到有效的交易记录，请检查截图质量')
    } else {
      ElMessage.success(`识别到 ${tradeResults.value.length} 条交易记录`)
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '识别失败')
  } finally {
    tradeRecognizing.value = false
  }
}

async function handleTradeConfirm() {
  const selectedItems = tradeResults.value.filter(r => r.selected)
  if (selectedItems.length === 0) {
    ElMessage.warning('请至少选择一条交易记录')
    return
  }
  tradeConfirming.value = true
  try {
    const res = await confirmOcrTrades(selectedItems) as any
    const data = res.data || res
    ElMessage.success(data.message || `成功导入 ${data.created?.length || 0} 条交易记录`)

    if (data.skipped?.length > 0) {
      ElMessage.warning(`已跳过 ${data.skipped.length} 条已撤单记录`)
    }
    if (data.errors?.length > 0) {
      ElMessage.error(`${data.errors.length} 条记录导入失败`)
    }

    tradeResults.value = []
    tradeFileList.value = []
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '导入失败')
  } finally {
    tradeConfirming.value = false
  }
}
</script>

<style scoped>
.ocr-import {
  padding: 0;
}

:deep(.trade-row-cancelled) {
  background-color: #f5f5f5 !important;
}

:deep(.trade-row-cancelled td) {
  color: #999 !important;
}
</style>
