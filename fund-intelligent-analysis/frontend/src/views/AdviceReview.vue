<template>
  <div>
    <div class="page-head">
      <div>
        <h2>AI 建议复盘</h2>
        <p>跟踪验证 AI 建议的准确性，积累数据优化决策</p>
      </div>
      <div class="head-actions">
        <el-button :loading="batching" @click="handleBatchReview">批量复盘</el-button>
        <el-select v-model="statsDays" style="width: 120px; margin-left: 8px;" @change="loadStats">
          <el-option :value="30" label="近30天" />
          <el-option :value="90" label="近90天" />
          <el-option :value="180" label="近半年" />
          <el-option :value="365" label="近一年" />
        </el-select>
      </div>
    </div>

    <!-- 免责声明 -->
    <el-alert
      title="复盘结果仅供验证 AI 分析框架的有效性，不构成对未来的预测。投资有风险，决策需独立判断。"
      type="info" show-icon :closable="false" style="margin-bottom: 20px;"
    />

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px;" v-if="stats.total">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">建议总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">命中率</div>
          <div class="stat-value" style="color: #67c23a;">{{ stats.hit_rate }}%</div>
          <div class="stat-sub">{{ stats.hits }} 命中</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">有效命中率</div>
          <div class="stat-value" style="color: #409eff;">{{ stats.effective_rate }}%</div>
          <div class="stat-sub">半命中算50%</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">平均评分</div>
          <div class="stat-value" :style="{ color: stats.avg_hit_score >= 60 ? '#67c23a' : '#e6a23c' }">
            {{ stats.avg_hit_score }}
          </div>
          <div class="stat-sub">/100</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 细分统计 -->
    <el-row :gutter="16" style="margin-bottom: 20px;" v-if="stats.by_market_view">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold;">按市场观点</span></template>
          <el-table :data="viewStatsRows" size="small" stripe>
            <el-table-column prop="label" label="观点" width="80" />
            <el-table-column prop="total" label="次数" width="60" />
            <el-table-column prop="hit_rate" label="命中率" width="100">
              <template #default="{ row }">
                <el-progress :percentage="row.hit_rate" :stroke-width="8" :color="row.hit_rate >= 60 ? '#67c23a' : '#e6a23c'" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" v-if="stats.by_confidence">
          <template #header><span style="font-weight: bold;">按置信度</span></template>
          <div style="display: flex; gap: 16px; justify-content: space-around; padding: 12px 0;">
            <div style="text-align: center;">
              <div style="font-size: 12px; color: var(--gray-400);">高置信度(≥65%)</div>
              <div style="font-size: 24px; font-weight: 700; color: #409eff; margin: 8px 0;">
                {{ stats.by_confidence.high_confidence_hit_rate }}%
              </div>
              <div style="font-size: 12px; color: var(--gray-400);">{{ stats.by_confidence.high_confidence_total }} 条</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 12px; color: var(--gray-400);">低置信度(&lt;65%)</div>
              <div style="font-size: 24px; font-weight: 700; color: #e6a23c; margin: 8px 0;">
                {{ stats.by_confidence.low_confidence_hit_rate }}%
              </div>
              <div style="font-size: 12px; color: var(--gray-400);">{{ stats.by_confidence.low_confidence_total }} 条</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 无数据提示 -->
    <el-card v-if="!stats.total && !loading" shadow="hover" style="text-align: center; padding: 40px;">
      <el-icon :size="48" color="#c0c4cc"><DataAnalysis /></el-icon>
      <div style="margin-top: 16px; color: #909399;">暂无复盘数据</div>
      <div style="color: #c0c4cc; font-size: 13px; margin-top: 4px;">
        复盘需要 AI 建议生成至少 1 天后才能分析。建议生成当天建议后，次日再来看复盘结果。
      </div>
    </el-card>

    <!-- 复盘列表 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header><span style="font-weight: bold;">复盘记录</span></template>
      <el-table :data="reviews" stripe v-loading="loading">
        <el-table-column label="建议日期" width="110">
          <template #default="{ row }">{{ row.advice_date }}</template>
        </el-table-column>
        <el-table-column label="市场观点" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="viewTagType(row.market_view)">{{ viewLabel(row.market_view) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建议动作" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.suggested_action" size="small" :type="actionTagType(row.suggested_action)">
              {{ actionLabel(row.suggested_action) }}
            </el-tag>
            <span v-else style="color: var(--gray-400);">-</span>
          </template>
        </el-table-column>
        <el-table-column label="次日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="(row.next_day_return || 0) >= 0 ? 'text-up' : 'text-down'">
              {{ (row.next_day_return || 0) >= 0 ? '+' : '' }}{{ row.next_day_return?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="3日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="(row.three_day_return || 0) >= 0 ? 'text-up' : 'text-down'">
              {{ (row.three_day_return || 0) >= 0 ? '+' : '' }}{{ row.three_day_return?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="5日收益" width="100" align="right">
          <template #default="{ row }">
            <span :class="(row.five_day_return || 0) >= 0 ? 'text-up' : 'text-down'">
              {{ (row.five_day_return || 0) >= 0 ? '+' : '' }}{{ row.five_day_return?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="命中结果" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="hitTagType(row.hit_result)" size="small" effect="dark">
              {{ hitLabel(row.hit_result) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="70" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.hit_score >= 60 ? '#67c23a' : '#e6a23c', fontWeight: '700' }">
              {{ row.hit_score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="复盘概要" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.review_summary }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 16px; display: flex; justify-content: center;">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="loadReviews"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="复盘详情" width="650px">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="建议日期">{{ detailRow.advice_date }}</el-descriptions-item>
        <el-descriptions-item label="市场观点">{{ viewLabel(detailRow.market_view) }}</el-descriptions-item>
        <el-descriptions-item label="建议动作">{{ actionLabel(detailRow.suggested_action) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="命中结果">
          <el-tag :type="hitTagType(detailRow.hit_result)" size="small">{{ hitLabel(detailRow.hit_result) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="次日组合收益">{{ (detailRow.next_day_return || 0) >= 0 ? '+' : '' }}{{ detailRow.next_day_return?.toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="次日沪深300">{{ (detailRow.next_day_market_return || 0) >= 0 ? '+' : '' }}{{ detailRow.next_day_market_return?.toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="3日组合收益">{{ (detailRow.three_day_return || 0) >= 0 ? '+' : '' }}{{ detailRow.three_day_return?.toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="3日沪深300">{{ (detailRow.three_day_market_return || 0) >= 0 ? '+' : '' }}{{ detailRow.three_day_market_return?.toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="5日组合收益">{{ (detailRow.five_day_return || 0) >= 0 ? '+' : '' }}{{ detailRow.five_day_return?.toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="5日沪深300">{{ (detailRow.five_day_market_return || 0) >= 0 ? '+' : '' }}{{ detailRow.five_day_market_return?.toFixed(2) }}%</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 16px; line-height: 1.7;">
        <div style="font-weight: bold; margin-bottom: 4px;">复盘总结</div>
        <div style="color: #606266;">{{ detailRow.review_summary || '-' }}</div>
      </div>
      <div v-if="detailRow.error_reason" style="margin-top: 12px; padding: 10px; background: #fef0f0; border-radius: 6px; line-height: 1.7;">
        <div style="font-weight: bold; color: #b26a00; margin-bottom: 4px;">偏差原因</div>
        <div style="color: #b26a00; font-size: 13px;">{{ detailRow.error_reason }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api/request'

const loading = ref(false)
const batching = ref(false)
const statsDays = ref(90)
const stats = ref<any>({})
const reviews = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailVisible = ref(false)
const detailRow = ref<any>({})

const viewStatsRows = computed(() => {
  const vm = stats.value.by_market_view || {}
  return [
    { label: '看多', ...(vm.bullish || {}), hit_rate: vm.bullish?.hit_rate || 0, total: vm.bullish?.total || 0 },
    { label: '看空', ...(vm.bearish || {}), hit_rate: vm.bearish?.hit_rate || 0, total: vm.bearish?.total || 0 },
    { label: '中性', ...(vm.neutral || {}), hit_rate: vm.neutral?.hit_rate || 0, total: vm.neutral?.total || 0 },
  ].filter(r => r.total > 0)
})

// label helpers
function viewLabel(v: string) {
  if (v === 'bullish') return '看多'
  if (v === 'bearish') return '看空'
  return '中性'
}
function viewTagType(v: string) {
  if (v === 'bullish') return 'danger'
  if (v === 'bearish') return 'success'
  return 'info'
}
function actionLabel(a: string) {
  const m: Record<string,string> = { add:'加仓', reduce:'减仓', hold:'持有', gradual_buy:'分批低吸', stop_profit:'止盈' }
  return m[a] || a
}
function actionTagType(a: string) {
  if (a === 'add' || a === 'gradual_buy') return 'danger'
  if (a === 'reduce' || a === 'stop_profit') return 'success'
  return 'info'
}
function hitLabel(h: string) {
  const m: Record<string,string> = { hit:'✓ 命中', miss:'✗ 未命中', partial:'△ 部分', pending:'⏳ 待复盘' }
  return m[h] || h
}
function hitTagType(h: string) {
  if (h === 'hit') return 'success'
  if (h === 'miss') return 'danger'
  if (h === 'partial') return 'warning'
  return 'info'
}

async function loadStats() {
  try {
    const res = await request.get('/ai/review/stats', { params: { days: statsDays.value } }) as any
    stats.value = res
  } catch { /* empty */ }
}

async function loadReviews() {
  loading.value = true
  try {
    const res = await request.get('/ai/review/list', { params: { page: page.value, page_size: pageSize.value } }) as any
    reviews.value = res.items || []
    total.value = res.total || 0
  } catch { /* empty */ }
  finally { loading.value = false }
}

async function handleBatchReview() {
  batching.value = true
  try {
    const res = await request.post('/ai/review/batch') as any
    ElMessage.success(`复盘完成：新增 ${res.reviewed} 条，跳过 ${res.skipped} 条`)
    await Promise.all([loadStats(), loadReviews()])
  } catch (e: any) {
    ElMessage.error('批量复盘失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    batching.value = false
  }
}

function viewDetail(row: any) {
  detailRow.value = row
  detailVisible.value = true
}

onMounted(async () => {
  await Promise.all([loadStats(), loadReviews()])
})
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-head h2 { margin: 0; }
.page-head p { margin: 4px 0 0; color: var(--gray-400); font-size: 13px; }
.head-actions { display: flex; gap: 8px; align-items: center; }

.stat-card { text-align: center; }
.stat-label { font-size: 11px; color: var(--gray-400); text-transform: uppercase; }
.stat-value { font-size: 28px; font-weight: 700; color: var(--gray-900); margin: 8px 0; }
.stat-sub { font-size: 12px; color: var(--gray-400); }

.text-up { color: var(--danger-500); font-weight: 600; }
.text-down { color: var(--success-500); font-weight: 600; }
</style>
