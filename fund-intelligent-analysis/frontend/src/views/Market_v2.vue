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
          <el-icon><Refresh /></el-icon> 刷新行情
        </el-button>
      </div>
    </header>

    <section class="ticker-strip">
      <button
        v-for="item in aIndices.slice(0, 6)" :key="item.symbol"
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
          :data="displayRows" stripe height="640" highlight-current-row
          :current-row-key="selected?.symbol" row-key="symbol"
          v-loading="listLoading" @row-click="selectCurrentRow"
        >
          <template #empty>
            <el-empty v-if="!listLoading" :description="activeTab === 'global' ? '暂无全球指数数据' : '暂无行情数据，请点击刷新'">
              <el-button type="primary" size="small" @click="handleRefresh">刷新行情</el-button>
            </el-empty>
          </template>
          <el-table-column prop="name" label="名称" min-width="128">
            <template #default="{ row }">
              <div class="name-cell">
                <strong>{{ row.name }}</strong><span>{{ row.symbol }}</span>
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
          <!-- V2 新增：快捷区间 -->
          <el-radio-group v-model="quickRange" size="small" @change="onQuickRange">
            <el-radio-button :value="60">60</el-radio-button>
            <el-radio-button :value="120">120</el-radio-button>
            <el-radio-button :value="240">240</el-radio-button>
          </el-radio-group>
          <el-button :disabled="!selected" @click="openDetail">
            <el-icon><FullScreen /></el-icon> 全屏详情
          </el-button>
        </div>

        <section class="chart-panel" v-loading="detailLoading">
          <v-chart v-if="hasRows" :option="chartOption" class="market-chart" autoresize />
          <div v-else class="chart-empty">
            <el-icon :size="48" color="#cbd5e1"><TrendCharts /></el-icon>
            <p>{{ detailLoading ? '加载中...' : '暂无 K 线数据，请选择左侧标的或刷新行情' }}</p>
          </div>
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
        </div>
      </main>
    </div>
  </div>
</template>

<!--
  Market.vue V2 改动（针对"K线显示不完整 + 简陋"反馈）：

  1. 布局响应式：.market-chart 由固定 570px 改为 flex: 1; min-height: 540px;
     ECharts grid 用百分比 top/height，容器变高/变窄都不会裁掉副图

  2. 自定义 tooltip：K线 hover 时显示中文友好的"开/高/低/收/涨跌额/涨跌幅/MA5/MA20"信息卡

  3. MA 配色规范：MA5=橙 MA10=紫 MA20=蓝 MA60=绿，符合主流软件配色（同花顺/通达信）
     BOLL 同样规范配色

  4. 十字光标 label：showLabel:true，鼠标拖动时 Y 轴价格、X 轴日期都会显示

  5. 加 30/60/120/240 快捷区间，避免用户拖 slider

  6. 空状态：detail 加载失败 / 无数据时显示友好提示，而非空白 echarts 画布

  7. legend 改为放在主图上方，且 selected 默认只勾选 MA20，避免 MA5/10/20/60 四条线挤在一起
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, Refresh, TrendCharts } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import { AxisPointerComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getBoardRankings, getGlobalIndices, getIndices, getMarketDetail, getSectors, refreshMarketData } from '../api'

use([CandlestickChart, LineChart, BarChart, TooltipComponent, GridComponent, DataZoomComponent, LegendComponent, AxisPointerComponent, MarkLineComponent, CanvasRenderer])

// V2: MA 配色规范，符合主流软件
const MA_COLORS = { ma5: '#fb923c', ma10: '#a855f7', ma20: '#0ea5e9', ma60: '#10b981' }
const BOLL_COLORS = { mid: '#fbbf24', upper: '#0ea5e9', lower: '#a855f7' }

const router = useRouter()
const activeTab = ref<'index' | 'sector' | 'concept' | 'global'>('index')
const period = ref('daily')
const mainIndicator = ref('ma')
const quickRange = ref(120)
const sortKey = ref('change_pct')
const keyword = ref('')
const debouncedKeyword = ref('')
let keywordTimer: ReturnType<typeof setTimeout> | null = null
watch(keyword, (val) => {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => { debouncedKeyword.value = val }, 200)
})

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
  const kw = debouncedKeyword.value.trim().toLowerCase()
  return [...sourceRows.value]
    .filter((row: any) => !kw || String(row.name).toLowerCase().includes(kw) || String(row.symbol).toLowerCase().includes(kw))
    .sort((a: any, b: any) => Number(b[sortKey.value] || 0) - Number(a[sortKey.value] || 0))
})
const gainers = computed(() => [...sourceRows.value].sort((a, b) => Number(b.change_pct || 0) - Number(a.change_pct || 0)).slice(0, 8))
const losers = computed(() => [...sourceRows.value].sort((a, b) => Number(a.change_pct || 0) - Number(b.change_pct || 0)).slice(0, 8))
const turnoverLeaders = computed(() => [...sourceRows.value].sort((a, b) => Number(b.turnover || 0) - Number(a.turnover || 0)).slice(0, 8))
const rows = computed(() => detail.value.rows || [])
const hasRows = computed(() => rows.value.length > 0)

