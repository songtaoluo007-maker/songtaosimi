<template>
  <div class="market-workbench">
    <header class="market-header">
      <div>
        <h2>行情监控</h2>
        <p>指数、行业、概念与全球市场联动监控</p>
      </div>
      <div class="header-actions">
        <span>更新时间 {{ lastUpdated || '-' }}</span>
        <el-button :loading="refreshing" @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新行情
        </el-button>
      </div>
    </header>

    <section class="ticker-strip">
      <button
        v-for="item in aIndices.slice(0, 6)"
        :key="item.symbol"
        class="ticker"
        :class="{ active: selected?.symbol === item.symbol }"
        @click="selectInstrument(item, 'index')"
      >
        <span>{{ item.name }}</span>
        <strong>{{ formatPrice(item.price) }}</strong>
        <em :class="profitClass(item.change_pct)">{{ signedPercent(item.change_pct) }}</em>
      </button>
    </section>

    <div class="market-layout">
      <aside class="watchlist">
        <div class="segment">
          <button :class="{ active: activeTab === 'index' }" @click="switchTab('index')">指数</button>
          <button :class="{ active: activeTab === 'sector' }" @click="switchTab('sector')">行业</button>
          <button :class="{ active: activeTab === 'concept' }" @click="switchTab('concept')">概念</button>
          <button :class="{ active: activeTab === 'global' }" @click="switchTab('global')">全球</button>
        </div>

        <div class="list-tools">
          <el-input v-model="keyword" placeholder="搜索名称/代码" clearable />
          <el-select v-model="sortKey" style="width: 116px;">
            <el-option label="涨跌幅" value="change_pct" />
            <el-option label="热度" value="heat_score" />
            <el-option label="资金流" value="main_net_inflow" />
            <el-option label="成交额" value="turnover" />
            <el-option label="最新价" value="price" />
          </el-select>
        </div>

        <el-table
          :data="displayRows"
          stripe
          height="640"
          highlight-current-row
          :current-row-key="selected?.symbol"
          row-key="symbol"
          v-loading="listLoading"
          @row-click="selectCurrentRow"
        >
          <el-table-column prop="name" label="名称" min-width="128">
            <template #default="{ row }">
              <div class="name-cell">
                <strong>{{ row.name }}</strong>
                <span>{{ row.symbol }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="最新" width="92" align="right">
            <template #default="{ row }">{{ formatPrice(row.price) }}</template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="92" align="right">
            <template #default="{ row }">
              <span :class="profitClass(row.change_pct)">{{ signedPercent(row.change_pct) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="成交额" width="104" align="right">
            <template #default="{ row }">{{ formatTurnover(row.turnover) }}</template>
          </el-table-column>
          <el-table-column v-if="activeTab === 'sector' || activeTab === 'concept'" label="热度" width="82" align="right">
            <template #default="{ row }">{{ formatHeat(row.heat_score) }}</template>
          </el-table-column>
          <el-table-column v-if="activeTab === 'sector' || activeTab === 'concept'" label="资金流" width="104" align="right">
            <template #default="{ row }">
              <span :class="profitClass(row.main_net_inflow)">{{ formatTurnover(row.main_net_inflow) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </aside>

      <main class="chart-desk">
        <div class="quote-panel" v-if="selected">
          <div>
            <div class="quote-name">{{ selected.name }}</div>
            <div class="quote-code">{{ selected.symbol }} · {{ tabLabel }}</div>
          </div>
          <strong :class="profitClass(selected.change_pct)">{{ formatPrice(selected.price) }}</strong>
          <span :class="profitClass(selected.change_pct)">{{ signedAmount(selected.change_amount) }}</span>
          <span :class="profitClass(selected.change_pct)">{{ signedPercent(selected.change_pct) }}</span>
          <em>开 {{ formatPrice(selected.open) }}</em>
          <em>高 {{ formatPrice(selected.high) }}</em>
          <em>低 {{ formatPrice(selected.low) }}</em>
          <em>额 {{ formatTurnover(selected.turnover) }}</em>
        </div>

        <div class="chart-toolbar">
          <el-radio-group v-model="period" size="small" @change="loadPreview">
            <el-radio-button value="intraday">分时</el-radio-button>
            <el-radio-button value="daily">日K</el-radio-button>
            <el-radio-button value="weekly">周K</el-radio-button>
            <el-radio-button value="monthly">月K</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="mainIndicator" size="small">
            <el-radio-button value="ma">MA</el-radio-button>
            <el-radio-button value="boll">BOLL</el-radio-button>
          </el-radio-group>
          <el-button :disabled="!selected" @click="openDetail">
            <el-icon><FullScreen /></el-icon>
            全屏详情
          </el-button>
        </div>

        <section class="chart-panel" v-loading="detailLoading">
          <v-chart :option="chartOption" class="market-chart" autoresize />
        </section>

        <div class="bottom-grid">
          <section class="rank-panel">
            <div class="panel-title">涨幅榜</div>
            <button v-for="row in gainers" :key="row.symbol" @click="selectInstrument(row, activeTab)">
              <span>{{ row.name }}</span>
              <strong class="up">{{ signedPercent(row.change_pct) }}</strong>
            </button>
          </section>
          <section class="rank-panel">
            <div class="panel-title">跌幅榜</div>
            <button v-for="row in losers" :key="row.symbol" @click="selectInstrument(row, activeTab)">
              <span>{{ row.name }}</span>
              <strong class="down">{{ signedPercent(row.change_pct) }}</strong>
            </button>
          </section>
          <section class="rank-panel">
            <div class="panel-title">成交额排行</div>
            <button v-for="row in turnoverLeaders" :key="row.symbol" @click="selectInstrument(row, activeTab)">
              <span>{{ row.name }}</span>
              <strong>{{ formatTurnover(row.turnover) }}</strong>
            </button>
          </section>
          <section v-if="activeTab === 'sector' || activeTab === 'concept'" class="rank-panel gradient-panel">
            <div class="panel-title">{{ boardRankTitle }}热度Top20</div>
            <button v-for="(row, index) in heatLeaders" :key="`heat-${row.name}`" @click="selectInstrument(row, activeTab)">
              <span><i :style="{ width: gradientWidth(index, heatLeaders.length) }"></i>{{ row.name }}</span>
              <strong>{{ formatHeat(row.heat_score) }}</strong>
            </button>
          </section>
          <section v-if="activeTab === 'sector' || activeTab === 'concept'" class="rank-panel gradient-panel">
            <div class="panel-title">{{ boardRankTitle }}资金流入Top20</div>
            <button v-for="(row, index) in inflowLeaders" :key="`flow-${row.name}`" @click="selectInstrument(row, activeTab)">
              <span><i :style="{ width: gradientWidth(index, inflowLeaders.length) }"></i>{{ row.name }}</span>
              <strong :class="profitClass(row.main_net_inflow)">{{ formatTurnover(row.main_net_inflow) }}</strong>
            </button>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import { AxisPointerComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getBoardRankings, getGlobalIndices, getIndices, getMarketDetail, getSectors, refreshMarketData } from '../api'

use([CandlestickChart, LineChart, BarChart, TooltipComponent, GridComponent, DataZoomComponent, LegendComponent, AxisPointerComponent, CanvasRenderer])

const router = useRouter()
const activeTab = ref<'index' | 'sector' | 'concept' | 'global'>('index')
const period = ref('daily')
const mainIndicator = ref('ma')
const sortKey = ref('change_pct')
const keyword = ref('')
const refreshing = ref(false)
const listLoading = ref(false)
const detailLoading = ref(false)
const aIndices = ref<any[]>([])
const sectors = ref<any[]>([])
const concepts = ref<any[]>([])
const globalIndices = ref<any[]>([])
const sectorRankings = ref<any>({ heat_top: [], inflow_top: [] })
const conceptRankings = ref<any>({ heat_top: [], inflow_top: [] })
const selected = ref<any>(null)
const detail = ref<any>({})
const lastUpdated = ref('')

const tabLabel = computed(() => ({ index: 'A股指数', sector: '行业板块', concept: '概念板块', global: '全球指数' }[activeTab.value]))
const sourceRows = computed(() => {
  if (activeTab.value === 'index') return aIndices.value
  if (activeTab.value === 'sector') return sectors.value
  if (activeTab.value === 'concept') return concepts.value
  return globalIndices.value
})
const displayRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return [...sourceRows.value]
    .filter((row: any) => !kw || String(row.name).toLowerCase().includes(kw) || String(row.symbol).toLowerCase().includes(kw))
    .sort((a: any, b: any) => Number(b[sortKey.value] || 0) - Number(a[sortKey.value] || 0))
})
const gainers = computed(() => [...sourceRows.value].sort((a: any, b: any) => Number(b.change_pct || 0) - Number(a.change_pct || 0)).slice(0, 8))
const losers = computed(() => [...sourceRows.value].sort((a: any, b: any) => Number(a.change_pct || 0) - Number(b.change_pct || 0)).slice(0, 8))
const turnoverLeaders = computed(() => [...sourceRows.value].sort((a: any, b: any) => Number(b.turnover || 0) - Number(a.turnover || 0)).slice(0, 8))
const activeRankings = computed(() => activeTab.value === 'concept' ? conceptRankings.value : sectorRankings.value)
const heatLeaders = computed(() => activeTab.value === 'sector' || activeTab.value === 'concept' ? (activeRankings.value.heat_top || []).slice(0, 20) : [])
const inflowLeaders = computed(() => activeTab.value === 'sector' || activeTab.value === 'concept' ? (activeRankings.value.inflow_top || []).slice(0, 20) : [])
const boardRankTitle = computed(() => {
  const text = activeRankings.value?.market_date_label || activeRankings.value?.board_data_label || ''
  return text.includes('休市') || text.includes('最近交易日') ? '最近交易日' : '交易日'
})
const rows = computed(() => detail.value.rows || [])

const chartOption = computed(() => {
  const data = rows.value
  if (period.value === 'intraday') {
    return {
      animation: false,
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      grid: [
        { left: 58, right: 34, top: 28, height: 330 },
        { left: 58, right: 34, top: 386, height: 96 },
      ],
      xAxis: [
        { type: 'category', data: data.map((d: any) => shortTime(d.time)), boundaryGap: false },
        { type: 'category', data: data.map((d: any) => shortTime(d.time)), gridIndex: 1, axisLabel: { show: false } },
      ],
      yAxis: [{ type: 'value', scale: true }, { type: 'value', gridIndex: 1, scale: true }],
      axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }, { type: 'slider', xAxisIndex: [0, 1], height: 22, bottom: 8 }],
      series: [
        { name: '分时', type: 'line', data: data.map((d: any) => d.price), symbol: 'none', smooth: true, lineStyle: { color: '#2563eb', width: 2 } },
        { name: '均价', type: 'line', data: data.map((d: any) => d.avg_price), symbol: 'none', smooth: true, lineStyle: { color: '#f59e0b', width: 1.5 } },
        { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: data.map((d: any) => d.volume), itemStyle: { color: '#94a3b8' } },
      ],
    }
  }

  const dates = data.map((d: any) => d.date)
  const close = data.map((d: any) => d.close)
  const boll = calcBoll(close)
  const mainLines = mainIndicator.value === 'boll'
    ? [
        { name: 'BOLL中轨', type: 'line', data: boll.mid, symbol: 'none', lineStyle: { width: 1 } },
        { name: 'BOLL上轨', type: 'line', data: boll.upper, symbol: 'none', lineStyle: { width: 1 } },
        { name: 'BOLL下轨', type: 'line', data: boll.lower, symbol: 'none', lineStyle: { width: 1 } },
      ]
    : [
        { name: 'MA5', type: 'line', data: data.map((d: any) => d.ma5), symbol: 'none', smooth: true, lineStyle: { width: 1 } },
        { name: 'MA10', type: 'line', data: data.map((d: any) => d.ma10), symbol: 'none', smooth: true, lineStyle: { width: 1 } },
        { name: 'MA20', type: 'line', data: data.map((d: any) => d.ma20), symbol: 'none', smooth: true, lineStyle: { width: 1 } },
        { name: 'MA60', type: 'line', data: data.map((d: any) => d.ma60), symbol: 'none', smooth: true, lineStyle: { width: 1 } },
      ]
  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { top: 0, data: ['K线', ...mainLines.map((line: any) => line.name), '成交量', 'MACD', 'DIF', 'DEA'] },
    grid: [
      { left: 58, right: 34, top: 34, height: 270 },
      { left: 58, right: 34, top: 330, height: 88 },
      { left: 58, right: 34, top: 444, height: 92 },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: { show: false } },
    ],
    yAxis: [
      { type: 'value', scale: true },
      { type: 'value', gridIndex: 1, scale: true },
      { type: 'value', gridIndex: 2, scale: true },
    ],
    axisPointer: { link: [{ xAxisIndex: [0, 1, 2] }] },
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1, 2] }, { type: 'slider', xAxisIndex: [0, 1, 2], height: 22, bottom: 8 }],
    series: [
      { name: 'K线', type: 'candlestick', data: data.map((d: any) => [d.open, d.close, d.low, d.high]), itemStyle: { color: '#dc2626', color0: '#16a34a', borderColor: '#dc2626', borderColor0: '#16a34a' } },
      ...mainLines,
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: data.map((d: any) => d.volume), itemStyle: { color: (p: any) => Number(data[p.dataIndex]?.close || 0) >= Number(data[p.dataIndex]?.open || 0) ? '#dc2626' : '#16a34a' } },
      { name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.macd), itemStyle: { color: (p: any) => p.value >= 0 ? '#dc2626' : '#16a34a' } },
      { name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.dif), symbol: 'none', lineStyle: { width: 1 } },
      { name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.dea), symbol: 'none', lineStyle: { width: 1 } },
    ],
  }
})

