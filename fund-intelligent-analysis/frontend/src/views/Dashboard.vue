<template>
  <div class="dashboard">
    <div class="topbar">
      <div>
        <div class="eyebrow">PRIVATE FUND COMMAND CENTER</div>
        <h1>私人基金工作台</h1>
        <div class="updated-at">更新于 {{ command.updated_at || '-' }}</div>
      </div>
      <div class="toolbar">
        <el-button :loading="refreshing" @click="refreshAll">刷新</el-button>
        <el-button type="primary" :loading="generating" @click="generateCloseAdvice">
          <el-icon><MagicStick /></el-icon>
          生成尾盘建议
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="metric-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="metric clickable-card" role="button" tabindex="0" @click="go('/holdings')" @keydown.enter="go('/holdings')">
          <span>总资产</span>
          <strong>¥{{ money(portfolio.total_value) }}</strong>
          <em>{{ portfolio.holding_count || 0 }} 只持仓</em>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="metric clickable-card" role="button" tabindex="0" @click="go('/holdings')" @keydown.enter="go('/holdings')">
          <span>总盈亏</span>
          <strong :class="profitClass(portfolio.total_pnl)">
            {{ signedMoney(portfolio.total_pnl) }}
          </strong>
          <em :class="profitClass(portfolio.total_pnl_ratio)">
            {{ signedPercent(portfolio.total_pnl_ratio) }}
          </em>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="metric clickable-card" role="button" tabindex="0" @click="go('/holdings')" @keydown.enter="go('/holdings')">
          <span>最大单仓</span>
          <strong>{{ percent(portfolio.top_weight) }}</strong>
          <em>集中度监控</em>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="metric clickable-card" role="button" tabindex="0" @click="go('/market')" @keydown.enter="go('/market')">
          <span>数据状态</span>
          <strong>{{ freshnessLabel }}</strong>
          <em>新闻 {{ command.data_freshness?.recent_news_count || 0 }} 条</em>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="main-grid">
      <el-col :xs="24" :lg="15">
        <section class="panel advice-panel">
          <div class="panel-head">
            <div>
              <h2>{{ advicePanelTitle }}</h2>
              <p>{{ adviceSubtitle }}</p>
            </div>
            <div class="tag-group" v-if="latestAdvice">
              <el-tag :type="marketViewType(latestAdvice.market_view)" effect="dark">
                {{ marketViewLabel(latestAdvice.market_view) }}
              </el-tag>
              <el-tag :type="riskType(latestAdvice.risk_level)">
                风险{{ riskLabel(latestAdvice.risk_level) }}
              </el-tag>
            </div>
          </div>

          <div v-if="latestAdvice" class="advice-body">
            <div class="advice-summary clickable-card" role="button" tabindex="0" @click="go('/ai-analyst')" @keydown.enter="go('/ai-analyst')">
              {{ displayText(latestAdvice.overall_suggestion || latestAdvice.reasoning || '暂无总体建议') }}
            </div>
            <div class="action-strip">
              <div>
                <span>加仓</span>
                <strong class="up">{{ command.action_counts?.add || 0 }}</strong>
              </div>
              <div>
                <span>减仓</span>
                <strong class="down">{{ command.action_counts?.reduce || 0 }}</strong>
              </div>
              <div>
                <span>持有</span>
                <strong>{{ command.action_counts?.hold || 0 }}</strong>
              </div>
            </div>
            <el-table
              :data="latestAdvice.actions || []"
              height="300"
              stripe
              :row-class-name="clickableRowClass"
              @row-click="goAdviceFund"
            >
              <el-table-column prop="fund_code" label="代码" width="92" />
              <el-table-column prop="fund_name" label="基金" min-width="180" show-overflow-tooltip />
              <el-table-column label="动作" width="92">
                <template #default="{ row }">
                  <el-tag :type="actionType(row.action)" size="small">
                    {{ actionLabel(row.action) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="比例" width="80">
                <template #default="{ row }">{{ percent((row.suggested_ratio || 0) * 100) }}</template>
              </el-table-column>
              <el-table-column label="置信度" width="100">
                <template #default="{ row }">{{ percent((row.confidence || 0) * 100) }}</template>
              </el-table-column>
              <el-table-column label="理由" min-width="240" show-overflow-tooltip>
                <template #default="{ row }">{{ displayText(row.reason) }}</template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="暂无AI建议，可立即生成" />
        </section>
      </el-col>

      <el-col :xs="24" :lg="9">
        <section class="panel">
          <div class="panel-head compact">
            <h2>风险雷达</h2>
          </div>
          <div class="risk-list">
            <div
              v-for="item in command.risk_flags || []"
              :key="item.title"
              class="risk-item clickable-card"
              :class="item.level"
              role="button"
              tabindex="0"
              @click="goRisk(item)"
              @keydown.enter="goRisk(item)"
            >
              <div>
                <strong>{{ item.title }}</strong>
                <span>{{ item.detail }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="panel freshness">
          <div class="panel-head compact">
            <h2>数据新鲜度</h2>
          </div>
          <div class="fresh-grid">
            <div class="clickable-card" role="button" tabindex="0" @click="go('/market')" @keydown.enter="go('/market')">
              <span>指数</span>
              <strong>{{ command.data_freshness?.latest_index_time || '暂无' }}</strong>
            </div>
            <div class="clickable-card" role="button" tabindex="0" @click="go('/holdings')" @keydown.enter="go('/holdings')">
              <span>估值</span>
              <strong>{{ command.data_freshness?.latest_fund_estimate_time || '暂无' }}</strong>
            </div>
            <div class="clickable-card" role="button" tabindex="0" @click="go('/news')" @keydown.enter="go('/news')">
              <span>新闻</span>
              <strong>{{ command.data_freshness?.recent_news_count || 0 }} 条</strong>
            </div>
          </div>
        </section>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <section class="panel">
          <div class="panel-head compact">
            <h2>核心持仓</h2>
            <el-button text @click="$router.push('/holdings')">查看全部</el-button>
          </div>
          <el-table
            :data="command.top_positions || []"
            height="340"
            stripe
            :row-class-name="clickableRowClass"
            @row-click="goPositionFund"
          >
            <el-table-column prop="fund_code" label="代码" width="92" />
            <el-table-column prop="fund_name" label="基金" min-width="180" show-overflow-tooltip />
            <el-table-column label="市值" width="118">
              <template #default="{ row }">¥{{ money(row.current_value) }}</template>
            </el-table-column>
            <el-table-column label="占比" width="82">
              <template #default="{ row }">{{ percent(row.weight) }}</template>
            </el-table-column>
            <el-table-column label="盈亏" width="108">
              <template #default="{ row }">
                <span :class="profitClass(row.pnl_amount)">{{ signedMoney(row.pnl_amount) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-col>

      <el-col :xs="24" :lg="12">
        <section class="panel clickable-card" role="button" tabindex="0" @click="go('/holdings')" @keydown.enter="go('/holdings')">
          <div class="panel-head compact">
            <h2>资产配置</h2>
          </div>
          <v-chart :option="allocationOption" class="chart" autoresize />
        </section>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getAssetAllocation, getCommandCenter, generateAdvice } from '../api'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const router = useRouter()
const command = ref<any>({})
const allocation = ref<any[]>([])
const refreshing = ref(false)
const generating = ref(false)

const portfolio = computed(() => command.value.portfolio || {})
const latestAdvice = computed(() => command.value.latest_advice)
const freshnessLabel = computed(() => command.value.data_freshness?.latest_fund_estimate_time ? '已更新' : '待刷新')
const adviceSubtitle = computed(() => latestAdvice.value ? `${latestAdvice.value.advice_date} ${latestAdvice.value.advice_time || ''}` : '收盘前最后半小时生成，建议前自动刷新行情和新闻')
const advicePanelTitle = computed(() => latestAdvice.value?.data_quality?.is_trading_day === false ? '休市期间复盘建议' : '尾盘建议')
const isRestContext = computed(() => latestAdvice.value?.data_quality?.is_trading_day === false || command.value.data_freshness?.is_trading_day === false)

const allocationOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
  legend: { bottom: 0 },
  color: ['#2f6fef', '#e85d75', '#31a57b', '#f2a23a', '#7b61ff', '#5b6472'],
  series: [{
    type: 'pie',
    radius: ['48%', '72%'],
    center: ['50%', '45%'],
    label: { formatter: '{b}\n{d}%' },
    data: allocation.value.length ? allocation.value.map(a => ({ name: a.type, value: a.value })) : [{ name: '暂无数据', value: 1 }],
  }],
}))

function money(val: any) {
  const n = Number(val) || 0
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function signedMoney(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : '-'}¥${money(Math.abs(n))}`
}

function percent(val: any) {
  const n = Number(val) || 0
  return `${n.toFixed(2)}%`
}

function signedPercent(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

function profitClass(val: any) {
  return Number(val) >= 0 ? 'up' : 'down'
}

function marketViewLabel(view: string) {
  if (view === 'bullish') return '看多'
  if (view === 'bearish') return '看空'
  return '中性'
}

function marketViewType(view: string) {
  if (view === 'bullish') return 'danger'
  if (view === 'bearish') return 'success'
  return 'info'
}

function riskLabel(risk: string) {
  if (risk === 'high') return '高'
  if (risk === 'low') return '低'
  return '中'
}

function riskType(risk: string) {
  if (risk === 'high') return 'danger'
  if (risk === 'low') return 'success'
  return 'warning'
}

function actionLabel(action: string) {
  if (action === 'add') return '加仓'
  if (action === 'reduce') return '减仓'
  return '持有'
}

function actionType(action: string) {
  if (action === 'add') return 'danger'
  if (action === 'reduce') return 'success'
  return 'info'
}

function displayText(value: any) {
  const text = String(value || '')
  if (!isRestContext.value) return text
  return text
    .replaceAll('今日尾盘', '休市期间')
    .replaceAll('今日主力', '最近交易日主力')
    .replaceAll('今日资金', '最近交易日资金')
    .replaceAll('今日行情', '最近交易日行情')
    .replaceAll('今日涨跌', '最近交易日涨跌')
    .replaceAll('今日', '最近交易日')
    .replaceAll('当天', '最近交易日')
}

function go(path: string) {
  router.push(path)
}

function goFund(code: any) {
  const fundCode = String(code || '').trim()
  if (!fundCode) return
  router.push(`/fund/${encodeURIComponent(fundCode)}`)
}

function goAdviceFund(row: any) {
  goFund(row?.fund_code)
}

function goPositionFund(row: any) {
  goFund(row?.fund_code)
}

function goRisk(item: any) {
  const text = `${item?.title || ''} ${item?.detail || ''}`
  if (/AI|建议|模型|复盘/.test(text)) {
    go('/ai-analyst')
    return
  }
  go('/holdings')
}

function clickableRowClass() {
  return 'clickable-row'
}

async function loadData() {
  refreshing.value = true
  try {
    const [cmd, alloc] = await Promise.all([getCommandCenter(), getAssetAllocation()])
    command.value = cmd as any
    allocation.value = (alloc as any[]) || []
  } catch (e) {
    ElMessage.error('工作台数据加载失败')
  } finally {
    refreshing.value = false
  }
}

async function refreshAll() {
  await loadData()
}

async function generateCloseAdvice() {
  generating.value = true
  try {
    const res = await generateAdvice() as any
    if (res.error) {
      ElMessage.error(res.error)
    } else {
      ElMessage.success('尾盘建议已生成')
      await loadData()
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.dashboard {
  color: #1f2937;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.eyebrow {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.updated-at {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

h1 {
  margin: 4px 0 0;
  font-size: 28px;
}

h2 {
  margin: 0;
  font-size: 18px;
}

.toolbar {
  display: flex;
  gap: 8px;
}

.metric-row {
  margin-bottom: 16px;
}

.metric {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  min-height: 108px;
}

.metric span,
.metric em {
  display: block;
  color: #64748b;
  font-size: 13px;
  font-style: normal;
}

.metric strong {
  display: block;
  margin: 10px 0 6px;
  font-size: 26px;
  color: #111827;
}

.main-grid {
  margin-bottom: 16px;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.panel-head.compact {
  align-items: center;
}

.panel-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.tag-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.advice-summary {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  color: #334155;
  line-height: 1.7;
  margin-bottom: 12px;
}

.action-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.action-strip div {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
}

.action-strip span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.action-strip strong {
  display: block;
  margin-top: 4px;
  font-size: 24px;
}

.risk-list {
  display: grid;
  gap: 10px;
}

.risk-item {
  border: 1px solid #e5e7eb;
  border-left: 4px solid #64748b;
  border-radius: 8px;
  padding: 12px;
}

.risk-item.high {
  border-left-color: #e85d75;
}

.risk-item.medium {
  border-left-color: #f2a23a;
}

.risk-item.low {
  border-left-color: #31a57b;
}

.risk-item strong,
.risk-item span {
  display: block;
}

.risk-item span {
  color: #64748b;
  margin-top: 4px;
  font-size: 13px;
}

.fresh-grid {
  display: grid;
  gap: 10px;
}

.fresh-grid div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #eef2f7;
}

.fresh-grid span {
  color: #64748b;
}

.chart {
  height: 340px;
}

.up {
  color: #d94b64 !important;
}

.down {
  color: #259b72 !important;
}

.clickable-card {
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

.clickable-card:hover {
  border-color: rgba(47, 111, 239, 0.42);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.clickable-card:focus-visible {
  outline: 2px solid #2f6fef;
  outline-offset: 2px;
}

:deep(.clickable-row) {
  cursor: pointer;
}

:deep(.clickable-row:hover td.el-table__cell) {
  background: #eef4ff !important;
}

@media (max-width: 900px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .toolbar {
    flex-wrap: wrap;
    width: 100%;
  }

  .toolbar .el-button {
    flex: 1 1 148px;
    margin-left: 0;
  }

  h1 {
    font-size: 24px;
  }

  .metric {
    min-height: auto;
  }

  .panel-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .panel-head.compact {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .tag-group {
    justify-content: flex-start;
  }

  .chart {
    height: 300px;
  }
}

@media (max-width: 560px) {
  .dashboard {
    min-width: 0;
  }

  .panel,
  .metric {
    padding: 12px;
  }

  .metric strong {
    font-size: 22px;
  }

  .action-strip {
    grid-template-columns: 1fr;
  }

  .fresh-grid div {
    align-items: flex-start;
    flex-direction: column;
  }

  .chart {
    height: 260px;
  }
}
</style>
