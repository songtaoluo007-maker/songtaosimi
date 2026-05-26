<template>
  <div>
    <div class="page-head">
      <div>
        <h2>AI 投资顾问</h2>
        <p>{{ dataQuality.is_trading_day === false ? '休市期间复盘建议' : '结构化持仓分析与操作建议' }}</p>
      </div>
      <div class="head-actions">
        <el-button type="primary" :loading="generating" @click="handleGenerate(false)">
          <el-icon><MagicStick /></el-icon> 立即生成建议
        </el-button>
        <el-button :loading="generating" @click="handleGenerate(true)">刷新数据后生成</el-button>
        <el-button type="success" :loading="pushing" :disabled="!latestAdvice?.actions?.length" @click="handlePushToFeishu">
          <el-icon><Position /></el-icon> 推送到飞书
        </el-button>
        <!-- V2 新增：强制解锁按钮（仅在卡死时显示） -->
        <el-button v-if="canForceReset" type="warning" plain @click="handleForceReset">
          <el-icon><RefreshLeft /></el-icon> 强制解锁
        </el-button>
      </div>
    </div>

    <!-- V2: 进度提示（用真实 step_done/step_total 数字） -->
    <el-alert
      v-if="generationStatus.status === 'running' || generationStatus.status === 'queued'"
      :title="progressTitle"
      type="warning" show-icon :closable="false" style="margin-bottom: 14px;"
    >
      <template #default>
        <div class="progress-row">
          <span class="progress-step">{{ statusMessage }}</span>
          <el-progress
            :percentage="progressPercent"
            :status="progressBarStatus"
            :stroke-width="10"
            style="flex: 1; min-width: 220px;"
          />
          <span class="progress-elapsed">{{ elapsedText }}</span>
        </div>
      </template>
    </el-alert>

    <!-- V2: 生成失败提示 -->
    <el-alert
      v-if="generationStatus.status === 'failed'"
      :title="failureTitle"
      type="error" show-icon :closable="true" style="margin-bottom: 14px;"
      @close="dismissFailure"
    >
      <template #default>
        <p style="margin: 0;">{{ generationStatus.error || generationStatus.message }}</p>
        <p v-if="generationStatus.error === 'missing_today_advice'" style="margin: 6px 0 0;">
          AI 已调用完毕但今日记录写入失败，建议检查数据库可写性与日志，然后点击"刷新数据后生成"重试。
        </p>
      </template>
    </el-alert>

    <el-alert
      title="尾盘建议会在每个交易日 14:30 自动生成。AI 建议仅供个人复盘和决策辅助，不构成收益承诺。"
      type="info" show-icon :closable="false" style="margin-bottom: 20px;"
    />

    <template v-if="hasStructuredAdvice">
      <!-- V2: 离线降级提示（红色大字，比 v1 醒目） -->
      <el-alert
        v-if="isOfflineMode"
        title="⚠️ 离线规则引擎生成的降级建议"
        type="error" show-icon :closable="false" style="margin-bottom: 16px;"
      >
        <template #default>
          <p style="margin: 0;">
            DeepSeek API 当前不可用（{{ latestAdvice.failure_reason || '原因未知' }}），
            本条建议来自本地规则引擎，<strong>仅作降级参考</strong>。请尽快检查网络与 API Key，重新生成获取真实 AI 建议。
          </p>
        </template>
      </el-alert>

      <!-- V2: "今日未生成" 提示（latest advice 不是今天） -->
      <el-alert
        v-if="!isOfflineMode && latestAdvice?.advice_date && latestAdvice.advice_date !== todayStr"
        :title="`当前展示的是 ${latestAdvice.advice_date} 的建议，今日尚未生成`"
        type="info" show-icon :closable="false" style="margin-bottom: 16px;"
      />

      <el-row :gutter="16" style="margin-bottom: 16px;">
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="state-card">
            <div class="state-card-label">市场状态</div>
            <div class="state-card-value">
              <el-tag :type="marketTrendType" size="large" effect="dark">{{ marketTrendLabel }}</el-tag>
            </div>
            <div class="state-card-sub">{{ structured.market_state?.summary || '暂无' }}</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="state-card">
            <div class="state-card-label">组合风险</div>
            <div class="state-card-value">
              <el-tag :type="portfolioRiskType" size="large" effect="dark">{{ portfolioRiskLabel }}</el-tag>
            </div>
            <div class="state-card-sub" v-if="structured.portfolio_risk?.concentration_warning">
              {{ structured.portfolio_risk.concentration_warning }}
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="state-card">
            <div class="state-card-label">建议操作</div>
            <div class="state-card-value">
              <el-tag :type="suggestedActionType" size="large" effect="dark">{{ suggestedActionLabel }}</el-tag>
              <el-tag style="margin-left: 8px;" :type="positionType" size="small">{{ positionLabel }}</el-tag>
            </div>
            <div style="margin-top: 8px; display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 12px; color: var(--gray-400);">置信度</span>
              <el-progress
                :percentage="Math.round((structured.suggested_action?.confidence || 0) * 100)"
                :stroke-width="8" style="flex: 1;" :color="confidenceColor"
              />
            </div>
            <div class="state-card-sub" style="margin-top: 6px;">{{ structured.suggested_action?.reasoning || '' }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="hover" style="margin-bottom: 16px;">
        <template #header><span style="font-weight: bold;">AI 研判摘要</span></template>
        <p style="font-size: 15px; line-height: 1.7; color: var(--gray-900); margin: 0;">
          {{ structured.summary || latestAdvice.overall_suggestion }}
        </p>
        <div v-if="structured.key_reasons?.length" style="margin-top: 14px;">
          <div style="font-weight: bold; font-size: 13px; margin-bottom: 6px; color: var(--gray-600);">核心理由</div>
          <div v-for="(r, i) in structured.key_reasons" :key="i" class="reason-item">
            <span class="reason-num">{{ i + 1 }}</span><span>{{ r }}</span>
          </div>
        </div>
      </el-card>

      <el-card v-if="structured.fund_level_suggestions?.length" shadow="hover" style="margin-bottom: 16px;">
        <template #header><span style="font-weight: bold;">持仓操作建议</span></template>
        <el-table :data="structured.fund_level_suggestions" stripe>
          <el-table-column prop="fund_code" label="代码" width="100" />
          <el-table-column prop="fund_name" label="基金名称" min-width="160" show-overflow-tooltip />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="fundActionType(row.action)" size="small" effect="dark">{{ fundActionLabel(row.action) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="比例调整" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.suggested_ratio_change" :class="Number(row.suggested_ratio_change) > 0 ? 'text-up' : 'text-down'">
                {{ Number(row.suggested_ratio_change) > 0 ? '+' : '' }}{{ (Number(row.suggested_ratio_change) * 100).toFixed(0) }}%
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="90" align="center">
            <template #default="{ row }">
              <el-progress :percentage="Math.round((row.confidence || 0) * 100)" :stroke-width="6" :show-text="true" />
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="理由" min-width="200" show-overflow-tooltip />
        </el-table>
      </el-card>
    </template>

    <el-card v-else shadow="hover" style="margin-bottom: 20px; text-align: center; padding: 40px;">
      <el-icon :size="48" color="#c0c4cc"><MagicStick /></el-icon>
      <div style="margin-top: 16px; color: #909399;">暂无 AI 建议</div>
      <div style="color: #c0c4cc; font-size: 13px; margin-top: 4px;">
        每个交易日 14:30 自动生成，或点击上方按钮手动触发
      </div>
    </el-card>

    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">历史建议</span></template>
      <el-table :data="advices" stripe>
        <el-table-column prop="advice_date" label="日期" width="120" />
        <el-table-column prop="advice_time" label="时间" width="80" />
        <el-table-column label="市场判断" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="marketViewTagType(row.market_view)">{{ marketViewLabel(row.market_view) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="riskTagType(row.risk_level)">{{ riskLabel(row.risk_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="160">
          <template #default="{ row }">
            <el-tag v-if="(row.model_name || '').startsWith('offline:')" type="warning" size="small">离线</el-tag>
            <span v-else>{{ row.model_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="token_usage" label="Token" width="80" />
        <el-table-column label="执行" width="180">
          <template #default="{ row }">
            <template v-if="row.adopted === null">
              <el-button size="small" type="success" plain @click="adopt(row, true)">采纳</el-button>
              <el-button size="small" type="info" plain @click="adopt(row, false)">忽略</el-button>
            </template>
            <el-tag v-else-if="row.adopted === true" type="success" effect="dark">✓ 已采纳</el-tag>
            <el-tag v-else type="info">— 已忽略</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<!--
  AiAdvisor.vue V2 改动：
  1. 进度条用 step_done/step_total 真实数字，不再 +8/+25 假估
  2. 显示已耗时（elapsedText），让用户知道"卡了多久"
  3. 加 "强制解锁" 按钮，对应后端 /api/ai/advice/generate/reset
  4. 离线模式由黄色 warning 升级为红色 error，标注 failure_reason
  5. 加 "今日尚未生成" 横幅（latest.advice_date !== today 时显示）
  6. 加 失败提示 alert，区分 stale_timeout / missing_today_advice 等错误
  7. 轮询间隔 2.5s → 1.5s
  8. generateAdvice 调用超时 10s → 30s
-->
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Position, RefreshLeft } from '@element-plus/icons-vue'
import {
  getAdviceGenerationStatus, getAiAdvices, getLatestAdvice,
  markAdviceRead, sendLatestToFeishu,
} from '../api'
import request from '../api/request'

const latestAdvice = ref<any>({})
const advices = ref<any[]>([])
const generating = ref(false)
const pushing = ref(false)
const generationStatus = ref<any>({ status: 'idle', step: '', message: '', step_done: 0, step_total: 0 })
let pollTimer: ReturnType<typeof setInterval> | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null
const elapsedSeconds = ref(0)
let startedAt = 0

const todayStr = computed(() => new Date().toISOString().slice(0, 10))
const structured = computed(() => latestAdvice.value?.structured || {})
const isOfflineMode = computed(() =>
  latestAdvice.value?.offline_mode ||
  (latestAdvice.value?.model_name || '').startsWith('offline:'),
)
const hasStructuredAdvice = computed(() => {
  const s = structured.value
  return s && !s.parse_error && (s.market_state?.trend || s.summary || s.fund_level_suggestions?.length)
})
const dataQuality = computed(() => latestAdvice.value?.data_quality || {})

// V2: 真实进度计算 — 优先用后端 step_done/step_total，没有时退回小数估算
const progressPercent = computed(() => {
  const s = generationStatus.value
  if (s.step === 'completed') return 100
  if (s.step_total && s.step_total > 0) {
    // 数据刷新阶段：占总进度的 60%
    if (s.step === 'refreshing_data') {
      return Math.round((s.step_done / s.step_total) * 60)
    }
  }
  if (s.step === 'building_context') return 65
  if (s.step === 'calling_ai') return 75
  if (s.step === 'parsing') return 92
  if (s.status === 'queued') return 5
  return 10
})
const progressBarStatus = computed(() => generationStatus.value.status === 'failed' ? 'exception' : '')
const progressTitle = computed(() =>
  generationStatus.value.refresh ? '正在刷新数据后生成 AI 建议' : '正在用当前数据生成 AI 建议',
)
const statusMessage = computed(() => {
  const s = generationStatus.value
  if (s.step === 'queued') return '任务已入队'
  if (s.step === 'refreshing_data') return `刷新数据中 ${s.step_done}/${s.step_total}: ${s.message}`
  if (s.step === 'building_context') return '组装持仓与市场上下文...'
  if (s.step === 'calling_ai') return '正在调用 DeepSeek AI（耗时 15-40s）...'
  if (s.step === 'parsing') return '解析并写入数据库...'
  return s.message || '处理中...'
})
const elapsedText = computed(() => {
  const s = elapsedSeconds.value
  if (!s) return ''
  if (s < 60) return `已耗时 ${s}s`
  return `已耗时 ${Math.floor(s / 60)}m ${s % 60}s`
})
const canForceReset = computed(() => {
  const s = generationStatus.value
  if (s.status !== 'running' && s.status !== 'queued') return false
  return elapsedSeconds.value > 60 // 超过 60s 才显示，避免误触
})
const failureTitle = computed(() => {
  const err = generationStatus.value.error || ''
  if (err === 'stale_timeout') return '任务超时未完成，已自动重置'
  if (err === 'missing_today_advice') return 'AI 已调用但今日记录未生成'
  return 'AI 建议生成失败'
})

const marketTrendLabel = computed(() => marketTrendLabelMap[structured.value.market_state?.trend] || '中性')
const marketTrendType = computed(() => {
  const t = structured.value.market_state?.trend
  if (t === 'bullish') return 'danger'
  if (t === 'bearish') return 'success'
  return 'info'
})
const portfolioRiskLabel = computed(() => riskLevelMap[structured.value.portfolio_risk?.level] || '中')
const portfolioRiskType = computed(() => {
  const l = structured.value.portfolio_risk?.level
  if (l === 'high' || l === 'medium-high') return 'danger'
  if (l === 'medium' || l === 'medium-low') return 'warning'
  return 'success'
})
const suggestedActionLabel = computed(() => actionLabelMap[structured.value.suggested_action?.action] || '观望')
const suggestedActionType = computed(() => {
  const a = structured.value.suggested_action?.action
  if (a === 'add') return 'danger'
  if (a === 'reduce') return 'success'
  return 'info'
})
const positionLabel = computed(() => positionLabelMap[structured.value.suggested_action?.position] || '')
const positionType = computed(() => {
  const p = structured.value.suggested_action?.position
  if (p === 'aggressive') return 'danger'
  if (p === 'defensive') return 'success'
  return 'info'
})
const confidenceColor = computed(() => {
  const c = (structured.value.suggested_action?.confidence || 0) * 100
  if (c >= 70) return '#67c23a'
  if (c >= 50) return '#e6a23c'
  return '#f56c6c'
})

const marketTrendLabelMap: Record<string,string> = { bullish: '看多', bearish: '看空', neutral: '中性' }
const riskLevelMap: Record<string,string> = { low: '低', 'medium-low': '中低', medium: '中', 'medium-high': '中高', high: '高' }
const actionLabelMap: Record<string,string> = { add: '加仓', reduce: '减仓', hold: '持有', gradual_buy: '分批低吸', stop_profit: '止盈' }
const positionLabelMap: Record<string,string> = { aggressive: '积极', neutral: '中性', defensive: '防御' }

function marketViewLabel(view: string) {
  if (view === 'bullish') return '看多'
  if (view === 'bearish') return '看空'
  return '中性'
}
function marketViewTagType(view: string) {
  if (view === 'bullish') return 'danger'
  if (view === 'bearish') return 'success'
  return 'info'
}
function riskLabel(risk: string) { return riskLevelMap[risk] || '中' }
function riskTagType(risk: string) {
  if (risk === 'high' || risk === 'medium-high') return 'danger'
  if (risk === 'low') return 'success'
  return 'warning'
}
function fundActionType(action: string) {
  if (action === 'add' || action === 'gradual_buy') return 'danger'
  if (action === 'reduce' || action === 'stop_profit') return 'success'
  return 'info'
}
function fundActionLabel(action: string) { return actionLabelMap[action] || '持有' }

async function handleGenerate(refresh = false) {
  generating.value = true
  startedAt = Date.now()
  elapsedSeconds.value = 0
  startElapsedTimer()
  try {
    // V2: timeout 改为 30s（v1 是 10s，容易看似失败实际任务还在跑）
    const res = await request.post('/ai/advice/generate-async', {}, {
      params: { refresh },
      timeout: 30000,
    }) as any
    generationStatus.value = res || { status: 'running' }
    if (res?.accepted === false) {
      ElMessage.warning('已有 AI 建议正在生成，页面会继续跟踪进度')
    } else {
      ElMessage.success(refresh ? '已开始刷新数据后生成' : '已开始快速生成')
    }
    startPolling()
  } catch (e: any) {
    generating.value = false
    stopElapsedTimer()
    ElMessage.error('启动生成失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function handleForceReset() {
  try {
    await request.post('/ai/advice/generate/reset')
    generating.value = false
    stopPolling()
    stopElapsedTimer()
    elapsedSeconds.value = 0
    generationStatus.value = { status: 'idle', step: '', message: '' }
    ElMessage.success('已强制解锁，可重新发起生成')
  } catch (e: any) {
    ElMessage.error('解锁失败: ' + (e.response?.data?.detail || e.message))
  }
}

function dismissFailure() {
  generationStatus.value = { status: 'idle', step: '', message: '' }
}

async function handlePushToFeishu() {
  pushing.value = true
  try {
    const res = await sendLatestToFeishu() as any
    if (res.success) ElMessage.success('已推送到飞书')
    else ElMessage.error(res.error || '推送失败')
  } catch (e: any) {
    ElMessage.error('推送失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    pushing.value = false
  }
}

async function adopt(row: any, adopted: boolean) {
  try {
    await request.put(`/ai/advice/${row.id}/adopt`, { adopted, note: '' })
    row.adopted = adopted
    row.adopted_at = new Date().toISOString()
    ElMessage.success(adopted ? '已标记为采纳' : '已标记为忽略')
  } catch {
    ElMessage.error('操作失败')
  }
}

// V2: 轮询频率 2.5s → 1.5s
function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(checkGenerationStatus, 1500)
  checkGenerationStatus()
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}
function startElapsedTimer() {
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - startedAt) / 1000)
  }, 1000)
}
function stopElapsedTimer() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

async function checkGenerationStatus() {
  try {
    const status = await getAdviceGenerationStatus() as any
    generationStatus.value = status
    if (status.status === 'completed') {
      stopPolling()
      stopElapsedTimer()
      generating.value = false
      ElMessage.success('AI 建议生成完成')
      await loadData()
      // V2: 校验拿到的最新建议是不是今天的
      if (latestAdvice.value?.advice_date && latestAdvice.value.advice_date !== todayStr.value) {
        ElMessage.warning('最新建议日期与今天不一致，请刷新页面')
      }
      return
    }
    if (status.status === 'failed') {
      stopPolling()
      stopElapsedTimer()
      generating.value = false
      ElMessage.error(status.error || status.message || 'AI 建议生成失败')
    }
  } catch {
    /* poll silently */
  }
}

async function loadData() {
  try {
    const [latest, list] = await Promise.all([
      getLatestAdvice(),
      getAiAdvices(30),
    ])
    latestAdvice.value = (latest as any).advice || latest
    advices.value = list as any
  } catch { /* page remains usable */ }
}

onMounted(async () => {
  await loadData()
  const status = await getAdviceGenerationStatus() as any
  generationStatus.value = status
  if (status.status === 'running' || status.status === 'queued') {
    generating.value = true
    // 估算已运行时间：如果后端返了 started_at_ts 就用，否则 0
    if (status.started_at_ts) {
      startedAt = status.started_at_ts * 1000
      elapsedSeconds.value = Math.floor((Date.now() - startedAt) / 1000)
    }
    startElapsedTimer()
    startPolling()
  }
})
onBeforeUnmount(() => {
  stopPolling()
  stopElapsedTimer()
})
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-head h2 { margin: 0; }
.page-head p { margin: 4px 0 0; color: var(--gray-400); font-size: 13px; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.progress-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.progress-step { font-weight: 600; color: var(--gray-900); min-width: 200px; }
.progress-elapsed { font-size: 12px; color: var(--gray-500); white-space: nowrap; }
.state-card { text-align: center; }
.state-card-label { font-size: 11px; color: var(--gray-400); text-transform: uppercase; margin-bottom: 8px; }
.state-card-value { margin-bottom: 8px; }
.state-card-sub { font-size: 13px; color: var(--gray-600); line-height: 1.5; }
.reason-item { display: flex; gap: 8px; padding: 6px 0; font-size: 13px; color: var(--gray-700); line-height: 1.5; align-items: baseline; }
.reason-num { flex-shrink: 0; width: 20px; height: 20px; background: var(--brand-500); color: #fff; border-radius: 50%; text-align: center; line-height: 20px; font-size: 11px; font-weight: 700; }
.text-up { color: var(--danger-500); font-weight: 600; }
.text-down { color: var(--success-500); font-weight: 600; }
</style>