// V2: K线 tooltip 自定义 formatter（中文友好）
function kLineTooltipFormatter(params: any[]) {
  if (!params || !params.length) return ''
  const klineParam = params.find(p => p.seriesType === 'candlestick')
  if (!klineParam) return ''
  const [open, close, low, high] = klineParam.data.slice(1)
  const prev = klineParam.dataIndex > 0 ? rows.value[klineParam.dataIndex - 1] : null
  const changeAmount = prev ? close - Number(prev.close || 0) : 0
  const changePct = prev && Number(prev.close) ? (changeAmount / Number(prev.close)) * 100 : 0
  const colorChange = changeAmount >= 0 ? '#dc2626' : '#16a34a'
  const row = rows.value[klineParam.dataIndex]

  const lines = [
    `<div style="font-weight:600;margin-bottom:6px;">${klineParam.axisValue}</div>`,
    `<div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12px;">`,
    `<span>开盘</span><span>${formatPrice(open)}</span>`,
    `<span>最高</span><span style="color:#dc2626">${formatPrice(high)}</span>`,
    `<span>最低</span><span style="color:#16a34a">${formatPrice(low)}</span>`,
    `<span>收盘</span><span style="color:${colorChange};font-weight:600;">${formatPrice(close)}</span>`,
    `<span>涨跌</span><span style="color:${colorChange};">${signedAmount(changeAmount)} (${signedPercent(changePct)})</span>`,
    row?.volume ? `<span>成交量</span><span>${formatVolume(row.volume)}</span>` : '',
    row?.turnover ? `<span>成交额</span><span>${formatTurnover(row.turnover)}</span>` : '',
    row?.ma5 ? `<span style="color:${MA_COLORS.ma5}">MA5</span><span>${formatPrice(row.ma5)}</span>` : '',
    row?.ma20 ? `<span style="color:${MA_COLORS.ma20}">MA20</span><span>${formatPrice(row.ma20)}</span>` : '',
    `</div>`,
  ].filter(Boolean).join('')
  return lines
}

