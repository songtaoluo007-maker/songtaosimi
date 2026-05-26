<template>
  <div class="fund-detail">
    <header class="page-head">
      <el-button :icon="ArrowLeft" text @click="$router.push('/holdings')">返回持仓</el-button>
      <div class="title">
        <div class="eyebrow">FUND PROFILE</div>
        <h1>{{ data.fund_name || code }}</h1>
        <p>{{ code }} · {{ data.fund_type || '基金' }} · 更新时间 {{ data.updated_at || '-' }}</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
    </header>

    <el-row :gutter="14" class="metric-row">
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>当天收益率</span>
          <strong :class="profitClass(data.latest_daily_return)">{{ formatPercent(data.latest_daily_return) }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>当日盈亏</span>
          <strong :class="profitClass(holding.daily_pnl)">{{ signedMoney(holding.daily_pnl) }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>持仓市值</span>
          <strong>¥{{ number(holding.current_value) }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>持有收益率</span>
          <strong :class="profitClass(holding.pnl_ratio)">{{ formatPercent(holding.pnl_ratio) }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>最大回撤</span>
          <strong class="down">{{ formatPercent(data.risk_metrics?.max_drawdown) }}</strong>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>样本胜率</span>
          <strong>{{ formatPercent(data.risk_metrics?.win_rate) }}</strong>
        </div>
      </el-col>
    </el-row>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="收益走势" name="return">
        <el-row :gutter="14">
          <el-col :xs="24" :lg="16">
            <section class="panel" v-loading="loading">
              <div class="panel-head">
                <h2>净值走势与日收益</h2>
                <p>上方为净值，下方为日涨跌幅</p>
              </div>
              <v-chart :option="navOption" class="chart" autoresize />
            </section>
          </el-col>
          <el-col :xs="24" :lg="8">
            <section class="panel">
              <div class="panel-head compact"><h2>区间表现</h2></div>
              <div class="return-grid">
                <div v-for="item in returnCards" :key="item.label">
                  <span>{{ item.label }}</span>
                  <strong :class="profitClass(item.value)">{{ formatPercent(item.value) }}</strong>
                </div>
              </div>
            </section>
            <section class="panel">
              <div class="panel-head compact"><h2>持仓档案</h2></div>
              <div class="profile-list">
                <div><span>份额</span><strong>{{ number(holding.shares) }}</strong></div>
                <div><span>成本金额</span><strong>¥{{ number(holding.cost_amount) }}</strong></div>
                <div><span>成本净值</span><strong>{{ number(holding.cost_price, 4) }}</strong></div>
                <div><span>最新估值</span><strong>{{ number(holding.current_nav, 4) }}</strong></div>
                <div><span>估值日期</span><strong>{{ holding.daily_pnl_date || '-' }}</strong></div>
              </div>
            </section>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="持仓穿透" name="holding">
        <el-row :gutter="14">
          <el-col :xs="24" :lg="9">
            <section class="panel" v-loading="loading">
              <div class="panel-head compact"><h2>行业配置</h2></div>
              <v-chart :option="industryOption" class="small-chart" autoresize />
            </section>
          </el-col>
          <el-col :xs="24" :lg="15">
            <section class="panel">
              <div class="panel-head">
                <h2>重仓股票</h2>
                <p>用于判断基金暴露是否和你的其他基金重叠</p>
              </div>
              <el-table :data="data.stock_holdings || []" height="430" stripe>
                <el-table-column prop="stock_code" label="代码" width="100" />
                <el-table-column prop="stock_name" label="股票" min-width="140" />
                <el-table-column label="占净值" width="100"><template #default="{ row }">{{ formatPercent(row.ratio) }}</template></el-table-column>
                <el-table-column label="持股数" width="120"><template #default="{ row }">{{ number(row.shares) }}</template></el-table-column>
                <el-table-column label="持仓市值" width="130"><template #default="{ row }">{{ number(row.market_value) }}</template></el-table-column>
                <el-table-column prop="quarter" label="季度" min-width="150" />
              </el-table>
            </section>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="基金经理" name="manager">
        <section class="panel">
          <div class="panel-head">
            <h2>现任 + 历任基金经理</h2>
            <p>老基民关键看点 — 业绩归因到具体经理，离职预警在 Dashboard 红点提示</p>
            <el-button size="small" :loading="managerSyncing" @click="refreshManagers">
              <el-icon><Refresh /></el-icon> 立即拉取最新
            </el-button>
          </div>
          <div v-if="!managers.current?.length && !managers.history?.length" class="manager-empty">
            <p>暂无经理数据，点击"立即拉取最新"从东方财富同步</p>
          </div>
          <div v-if="managers.current?.length" class="manager-block">
            <h3>现任</h3>
            <el-table :data="managers.current" stripe>
              <el-table-column prop="manager_name" label="经理" width="140" />
              <el-table-column prop="start_date" label="任职开始" width="130" />
              <el-table-column label="已任职" width="120">
                <template #default="{ row }">{{ tenureDays(row.start_date) }}</template>
              </el-table-column>
              <el-table-column label="任职回报" width="140">
                <template #default="{ row }">
                  <span :class="profitClass(row.tenure_return_pct)">
                    {{ formatPercent(row.tenure_return_pct) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div v-if="managers.history?.length" class="manager-block">
            <h3>历任</h3>
            <el-table :data="managers.history" stripe height="280">
              <el-table-column prop="manager_name" label="经理" width="140" />
              <el-table-column prop="start_date" label="开始" width="120" />
              <el-table-column prop="end_date" label="结束" width="120" />
              <el-table-column label="任职回报" width="140">
                <template #default="{ row }">
                  <span :class="profitClass(row.tenure_return_pct)">
                    {{ formatPercent(row.tenure_return_pct) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane label="风险体检" name="risk">
        <section class="panel">
          <div class="panel-head">
            <h2>风险指标</h2>
            <p>样本来自净值历史，适合做相对比较，不等同未来预测</p>
          </div>
          <div class="risk-grid">
            <div>
              <span>最大回撤</span>
              <strong class="down">{{ formatPercent(data.risk_metrics?.max_drawdown) }}</strong>
              <p>越接近0说明近期回撤越小</p>
            </div>
            <div>
              <span>日波动率</span>
              <strong>{{ formatPercent(data.risk_metrics?.volatility) }}</strong>
              <p>波动越大，越适合分批而非一次性加仓</p>
            </div>
            <div>
              <span>样本胜率</span>
              <strong>{{ formatPercent(data.risk_metrics?.win_rate) }}</strong>
              <p>统计历史上涨天数占比</p>
            </div>
            <div>
              <span>样本天数</span>
              <strong>{{ data.risk_metrics?.sample_days || 0 }}</strong>
              <p>样本越少，结论越需要降权</p>
            </div>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { getFundAnalysis, getFundManagers, syncFundManagers } from '../api'

use([LineChart, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const code = route.params.code as string
const data = ref<any>({})
const loading = ref(false)
const activeTab = ref('return')
const holding = computed(() => data.value.holding || {})

const returnCards = computed(() => {
  const r = data.value.returns || {}
  return [
    { label: '近1周', value: r['1w'] },
    { label: '近1月', value: r['1m'] },
    { label: '近3月', value: r['3m'] },
    { label: '近6月', value: r['6m'] },
    { label: '近1年', value: r['1y'] },
  ]
})

const navOption = computed(() => {
  const rows = data.value.nav_history || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['单位净值', '日收益率'] },
    grid: [{ left: 55, right: 35, top: 42, height: 250 }, { left: 55, right: 35, top: 320, height: 90 }],
    xAxis: [
      { type: 'category', data: rows.map((r: any) => r.date) },
      { type: 'category', data: rows.map((r: any) => r.date), gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [{ type: 'value', scale: true }, { type: 'value', gridIndex: 1 }],
    series: [
      { name: '单位净值', type: 'line', data: rows.map((r: any) => r.nav), symbol: 'none', smooth: true, lineStyle: { color: '#2563eb', width: 2 } },
      { name: '日收益率', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: rows.map((r: any) => r.daily_return), itemStyle: { color: (p: any) => p.value >= 0 ? '#dc2626' : '#16a34a' } },
    ],
  }
})

const industryOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  color: ['#2563eb', '#dc2626', '#16a34a', '#f59e0b', '#7c3aed', '#475569'],
  series: [{
    type: 'pie',
    radius: ['42%', '68%'],
    center: ['50%', '44%'],
    data: (data.value.industry_allocation || []).map((i: any) => ({ name: i.industry, value: i.ratio || i.market_value })),
  }],
}))

function formatPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function profitClass(v: any) {
  return Number(v || 0) >= 0 ? 'up' : 'down'
}
function number(v: any, digits = 2) {
  const n = Number(v) || 0
  return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
function signedMoney(v: any) {
  const n = Number(v) || 0
  return `${n >= 0 ? '+' : '-'}¥${number(Math.abs(n))}`
}
// P0.2 — 基金经理
const managers = ref<any>({ current: [], history: [] })
const managerSyncing = ref(false)

function tenureDays(start: any) {
  if (!start) return '-'
  try {
    const days = Math.floor((Date.now() - new Date(start).getTime()) / 86400000)
    if (days < 30) return `${days} 天`
    if (days < 365) return `${Math.floor(days / 30)} 个月`
    const years = Math.floor(days / 365)
    const months = Math.floor((days % 365) / 30)
    return months > 0 ? `${years} 年 ${months} 个月` : `${years} 年`
  } catch {
    return '-'
  }
}

async function loadManagers() {
  try {
    managers.value = (await getFundManagers(code)) as any
  } catch (e: any) {
    // 静默失败，避免影响主页面
    managers.value = { current: [], history: [] }
  }
}

async function refreshManagers() {
  managerSyncing.value = true
  try {
    const res: any = await syncFundManagers(code)
    if (res?.warning) {
      ElMessage.warning(res.warning)
    } else {
      ElMessage.success(`已同步 ${res?.updated || 0} 条经理记录`)
    }
    await loadManagers()
  } catch (e: any) {
    ElMessage.error('同步失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    managerSyncing.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    data.value = await getFundAnalysis(code, 360)
  } finally {
    loading.value = false
  }
  loadManagers()  // 并行加载，不阻塞主流程
}
onMounted(loadData)
</script>

<style scoped>
.fund-detail { max-width: var(--content-max-width); }
.manager-empty { text-align: center; color: var(--gray-400); padding: 24px 0; font-size: 13px; }
.manager-block { margin-top: 18px; }
.manager-block h3 { font-size: 14px; font-weight: 600; color: var(--gray-700); margin: 0 0 8px; }
.up { color: var(--danger-500); font-weight: 600; }
.down { color: var(--success-500); font-weight: 600; }
.page-head { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 24px; }
.title { flex: 1; }
.eyebrow { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--gray-400); }
h1 { margin: 4px 0; font-size: 24px; font-weight: 700; color: var(--gray-900); letter-spacing: -0.01em; }
h2 { margin: 0; font-size: var(--text-lg); font-weight: 600; color: var(--gray-800); }
p { margin: 0; color: var(--gray-500); font-size: var(--text-sm); }
.metric-row { margin-bottom: var(--space-4); }
.metric, .panel { background: #fff; border: 1px solid var(--gray-200); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.metric { padding: var(--space-4); min-height: 104px; transition: all var(--transition-base); }
.metric:hover { border-color: var(--brand-200); box-shadow: var(--shadow-md); transform: translateY(-1px); }
.metric span { font-size: var(--text-xs); color: var(--gray-400); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.metric strong { display: block; margin-top: var(--space-3); font-size: 22px; font-weight: 700; color: var(--gray-900); }
.detail-tabs :deep(.el-tabs__header) { margin-bottom: var(--space-4); }
.panel { padding: var(--space-5); margin-bottom: var(--space-4); }
.panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: var(--space-4); }
.panel-head.compact { align-items: center; }
.chart { height: 440px; }
.small-chart { height: 450px; }
.return-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-3); }
.return-grid div, .profile-list div, .risk-grid div {
  background: var(--gray-50);
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  transition: all var(--transition-fast);
}
.return-grid div:hover, .profile-list div:hover, .risk-grid div:hover { border-color: var(--gray-200); }
.return-grid span, .return-grid strong, .profile-list span, .profile-list strong, .risk-grid span, .risk-grid strong { display: block; }
.return-grid span, .profile-list span, .risk-grid span { font-size: var(--text-xs); color: var(--gray-400); }
.return-grid strong, .profile-list strong, .risk-grid strong { margin-top: 7px; font-size: 18px; font-weight: 700; color: var(--gray-800); }
.profile-list { display: grid; gap: var(--space-3); }
.risk-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-3); }
.risk-grid p { margin-top: 7px; font-size: var(--text-xs); line-height: 1.5; color: var(--gray-500); }
.up { color: var(--danger-500) !important; }
.down { color: var(--success-500) !important; }
@media (max-width: 980px) {
  .page-head { display: grid; }
  .risk-grid { grid-template-columns: 1fr 1fr; }
}
</style>