function currentSnapshotType() {
  return activeTab.value
}
function switchTab(tab: 'index' | 'sector' | 'concept' | 'global') {
  activeTab.value = tab
  if (displayRows.value.length) selectInstrument(displayRows.value[0], tab)
}
function selectCurrentRow(row: any) {
  selectInstrument(row, activeTab.value)
}
async function selectInstrument(row: any, tab = activeTab.value) {
  selected.value = row
  activeTab.value = tab as any
  await loadPreview()
}
async function loadPreview() {
  if (!selected.value) return
  detailLoading.value = true
  try {
    detail.value = await getMarketDetail(selected.value.symbol || selected.value.name, {
      name: selected.value.name,
      snapshot_type: currentSnapshotType(),
      period: period.value,
      limit: 180,
    }) as any
    lastUpdated.value = detail.value.updated_at || new Date().toLocaleString()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '行情详情加载失败')
  } finally {
    detailLoading.value = false
  }
}
async function loadLists() {
  listLoading.value = true
  try {
    const [idx, sectorRows, globalRows] = await Promise.all([
      getIndices(),
      getSectors('sector'),
      getGlobalIndices(),
    ])
    aIndices.value = idx as any[]
    sectors.value = sectorRows as any[]
    globalIndices.value = globalRows as any[]
    loadBoardRankings('sector')
    getSectors('concept')
      .then((rows: any) => { concepts.value = rows as any[]; loadBoardRankings('concept') })
      .catch(() => { concepts.value = [] })
    if (!selected.value && aIndices.value.length) await selectInstrument(aIndices.value[0], 'index')
  } finally {
    listLoading.value = false
  }
}
async function loadBoardRankings(type: 'sector' | 'concept') {
  try {
    const data = await getBoardRankings(type, 20) as any
    if (type === 'sector') sectorRankings.value = data
    else conceptRankings.value = data
    const merged = mergeRankingMetrics(type === 'sector' ? sectors.value : concepts.value, data)
    if (type === 'sector') sectors.value = merged
    else concepts.value = merged
    lastUpdated.value = data.updated_at || lastUpdated.value
  } catch {
    if (type === 'sector') sectorRankings.value = { heat_top: [], inflow_top: [] }
    else conceptRankings.value = { heat_top: [], inflow_top: [] }
  }
}
function mergeRankingMetrics(rows: any[], rankings: any) {
  const metricMap = new Map<string, any>()
  ;[...(rankings.heat_top || []), ...(rankings.inflow_top || [])].forEach((row: any) => {
    metricMap.set(row.name, { ...(metricMap.get(row.name) || {}), ...row })
  })
  return rows.map((row: any) => ({ ...row, ...(metricMap.get(row.name) || {}) }))
}
async function handleRefresh() {
  refreshing.value = true
  try {
    await refreshMarketData()
    await loadLists()
    await loadPreview()
    ElMessage.success('行情已刷新')
  } finally {
    refreshing.value = false
  }
}
function openDetail() {
  if (!selected.value) return
  router.push({
    path: `/market/detail/${encodeURIComponent(selected.value.symbol || selected.value.name)}`,
    query: { name: selected.value.name, type: currentSnapshotType() },
  })
}
function calcBoll(values: number[], n = 20) {
  const mid: any[] = []
  const upper: any[] = []
  const lower: any[] = []
  values.forEach((_, idx) => {
    if (idx + 1 < n) {
      mid.push(null); upper.push(null); lower.push(null); return
    }
    const slice = values.slice(idx + 1 - n, idx + 1)
    const avg = slice.reduce((sum, v) => sum + Number(v || 0), 0) / n
    const sd = Math.sqrt(slice.reduce((sum, v) => sum + Math.pow(Number(v || 0) - avg, 2), 0) / n)
    mid.push(Number(avg.toFixed(4)))
    upper.push(Number((avg + 2 * sd).toFixed(4)))
    lower.push(Number((avg - 2 * sd).toFixed(4)))
  })
  return { mid, upper, lower }
}
function formatPrice(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return '-'
  return n.toFixed(2)
}
function signedPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function signedAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
}
function formatTurnover(v: any) {
  const n = Number(v) || 0
  if (!n) return '-'
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toFixed(2)
}
function formatHeat(v: any) {
  const n = Number(v) || 0
  if (!n) return '-'
  return n >= 10000 ? `${(n / 10000).toFixed(1)}万` : n.toFixed(0)
}
function gradientWidth(index: number, total: number) {
  const base = total <= 1 ? 100 : 100 - (index / (total - 1)) * 58
  return `${Math.max(38, base).toFixed(0)}%`
}
function profitClass(v: any) {
  return Number(v) >= 0 ? 'up' : 'down'
}
function shortTime(v: string) {
  return String(v || '').slice(-8, -3) || v
}