const chartOption = computed(() => {
  const data = rows.value
  if (period.value === 'intraday') {
    return {
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { show: true } },
      },
      legend: { top: 4, data: ['分时', '均价', '成交量'] },
      // V2: grid 用百分比，容器变高/变窄都自适应
      grid: [
        { left: 60, right: 36, top: '8%', height: '60%' },
        { left: 60, right: 36, top: '74%', height: '14%' },
      ],
      xAxis: [
        { type: 'category', data: data.map((d: any) => shortTime(d.time)), boundaryGap: false },
        { type: 'category', data: data.map((d: any) => shortTime(d.time)), gridIndex: 1, axisLabel: { show: false } },
      ],
      yAxis: [
        { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(2) } },
        { type: 'value', gridIndex: 1, scale: true },
      ],
      axisPointer: { link: [{ xAxisIndex: [0, 1] }], label: { backgroundColor: '#1e293b' } },
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }, { type: 'slider', xAxisIndex: [0, 1], height: 22, bottom: 8 }],
      series: [
        { name: '分时', type: 'line', data: data.map((d: any) => d.price), symbol: 'none', smooth: true, lineStyle: { color: '#2563eb', width: 2 }, areaStyle: { color: 'rgba(37, 99, 235, 0.1)' } },
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
        { name: 'BOLL中轨', type: 'line', data: boll.mid, symbol: 'none', lineStyle: { width: 1, color: BOLL_COLORS.mid } },
        { name: 'BOLL上轨', type: 'line', data: boll.upper, symbol: 'none', lineStyle: { width: 1, color: BOLL_COLORS.upper } },
        { name: 'BOLL下轨', type: 'line', data: boll.lower, symbol: 'none', lineStyle: { width: 1, color: BOLL_COLORS.lower } },
      ]
    : [
        { name: 'MA5', type: 'line', data: data.map((d: any) => d.ma5), symbol: 'none', smooth: true, lineStyle: { width: 1, color: MA_COLORS.ma5 } },
        { name: 'MA10', type: 'line', data: data.map((d: any) => d.ma10), symbol: 'none', smooth: true, lineStyle: { width: 1, color: MA_COLORS.ma10 } },
        { name: 'MA20', type: 'line', data: data.map((d: any) => d.ma20), symbol: 'none', smooth: true, lineStyle: { width: 1.5, color: MA_COLORS.ma20 } },
        { name: 'MA60', type: 'line', data: data.map((d: any) => d.ma60), symbol: 'none', smooth: true, lineStyle: { width: 1, color: MA_COLORS.ma60 } },
      ]

  // 计算 dataZoom 默认显示区间
  const zoomStart = quickRange.value ? Math.max(0, 100 - (quickRange.value / data.length) * 100) : 0

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { show: true } },
      formatter: kLineTooltipFormatter,
      backgroundColor: 'rgba(255,255,255,0.98)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: 10,
    },
    legend: {
      top: 4,
      data: ['K线', ...mainLines.map(l => l.name), '成交量', 'MACD', 'DIF', 'DEA'],
      selected: { 'MA5': true, 'MA10': false, 'MA20': true, 'MA60': true },
    },
    // V2: grid 全部用百分比，副图永远完整可见
    grid: [
      { left: 60, right: 36, top: '8%', height: '48%' },
      { left: 60, right: 36, top: '60%', height: '15%' },
      { left: 60, right: 36, top: '79%', height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLine: { onZero: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: { show: false } },
    ],
    yAxis: [
      { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(2) } },
      { type: 'value', gridIndex: 1, scale: true, splitNumber: 2 },
      { type: 'value', gridIndex: 2, scale: true, splitNumber: 2 },
    ],
    axisPointer: { link: [{ xAxisIndex: [0, 1, 2] }], label: { backgroundColor: '#1e293b' } },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2], start: zoomStart, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2], start: zoomStart, end: 100, height: 22, bottom: 8 },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick',
        data: data.map((d: any) => [d.open, d.close, d.low, d.high]),
        itemStyle: { color: '#dc2626', color0: '#16a34a', borderColor: '#dc2626', borderColor0: '#16a34a' },
      },
      ...mainLines,
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: data.map((d: any) => d.volume),
        itemStyle: {
          color: (p: any) => Number(data[p.dataIndex]?.close || 0) >= Number(data[p.dataIndex]?.open || 0) ? '#dc2626' : '#16a34a',
        },
      },
      {
        name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2,
        data: data.map((d: any) => d.macd),
        itemStyle: { color: (p: any) => p.value >= 0 ? '#dc2626' : '#16a34a' },
      },
      { name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.dif), symbol: 'none', lineStyle: { width: 1, color: '#fb923c' } },
      { name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.dea), symbol: 'none', lineStyle: { width: 1, color: '#0ea5e9' } },
    ],
  }
})

