<template>
  <div class="dashboard">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h1>投资工作台</h1>
        <p>更新时间 {{ command.updated_at || '-' }} · {{ marketDateLabel }}</p>
      </div>
      <div class="actions">
        <el-button :icon="Refresh" :loading="refreshing" @click="loadData">刷新</el-button>
        <el-button type="primary" :icon="MagicStick" :loading="generating" @click="generateCloseAdvice">
          生成 AI 建议
        </el-button>
      </div>
    </div>

    <!-- P0.2 基金经理预警横幅 -->
    <el-alert
      v-if="managerAlerts.length > 0"
      type="error"
      :title="`⚠️ 持仓基金经理变更 — 共 ${managerAlerts.length} 起未读`"
      :closable="false"
      show-icon
      style="margin-bottom: 14px;"
    >
      <template #default>
        <div class="manager-alert-row">
          <div v-for="a in managerAlerts.slice(0, 3)" :key="a.id" class="manager-alert-item">
            <strong>{{ a.fund_code }}</strong>
            <span>{{ a.detail }}</span>
            <el-button text size="small" @click="markAlertRead(a.id)">已读</el-button>
          </div>
          <el-button v-if="managerAlerts.length > 3" text size="small" @click="showAllAlerts = true">
            查看全部 {{ managerAlerts.length }} 条
          </el-button>
        </div>
      </template>
    </el-alert>

    <!-- 经理预警详情弹层 -->
    <el-dialog v-model="showAllAlerts" title="基金经理变更预警" width="640px">
      <el-table :data="managerAlerts" stripe height="420">
        <el-table-column prop="fund_code" label="代码" width="100" />
        <el-table-column prop="alert_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="alertTagType(row.severity)" size="small">
              {{ alertTypeLabel(row.alert_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="说明" />
        <el-table-column prop="alert_date" label="日期" width="110" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button text size="small" @click="markAlertRead(row.id)">已读</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 今日故事：Hero 区域 -->
    <div class="today-hero">
      <div class="hero-main">
        <div class="hero-label">今天 {{ marketDateLabel }}</div>
        <div class="hero-big-number" :class="profitClass(portfolio.total_daily_pnl)">
          {{ signedMoney(portfolio.total_daily_pnl) }}
        </div>
        <div class="hero-sub" :class="profitClass(portfolio.total_daily_pnl_ratio)">
          日收益率 {{ signedPercent(portfolio.total_daily_pnl_ratio) }}
        </div>
        <div class="hero-subline">
          年化 XIRR <strong :class="profitClass(portfolio.portfolio_xirr)">{{ signedPercent(portfolio.portfolio_xirr) }}</strong>
          <span>·</span>
          当前回撤 <strong :class="drawdownClass(portfolio.current_drawdown)">{{ drawdownPercent(portfolio.current_drawdown) }}</strong>
        </div>
        <div class="hero-story" v-if="dailyRows.length > 0">
          <template v-if="(portfolio.total_daily_pnl || 0) >= 0">
            主要由 <strong>{{ dailyRows[0]?.fund_name }}</strong> 贡献，{{ dailyRows.length }} 只持仓中 {{ upCount }} 只上涨。
          </template>
          <template v-else>
            主要受 <strong>{{ dailyRows[dailyRows.length-1]?.fund_name }}</strong> 拖累，{{ dailyRows.length }} 只持仓中 {{ downCount }} 只下跌。
          </template>
        </div>
      </div>
      <div class="hero-stats">
        <div class="hero-stat">
          <span>总资产</span>
          <strong>{{ money(portfolio.total_value) }}</strong>
          <small>{{ portfolio.holding_count || 0 }} 只基金</small>
        </div>
        <div class="hero-stat">
          <span>累计盈亏</span>
          <strong :class="profitClass(portfolio.total_pnl)">{{ signedMoney(portfolio.total_pnl) }}</strong>
          <small :class="profitClass(portfolio.total_pnl_ratio)">{{ signedPercent(portfolio.total_pnl_ratio) }}</small>
        </div>
        <div class="hero-stat">
          <span>年化 XIRR</span>
          <strong :class="profitClass(portfolio.portfolio_xirr)">{{ signedPercent(portfolio.portfolio_xirr) }}</strong>
          <small>现金流加权</small>
        </div>
        <div class="hero-stat">
          <span>最大回撤</span>
          <strong :class="drawdownClass(portfolio.max_drawdown)">{{ drawdownPercent(portfolio.max_drawdown) }}</strong>
          <small>{{ drawdownWindow }}</small>
        </div>
        <div class="hero-stat">
          <span>最大持仓占比</span>
          <strong>{{ percent(portfolio.top_weight) }}</strong>
          <small>{{ concentrationLabel }}</small>
        </div>
        <div class="hero-stat" v-if="latestAdvice?.overall_suggestion">
          <span>AI 研判</span>
          <strong style="font-size:16px;color:var(--brand-600);">📋 {{ latestAdvice.overall_suggestion?.slice(0, 20) || '查看详情' }}</strong>
          <small>{{ latestAdvice.advice_date }}</small>
        </div>
      </div>
    </div>

    <!-- V2: 今日重点事项 + AI研判 + 风险暴露 -->
    <div class="v2-section" v-if="command.today_focus">
      <el-row :gutter="16">
        <!-- 今日重点事项 4 卡片 -->
        <el-col :xs="24" :lg="14">
          <el-card shadow="hover">
            <template #header><span style="font-weight: bold;">今天最该关注的事</span></template>
            <el-row :gutter="12">
              <el-col :xs="12" :sm="6" v-if="todayFocus.top_contributor">
                <div class="focus-card-v2">
                  <div class="focus-tag up">最大贡献</div>
                  <div class="focus-name">{{ todayFocus.top_contributor.fund_name }}</div>
                  <div class="focus-value text-profit">{{ signedMoney(todayFocus.top_contributor.daily_pnl) }}</div>
                </div>
              </el-col>
              <el-col :xs="12" :sm="6" v-if="todayFocus.top_dragger">
                <div class="focus-card-v2">
                  <div class="focus-tag down">最大拖累</div>
                  <div class="focus-name">{{ todayFocus.top_dragger.fund_name }}</div>
                  <div class="focus-value text-loss">{{ signedMoney(todayFocus.top_dragger.daily_pnl) }}</div>
                </div>
              </el-col>
              <el-col :xs="12" :sm="6" v-if="todayFocus.top_opportunity">
                <div class="focus-card-v2">
                  <div class="focus-tag info">市场机会</div>
                  <div class="focus-name">{{ todayFocus.top_opportunity.name }}</div>
                  <div class="focus-value">{{ signedPercent(todayFocus.top_opportunity.change_pct) }} · 热度{{ todayFocus.top_opportunity.heat_score }}</div>
                </div>
              </el-col>
              <el-col :xs="12" :sm="6" v-if="todayFocus.market_signal">
                <div class="focus-card-v2">
                  <div class="focus-tag warn">市场信号</div>
                  <div class="focus-name">沪深300</div>
                  <div class="focus-value">{{ todayFocus.market_signal }}</div>
                </div>
              </el-col>
            </el-row>
          </el-card>
        </el-col>

        <!-- AI 研判摘要 -->
        <el-col :xs="24" :lg="10">
          <el-card shadow="hover" v-if="command.ai_summary?.suggested_action">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold;">今日 AI 研判</span>
                <el-button text size="small" @click="$router.push('/ai-advisor')">详情 →</el-button>
              </div>
            </template>
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
              <el-tag :type="aiActionTagType" size="large" effect="dark">{{ aiActionLabel }}</el-tag>
              <el-tag :type="aiPositionTagType" size="small">{{ aiPositionLabel }}</el-tag>
              <span style="font-size: 12px; color: var(--gray-400);">置信度 {{ ((command.ai_summary?.confidence || 0) * 100).toFixed(0) }}%</span>
            </div>
            <div style="font-size: 13px; color: var(--gray-700); line-height: 1.6; margin-bottom: 8px;">
              {{ command.ai_summary?.summary || command.ai_summary?.overall_suggestion }}
            </div>
            <div v-if="command.ai_summary?.key_reasons?.length" style="border-top: 1px solid var(--gray-200); padding-top: 8px;">
              <div v-for="(r, i) in command.ai_summary.key_reasons" :key="i" style="font-size: 12px; color: var(--gray-500); padding: 2px 0;">
                {{ i + 1 }}. {{ r }}
              </div>
            </div>
          </el-card>

          <!-- 风险暴露摘要 -->
          <el-card shadow="hover" style="margin-top: 12px;" v-if="command.risk_summary?.top1_pct">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold;">组合风险暴露</span>
                <el-button text size="small" @click="$router.push('/risk-exposure')">详情 →</el-button>
              </div>
            </template>
            <el-row :gutter="8">
              <el-col :span="8">
                <div class="risk-mini">
                  <div class="risk-mini-val" :class="(command.risk_summary.top1_pct || 0) > 15 ? 'text-warn' : ''">{{ command.risk_summary.top1_pct }}%</div>
                  <div class="risk-mini-label">最大持仓</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="risk-mini">
                  <div class="risk-mini-val" :class="(command.risk_summary.top3_pct || 0) > 45 ? 'text-warn' : ''">{{ command.risk_summary.top3_pct }}%</div>
                  <div class="risk-mini-label">前3大占比</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="risk-mini">
                  <div class="risk-mini-val" :class="(command.risk_summary.high_volatility_pct || 0) > 50 ? 'text-warn' : ''">{{ command.risk_summary.high_volatility_pct }}%</div>
                  <div class="risk-mini-label">高波动占比</div>
                </div>
              </el-col>
            </el-row>
            <div v-if="command.risk_summary.top_industries?.length" style="margin-top: 8px; font-size: 12px; color: var(--gray-500);">
              行业TOP: {{ command.risk_summary.top_industries.map((i:any) => `${i.name} ${i.value}%`).join(' / ') }}
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- Metric Cards -->
    <div class="stat-row" style="display:none;">
      <div class="metric-card">
        <span class="label">总资产</span>
        <span class="value">{{ money(portfolio.total_value) }}</span>
        <span class="sub">{{ portfolio.holding_count || 0 }} 只持仓</span>
      </div>
    </div>

    <!-- Main Content Grid -->
    <div class="content-grid">
      <!-- Left Column -->
      <div class="content-main">
        <!-- Focus Items -->
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>今天最该关注的事</h2>
              <p>影响持仓与复盘的关键信息</p>
            </div>
            <el-tag :type="riskTagType(latestAdvice?.risk_level)" effect="light" size="small">
              风险 {{ riskLabel(latestAdvice?.risk_level) }}
            </el-tag>
          </div>
          <div class="panel-body">
            <div class="focus-grid">
              <div v-for="(item, index) in focusItems" :key="item" class="focus-card">
                <span class="focus-num">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="focus-text">{{ item }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Daily Contribution -->
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>持仓贡献与拖累</h2>
              <p>按当日收益率排序，优先关注影响最大的基金</p>
            </div>
            <el-button text size="small" @click="$router.push('/holdings')">
              进入持仓 <el-icon style="margin-left:4px"><ArrowRight /></el-icon>
            </el-button>
          </div>
          <el-table :data="dailyRows" height="330" stripe>
            <el-table-column prop="fund_name" label="基金" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <router-link class="fund-link" :to="`/fund/${row.fund_code}`">
                  {{ row.fund_name || row.fund_code }}
                </router-link>
                <span class="code-tag">{{ row.fund_code }}</span>
              </template>
            </el-table-column>
            <el-table-column label="当日收益率" width="110" sortable prop="daily_pnl_ratio">
              <template #default="{ row }">
                <span :class="profitClass(row.daily_pnl_ratio)">{{ signedPercent(row.daily_pnl_ratio) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="当日盈亏" width="120" sortable prop="daily_pnl">
              <template #default="{ row }">
                <span :class="profitClass(row.daily_pnl)">{{ signedMoney(row.daily_pnl) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="持仓占比" width="90">
              <template #default="{ row }">{{ percent(row.weight) }}</template>
            </el-table-column>
            <el-table-column label="累计盈亏" width="120">
              <template #default="{ row }">
                <span :class="profitClass(row.pnl_amount)">{{ signedMoney(row.pnl_amount) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- Right Column -->
      <div class="content-side">
        <!-- Risk Radar -->
        <div class="panel">
          <div class="panel-header">
            <h2>风险雷达</h2>
          </div>
          <div class="panel-body">
            <div class="risk-list">
              <div v-for="item in (command.risk_flags || [])" :key="item.title" class="risk-item" :class="item.level">
                <strong>{{ item.title }}</strong>
                <span>{{ item.detail }}</span>
              </div>
              <div v-if="!(command.risk_flags || []).length" class="empty-state">
                <el-icon class="icon"><CircleCheck /></el-icon>
                <p>暂未检测到风险信号</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Asset Exposure -->
        <div class="panel">
          <div class="panel-header">
            <h2>资产暴露</h2>
          </div>
          <div class="panel-body">
            <v-chart :option="exposureOption" class="chart" autoresize />
          </div>
        </div>
      </div>
    </div>

    <!-- Opportunities Row -->
    <div class="content-grid">
      <div class="content-main">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>未持仓机会池</h2>
              <p>行业与概念热度候选，供 AI 建议与人工复核</p>
            </div>
            <el-button text size="small" @click="$router.push('/market')">
              查看行情 <el-icon style="margin-left:4px"><ArrowRight /></el-icon>
            </el-button>
          </div>
          <div class="panel-body">
            <div class="opportunity-list">
              <div v-for="item in (command.opportunities || [])" :key="`${item.board_type}-${item.name}`" class="opportunity-item">
                <div>
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.label }} · 热度 {{ item.heat_score }}</span>
                </div>
                <div class="opportunity-metrics">
                  <span :class="profitClass(item.change_pct)">{{ signedPercent(item.change_pct) }}</span>
                  <small>净流入 {{ moneyYi(item.main_net_inflow) }}</small>
                </div>
              </div>
              <div v-if="!(command.opportunities || []).length" class="empty-state">
                <el-icon class="icon"><Coin /></el-icon>
                <p>暂无机会池数据</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="content-side">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>数据新鲜度</h2>
              <p>决策前确认数据是否可用</p>
            </div>
          </div>
          <div class="panel-body">
            <div class="fresh-grid">
              <div>
                <span class="section-label">交易状态</span>
                <strong>{{ marketDateLabel }}</strong>
              </div>
              <div>
                <span class="section-label">指数行情</span>
                <strong>{{ command.data_freshness?.latest_index_time || '暂无' }}</strong>
              </div>
              <div>
                <span class="section-label">基金估值</span>
                <strong>{{ command.data_freshness?.latest_fund_estimate_time || '暂无' }}</strong>
              </div>
              <div>
                <span class="section-label">近三日新闻</span>
                <strong>{{ command.data_freshness?.recent_news_count || 0 }} 条</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh, ArrowRight, CircleCheck, Coin } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getCommandCenter, generateAdvice, getManagerAlerts, markManagerAlertRead } from '../api'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const command = ref<any>({})
const refreshing = ref(false)
const generating = ref(false)
// P0.2 — 基金经理预警
const managerAlerts = ref<any[]>([])
const showAllAlerts = ref(false)

function alertTypeLabel(t: string) {
  return ({ departure: '经理离职', new_join: '新任经理', tenure_milestone: '任职里程碑' } as any)[t] || t
}
function alertTagType(s: string) {
  if (s === 'high') return 'danger'
  if (s === 'medium') return 'warning'
  return 'info'
}
async function loadManagerAlerts() {
  try {
    const res: any = await getManagerAlerts(true, 50)
    managerAlerts.value = res?.items || []
  } catch {
    managerAlerts.value = []
  }
}
async function markAlertRead(id: number) {
  try {
    await markManagerAlertRead(id)
    managerAlerts.value = managerAlerts.value.filter(a => a.id !== id)
  } catch { /* 静默 */ }
}

const portfolio = computed(() => command.value.portfolio || {})
const latestAdvice = computed(() => command.value.latest_advice)
const isRestContext = computed(() =>
  latestAdvice.value?.data_quality?.is_trading_day === false ||
  command.value.data_freshness?.is_trading_day === false
)
const marketDateLabel = computed(() =>
  command.value.data_freshness?.is_trading_day === false ? '休市复盘' : '交易日'
)
const concentrationLabel = computed(() =>
  Number(portfolio.value.top_weight || 0) >= 25 ? '集中度偏高' : '集中度正常'
)
const drawdownWindow = computed(() => {
  const peak = portfolio.value.drawdown_peak_date
  const trough = portfolio.value.drawdown_trough_date
  if (peak && trough) return `${peak} 至 ${trough}`
  return '等待快照沉淀'
})
// V2 computed
const todayFocus = computed(() => command.value.today_focus || {})
const aiSummary = computed(() => command.value.ai_summary || {})
const aiActionLabel = computed(() => {
  const m: Record<string,string> = { add:'加仓', reduce:'减仓', hold:'持有', gradual_buy:'分批低吸', stop_profit:'止盈' }
  return m[aiSummary.value.suggested_action] || '观望'
})
const aiActionTagType = computed(() => {
  const a = aiSummary.value.suggested_action
  if (a === 'add' || a === 'gradual_buy') return 'danger'
  if (a === 'reduce' || a === 'stop_profit') return 'success'
  return 'info'
})
const aiPositionLabel = computed(() => {
  const m: Record<string,string> = { aggressive:'积极', neutral:'中性', defensive:'防御' }
  return m[aiSummary.value.position] || '中性'
})
const aiPositionTagType = computed(() => {
  if (aiSummary.value.position === 'aggressive') return 'danger'
  if (aiSummary.value.position === 'defensive') return 'success'
  return 'info'
})
const upCount = computed(() => dailyRows.value.filter((r: any) => (r.daily_pnl || 0) > 0).length)
const downCount = computed(() => dailyRows.value.filter((r: any) => (r.daily_pnl || 0) < 0).length)
const focusItems = computed(() =>
  command.value.decision?.focus_items?.length
    ? command.value.decision.focus_items
    : ['等待行情和持仓数据刷新']
)
const dailyRows = computed(() => {
  const gainers = command.value.daily_gainers || []
  const losers = command.value.daily_losers || []
  const map = new Map<string, any>()
  ;[...gainers, ...losers].forEach((item: any) => map.set(item.fund_code, item))
  return Array.from(map.values()).sort(
    (a: any, b: any) => Math.abs(b.daily_pnl || 0) - Math.abs(a.daily_pnl || 0)
  )
})
const actionSummary = computed(() => {
  const c = command.value.action_counts || {}
  return `加${c.add || 0} 减${c.reduce || 0} 留${c.hold || 0}`
})
const quickStats = computed(() => [
  { label: '持仓数量', value: `${portfolio.value.holding_count || 0}`, color: '' },
  { label: 'AI 动作', value: actionSummary.value, color: '' },
  {
    label: command.value.decision?.benchmark?.name || '沪深300',
    value: signedPercent(command.value.decision?.benchmark?.change_pct),
    color: profitClass(command.value.decision?.benchmark?.change_pct),
  },
])
const exposureOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, textStyle: { fontSize: 12, color: '#5f6368' } },
  color: ['#1a73e8', '#ea4335', '#34a853', '#fbbc04', '#4285f4', '#ff6d01'],
  series: [{
    type: 'pie',
    radius: ['48%', '72%'],
    center: ['50%', '44%'],
    label: { formatter: '{b}\n{d}%', fontSize: 11 },
    data: (command.value.exposure || []).length > 0
      ? (command.value.exposure || []).map((item: any) => ({ name: item.name, value: item.value }))
      : [{ name: '加载中', value: 1 }],
    silent: true,
  }],
}))

/* ---------- helpers (same as before) ---------- */
function money(val: any) {
  return (Number(val) || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function signedMoney(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : '-'}${money(Math.abs(n))}`
}
function percent(val: any) {
  return `${(Number(val) || 0).toFixed(2)}%`
}
function signedPercent(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function drawdownPercent(val: any) {
  const n = Math.abs(Number(val) || 0)
  return n > 0 ? `-${n.toFixed(2)}%` : '0.00%'
}
function moneyYi(val: any) {
  return `${((Number(val) || 0) / 100000000).toFixed(2)}亿`
}
function profitClass(val: any) {
  return Number(val || 0) >= 0 ? 'text-profit' : 'text-loss'
}
function drawdownClass(val: any) {
  return Math.abs(Number(val) || 0) >= 15 ? 'text-loss' : 'text-profit'
}
function riskLabel(risk: string) {
  if (risk === 'high') return '高'
  if (risk === 'low') return '低'
  return '中'
}
function riskTagType(risk: string) {
  if (risk === 'high') return 'danger'
  if (risk === 'low') return 'success'
  return 'warning'
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

async function loadData() {
  refreshing.value = true
  try {
    command.value = await getCommandCenter()
  } catch (e) {
    ElMessage.error('工作台数据加载失败')
  } finally {
    refreshing.value = false
  }
  loadManagerAlerts()  // 并行加载，不阻塞主数据
}
async function generateCloseAdvice() {
  generating.value = true
  try {
    const res = await generateAdvice(false) as any
    if (res.error) {
      ElMessage.error(res.error)
    } else {
      ElMessage.success(
        res.status === 'running' || res.status === 'queued'
          ? 'AI 建议已在后台生成，可到 AI 顾问页查看进度'
          : 'AI 建议已生成'
      )
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
/* ═══════════════════════════════════════════
 * Google-style Dashboard
 * ═══════════════════════════════════════════ */

.dashboard { max-width: var(--content-max-width); }

/* ── V2 Section ───────────────────────── */
.v2-section { margin-bottom: 24px; }
.focus-card-v2 { text-align: center; padding: 8px 0; }
.focus-tag { font-size: 10px; text-transform: uppercase; font-weight: 600; margin-bottom: 4px; border-radius: 4px; padding: 1px 6px; display: inline-block; }
.focus-tag.up { background: #fef0f0; color: var(--danger-500); }
.focus-tag.down { background: #f0f9eb; color: var(--success-500); }
.focus-tag.info { background: #ecf5ff; color: var(--brand-500); }
.focus-tag.warn { background: #fdf6ec; color: #e6a23c; }
.focus-name { font-size: 13px; font-weight: 600; color: var(--gray-800); margin: 4px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.focus-value { font-size: 13px; color: var(--gray-600); }

.risk-mini { text-align: center; }
.risk-mini-val { font-size: 22px; font-weight: 700; color: var(--gray-900); }
.risk-mini-val.text-warn { color: #e6a23c; }
.risk-mini-label { font-size: 10px; color: var(--gray-400); text-transform: uppercase; margin-top: 2px; }

/* ── Hero ──────────────────────────────── */
.today-hero {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}

.hero-main {
  flex: 1;
  background: linear-gradient(135deg, #e8f0fe 0%, #f8f9fa 100%);
  border-radius: var(--radius-xl);
  padding: 32px 36px;
  box-shadow: var(--shadow-xs);
}

.hero-label {
  font-size: var(--text-sm);
  color: var(--gray-600);
  margin-bottom: 4px;
}

.hero-big-number {
  font-size: 48px;
  font-weight: var(--weight-normal);
  line-height: 1.15;
  margin-bottom: 4px;
  letter-spacing: -0.02em;
  color: var(--gray-900);
}
.hero-big-number.up   { color: var(--danger-500); }
.hero-big-number.down { color: var(--success-500); }

.hero-sub {
  font-size: var(--text-lg);
  margin-bottom: 12px;
  color: var(--gray-700);
}
.hero-sub.up   { color: var(--danger-400); }
.hero-sub.down { color: var(--success-400); }

.hero-subline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--gray-600);
  font-size: var(--text-sm);
  margin-bottom: 12px;
}
.hero-subline strong {
  font-weight: var(--weight-medium);
}

.hero-story {
  font-size: var(--text-sm);
  color: var(--gray-700);
  line-height: 1.6;
  max-width: 480px;
}
.hero-story strong { color: var(--gray-900); font-weight: var(--weight-medium); }

.hero-stats {
  width: 400px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.hero-stat {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base);
}
.hero-stat:hover { box-shadow: var(--shadow-md); }
.hero-stat span {
  font-size: 11px;
  color: var(--gray-600);
  font-weight: var(--weight-medium);
  display: block;
}
.hero-stat strong {
  font-size: 20px;
  font-weight: var(--weight-normal);
  color: var(--gray-900);
  display: block;
  margin: 6px 0 2px;
}
.hero-stat strong.up   { color: var(--danger-500); }
.hero-stat strong.down { color: var(--success-500); }
.hero-stat small {
  font-size: 12px;
  color: var(--gray-600);
}
.hero-stat small.up   { color: var(--danger-500); }
.hero-stat small.down { color: var(--success-500); }

@media (max-width: 860px) {
  .today-hero { flex-direction: column; }
  .hero-stats { width: 100%; }
  .hero-big-number { font-size: 40px; }
}

/* ── Content Grid ──────────────────────── */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
}
.content-main { min-width: 0; }
.content-side { min-width: 0; }

/* ── Focus Grid ─────────────────────────── */
.focus-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}

.focus-card {
  background: var(--gray-100);
  border: none;
  border-radius: var(--radius-md);
  padding: var(--space-4);
  transition: all var(--transition-base);
}
.focus-card:hover { background: var(--brand-50); }

.focus-num {
  display: inline-block;
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--brand-500);
  background: #fff;
  border-radius: var(--radius-full);
  padding: 2px 10px;
  margin-bottom: var(--space-2);
  box-shadow: var(--shadow-xs);
}

.focus-text {
  display: block;
  font-size: var(--text-sm);
  color: var(--gray-800);
  line-height: 1.6;
}

/* ── Risk List ─────────────────────────── */
.risk-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.risk-item {
  border-left: 3px solid var(--gray-400);
  background: var(--gray-100);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: var(--space-3) var(--space-4);
}
.risk-item.high {
  border-left-color: var(--danger-500);
  background: var(--danger-50);
}
.risk-item.medium {
  border-left-color: var(--warning-500);
  background: var(--warning-50);
}
.risk-item.low {
  border-left-color: var(--success-500);
  background: var(--success-50);
}
.risk-item strong { display: block; font-size: var(--text-sm); color: var(--gray-900); }
.risk-item span { display: block; margin-top: 3px; font-size: var(--text-xs); color: var(--gray-600); }

/* ── Chart ──────────────────────────────── */
.chart { height: 280px; }

/* ── Opportunity List ──────────────────── */
.opportunity-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.opportunity-item {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: none;
  border-radius: var(--radius-md);
  background: var(--gray-100);
  transition: background var(--transition-base);
}
.opportunity-item:hover { background: var(--brand-50); }
.opportunity-item strong { display: block; font-size: var(--text-sm); color: var(--gray-900); font-weight: var(--weight-medium); }
.opportunity-item span,
.opportunity-item small { display: block; color: var(--gray-600); font-size: var(--text-xs); margin-top: 2px; }
.opportunity-metrics { text-align: right; flex-shrink: 0; }
.opportunity-metrics span { font-size: var(--text-sm); font-weight: var(--weight-medium); }

/* ── Fresh Grid ────────────────────────── */
.fresh-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}
.fresh-grid > div {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--gray-100);
}
.fresh-grid strong {
  display: block;
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--gray-900);
}

/* ── Profit colors ─────────────────────── */
:deep(.text-profit) { color: var(--danger-500) !important; }
:deep(.text-loss)   { color: var(--success-500) !important; }

@media (max-width: 1100px) {
  .content-grid { grid-template-columns: 1fr; }
  .focus-grid { grid-template-columns: 1fr; }
}

/* P0.2 经理预警横幅 */
.manager-alert-row { display: flex; flex-direction: column; gap: 6px; }
.manager-alert-item { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.manager-alert-item strong { color: var(--danger-600); min-width: 70px; font-family: var(--font-mono, monospace); }
.manager-alert-item span { flex: 1; color: var(--gray-700); }
</style>