onMounted(loadLists)
</script>

<style scoped>
.market-workbench { display: flex; flex-direction: column; gap: 12px; }
.market-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.market-header h2 { margin: 0; font-size: 24px; }
.market-header p { margin: 4px 0 0; color: #64748b; }
.header-actions { display: flex; align-items: center; gap: 12px; color: #64748b; font-size: 13px; }
.ticker-strip { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 8px; }
.ticker { border: 1px solid #e5e7eb; background: #fff; border-radius: 8px; padding: 10px; text-align: left; cursor: pointer; }
.ticker.active { border-color: #2563eb; box-shadow: 0 0 0 1px #2563eb inset; }
.ticker span, .ticker em { display: block; font-style: normal; color: #64748b; font-size: 12px; }
.ticker strong { display: block; margin: 4px 0; font-size: 18px; }
.market-layout { display: grid; grid-template-columns: minmax(420px, 36%) minmax(0, 1fr); gap: 12px; align-items: start; }
.watchlist, .chart-desk, .chart-panel, .rank-panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; }
.watchlist { padding: 12px; }
.segment { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 10px; }
.segment button { border: 1px solid #dbe3ef; background: #f8fafc; border-radius: 6px; height: 34px; cursor: pointer; }
.segment button.active { background: #2563eb; border-color: #2563eb; color: #fff; }
.list-tools { display: flex; gap: 8px; margin-bottom: 10px; }
.name-cell strong, .name-cell span { display: block; }
.name-cell span { color: #94a3b8; font-size: 12px; margin-top: 2px; }
.chart-desk { padding: 12px; min-width: 0; }
.quote-panel { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; border-bottom: 1px solid #e5e7eb; padding-bottom: 10px; margin-bottom: 10px; }
.quote-name { font-weight: 700; font-size: 18px; }
.quote-code, .quote-panel em { color: #64748b; font-size: 12px; font-style: normal; }
.quote-panel > strong { font-size: 28px; }
.chart-toolbar { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 10px; }
.chart-panel { padding: 8px; }
.market-chart { height: 570px; }
.bottom-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
.rank-panel { padding: 10px; }
.panel-title { font-weight: 700; margin-bottom: 8px; }
.rank-panel button { width: 100%; height: 32px; border: 0; border-top: 1px solid #f1f5f9; background: transparent; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.rank-panel span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gradient-panel button span { position: relative; display: flex; align-items: center; flex: 1; height: 100%; padding-left: 8px; }
.gradient-panel button i { position: absolute; left: 0; height: 18px; border-radius: 4px; background: linear-gradient(90deg, rgba(37, 99, 235, 0.22), rgba(220, 38, 38, 0.16)); }
.gradient-panel button span { isolation: isolate; }
.gradient-panel button span::first-letter { position: relative; }
.up { color: #dc2626; }
.down { color: #16a34a; }
@media (max-width: 1280px) {
  .ticker-strip { grid-template-columns: repeat(3, 1fr); }
  .market-layout { grid-template-columns: 1fr; }
}
</style>