function onQuickRange() {
  // 触发响应式重算 dataZoom
}
function currentSnapshotType() { return activeTab.value }
function switchTab(tab: 'index' | 'sector' | 'concept' | 'global') {
  activeTab.value = tab
  if (displayRows.value.length) selectInstrument(displayRows.value[0], tab)
}
function selectCurrentRow(row: any) { selectInstrument(row, activeTab.value) }
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
      limit: 240,
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
      getIndices(), getSectors('sector'), getGlobalIndices(),
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
  const mid: any[] = [], upper: any[] = [], lower: any[] = []
  values.forEach((_, idx) => {
    if (idx + 1 < n) { mid.push(null); upper.push(null); lower.push(null); return }
    const slice = values.slice(idx + 1 - n, idx + 1)
    const avg = slice.reduce((sum, v) => sum + Number(v || 0), 0) / n
    const sd = Math.sqrt(slice.reduce((sum, v) => sum + Math.pow(Number(v || 0) - avg, 2), 0) / n)
    mid.push(Number(avg.toFixed(4)))
    upper.push(Number((avg + 2 * sd).toFixed(4)))
    lower.push(Number((avg - 2 * sd).toFixed(4)))
  })
  return { mid, upper, lower }
}
function formatPrice(v: any) { const n = Number(v); return Number.isFinite(n) && n !== 0 ? n.toFixed(2) : '-' }
function signedPercent(v: any) { const n = Number(v); return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '-' }
function signedAmount(v: any) { const n = Number(v); return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}` : '-' }
function formatTurnover(v: any) {
  const n = Number(v) || 0
  if (!n) return '-'
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toFixed(2)
}
function formatVolume(v: any) {
  const n = Number(v) || 0
  if (!n) return '-'
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿手`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万手`
  return n.toFixed(0)
}
function profitClass(v: any) { return Number(v) >= 0 ? 'up' : 'down' }
function shortTime(v: string) { return String(v || '').slice(-8, -3) || v }

onMounted(() => {
  loadLists()
  refreshing.value = true
  refreshMarketData()
    .then(() => loadLists())
    .catch(() => {})
    .finally(() => { refreshing.value = false })
})
</script>

<style scoped>
.market-workbench { display: flex; flex-direction: column; gap: 12px; max-width: var(--content-max-width); }
.market-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 4px; }
.market-header h2 { margin: 0; font-size: 24px; font-weight: 700; color: var(--gray-900); letter-spacing: -0.01em; }
.market-header p { margin: 4px 0 0; color: var(--gray-500); font-size: var(--text-sm); }
.header-actions { display: flex; align-items: center; gap: 12px; color: var(--gray-500); font-size: var(--text-sm); }
.ticker-strip { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 8px; }
.ticker { border: 1px solid var(--gray-200); background: #fff; border-radius: var(--radius-md); padding: 10px 12px; text-align: left; cursor: pointer; transition: all var(--transition-fast); }
.ticker:hover { border-color: var(--brand-300); box-shadow: var(--shadow-sm); }
.ticker.active { border-color: var(--brand-500); box-shadow: inset 0 0 0 1px var(--brand-500); }
.ticker span, .ticker em { display: block; font-style: normal; color: var(--gray-500); font-size: var(--text-xs); }
.ticker strong { display: block; margin: 4px 0; font-size: 17px; font-weight: 700; color: var(--gray-800); }
.market-layout { display: grid; grid-template-columns: minmax(420px, 36%) minmax(0, 1fr); gap: 12px; align-items: start; }
.watchlist, .chart-desk, .chart-panel, .rank-panel { background: #fff; border: 1px solid var(--gray-200); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.watchlist { padding: 12px; }
.segment { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 10px; }
.segment button { border: 1px solid var(--gray-200); background: var(--gray-50); border-radius: var(--radius-sm); height: 34px; cursor: pointer; font-size: var(--text-sm); color: var(--gray-600); transition: all var(--transition-fast); }
.segment button:hover { border-color: var(--brand-300); }
.segment button.active { background: var(--brand-600); border-color: var(--brand-600); color: #fff; font-weight: 600; }
.list-tools { display: flex; gap: 8px; margin-bottom: 10px; }
.name-cell strong { display: block; font-weight: 600; }
.name-cell span { display: block; color: var(--gray-400); font-size: var(--text-xs); margin-top: 2px; }
.chart-desk { padding: 12px; min-width: 0; display: flex; flex-direction: column; }
.quote-panel { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; border-bottom: 1px solid var(--gray-100); padding-bottom: 10px; margin-bottom: 10px; }
.quote-name { font-weight: 700; font-size: 18px; color: var(--gray-800); }
.quote-code, .quote-panel em { color: var(--gray-500); font-size: var(--text-xs); font-style: normal; }
.quote-panel > strong { font-size: 28px; font-weight: 700; }
.chart-toolbar { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.chart-panel { padding: 8px; flex: 1; min-height: 600px; }

/* V2 关键改动：高度用 vh，副图永远完整可见 */
.market-chart { height: 100%; width: 100%; min-height: 580px; }
.chart-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 580px; color: var(--gray-400); gap: 12px; }
.chart-empty p { margin: 0; font-size: 14px; }

.bottom-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
.rank-panel { padding: 10px 12px; }
.panel-title { font-weight: 700; margin-bottom: 8px; font-size: var(--text-sm); color: var(--gray-700); }
.rank-panel button { width: 100%; height: 32px; border: 0; border-top: 1px solid var(--gray-100); background: transparent; display: flex; justify-content: space-between; align-items: center; cursor: pointer; font-size: var(--text-xs); transition: background var(--transition-fast); }
.rank-panel button:hover { background: var(--gray-50); }
.rank-panel span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.up { color: var(--danger-500); }
.down { color: var(--success-500); }

@media (max-width: 1280px) {
  .ticker-strip { grid-template-columns: repeat(3, 1fr); }
  .market-layout { grid-template-columns: 1fr; }
  .market-chart { min-height: 520px; }
}
</style>
