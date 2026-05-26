<template>
  <div class="terminal">
    <header class="terminal-head">
      <el-button :icon="ArrowLeft" text @click="$router.push('/market')">返回</el-button>
      <div class="instrument">
        <h2>{{ detail.name || indexName }}</h2>
        <span>{{ symbol }} · {{ typeLabel }} · {{ detail.source === 'online' ? '在线行情' : '本地快照' }}</span>
      </div>
      <div class="head-actions">
        <span>更新时间 {{ detail.updated_at || '-' }}</span>
        <el-button :loading="loading" @click="loadDetail">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </header>

    <section class="quote-bar" v-if="latestRow">
      <strong :class="profitClass(changePct)">{{ formatVal(latestPrice) }}</strong>
      <span :class="profitClass(changePct)">{{ signedAmount(changeAmount) }}</span>
      <span :class="profitClass(changePct)">{{ signedPercent(changePct) }}</span>
      <em>开 {{ formatVal(latestRow.open) }}</em>
      <em>高 {{ formatVal(latestRow.high) }}</em>
      <em>低 {{ formatVal(latestRow.low) }}</em>
      <em>量 {{ formatVolume(latestRow.volume) }}</em>
      <em>额 {{ formatTurnover(latestRow.turnover) }}</em>
    </section>

    <section class="tool-row">
      <el-radio-group v-model="period" size="small" @change="loadDetail">
        <el-radio-button value="intraday">分时</el-radio-button>
        <el-radio-button value="daily">日K</el-radio-button>
        <el-radio-button value="weekly">周K</el-radio-button>
        <el-radio-button value="monthly">月K</el-radio-button>
      </el-radio-group>
      <el-radio-group v-model="mainIndicator" size="small">
        <el-radio-button value="ma">MA</el-radio-button>
        <el-radio-button value="boll">BOLL</el-radio-button>
      </el-radio-group>
      <el-radio-group v-model="subIndicator" size="small">
        <el-radio-button value="macd">MACD</el-radio-button>
        <el-radio-button value="kdj">KDJ</el-radio-button>
        <el-radio-button value="rsi">RSI</el-radio-button>
      </el-radio-group>
      <el-select v-model="limit" size="small" style="width: 110px;" @change="loadDetail">
        <el-option label="120根" :value="120" />
        <el-option label="180根" :value="180" />
        <el-option label="300根" :value="300" />
        <el-option label="500根" :value="500" />
      </el-select>
    </section>

    <section class="chart-shell" v-loading="loading">
      <v-chart v-if="hasRows" :option="chartOption" class="chart" autoresize />
      <div v-else class="chart-empty">
        <el-icon :size="48" color="#cbd5e1"><TrendCharts /></el-icon>
        <p>{{ loading ? '加载中...' : '暂无 K 线数据' }}</p>
      </div>
    </section>

    <section class="indicator-grid" v-if="latestRow">
      <div v-for="item in indicatorCards" :key="item.label">
        <span>{{ item.label }}</span>
        <strong :class="item.className">{{ item.value }}</strong>
      </div>
    </section>

    <section class="data-shell">
      <div class="section-title">{{ period === 'intraday' ? '分时明细' : 'K线明细' }}</div>
      <el-table :data="tableRows" stripe height="360">
        <el-table-column :prop="period === 'intraday' ? 'time' : 'date'" label="时间" width="170" fixed />
        <el-table-column label="开" width="90" align="right"><template #default="{ row }">{{ formatVal(row.open) }}</template></el-table-column>
        <el-table-column label="高" width="90" align="right"><template #default="{ row }">{{ formatVal(row.high) }}</template></el-table-column>
        <el-table-column label="低" width="90" align="right"><template #default="{ row }">{{ formatVal(row.low) }}</template></el-table-column>
        <el-table-column label="收/价" width="90" align="right"><template #default="{ row }">{{ formatVal(row.close || row.price) }}</template></el-table-column>
        <el-table-column label="涨跌幅" width="100" align="right">
          <template #default="{ row }"><span :class="profitClass(row.change_pct)">{{ signedPercent(row.change_pct) }}</span></template>
        </el-table-column>
        <el-table-column label="成交量" width="120" align="right"><template #default="{ row }">{{ formatVolume(row.volume) }}</template></el-table-column>
        <el-table-column label="成交额" width="120" align="right"><template #default="{ row }">{{ formatTurnover(row.turnover) }}</template></el-table-column>
        <el-table-column label="MA5" width="90" align="right"><template #default="{ row }">{{ formatVal(row.ma5) }}</template></el-table-column>
        <el-table-column label="MA20" width="90" align="right"><template #default="{ row }">{{ formatVal(row.ma20) }}</template></el-table-column>
        <el-table-column label="MACD" width="90" align="right"><template #default="{ row }">{{ formatVal(row.macd) }}</template></el-table-column>
        <el-table-column label="KDJ" width="150" align="right">
          <template #default="{ row }">{{ formatVal(row.kdj_k) }}/{{ formatVal(row.kdj_d) }}/{{ formatVal(row.kdj_j) }}</template>
        </el-table-column>
        <el-table-column label="RSI14" width="90" align="right"><template #default="{ row }">{{ formatVal(row.rsi14) }}</template></el-table-column>
      </el-table>
    </section>
  </div>
</template>

<!--
  MarketDetail.vue V2 改动：
  1. chart 容器：从固定 720px 改为 min(82vh, 860px)，响应式自适应
  2. ECharts grid 全部改百分比，副图（MACD/KDJ/RSI）在任何容器尺寸下都完整显示
  3. 自定义 tooltip formatter（中文友好）
  4. MA / BOLL 配色规范化
  5. 空状态：无数据时显示友好提示
  6. dataZoom 默认从倒数 120 根开始，全屏详情页打开就能看清最新走势
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Refresh, TrendCharts } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import { AxisPointerComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getMarketDetail } from '../api'

use([CandlestickChart, LineChart, BarChart, TooltipComponent, GridComponent, DataZoomComponent, LegendComponent, AxisPointerComponent, CanvasRenderer])

const MA_COLORS = { ma5: '#fb923c', ma10: '#a855f7', ma20: '#0ea5e9', ma60: '#10b981' }
const BOLL_COLORS = { mid: '#fbbf24', upper: '#0ea5e9', lower: '#a855f7' }

const route = useRoute()
const symbol = route.params.symbol as string
const indexName = ref((route.query.name as string) || symbol)
const snapshotType = computed(() => (route.query.type as string) || 'index')
const typeLabel = computed(() => ({ index: '指数', sector: '行业板块', concept: '概念板块', global: '全球指数' } as any)[snapshotType.value] || snapshotType.value)
const period = ref('daily')
const mainIndicator = ref('ma')
const subIndicator = ref('macd')
const limit = ref(180)
const loading = ref(false)
const detail = ref<any>({})
const rows = computed(() => detail.value.rows || [])
const hasRows = computed(() => rows.value.length > 0)
const tableRows = computed(() => [...rows.value].reverse())
const latestRow = computed(() => rows.value.length ? rows.value[rows.value.length - 1] : null)
const latestPrice = computed(() => latestRow.value?.close || latestRow.value?.price)
const changePct = computed(() => latestRow.value?.change_pct || 0)
const changeAmount = computed(() => latestRow.value?.change_amount || 0)

const indicatorCards = computed(() => {
  const d = latestRow.value
  if (!d) return []
  return [
    { label: 'MA5', value: formatVal(d.ma5) },
    { label: 'MA10', value: formatVal(d.ma10) },
    { label: 'MA20', value: formatVal(d.ma20) },
    { label: 'MA60', value: formatVal(d.ma60) },
    { label: 'MACD', value: formatVal(d.macd), className: profitClass(d.macd) },
    { label: 'DIF/DEA', value: `${formatVal(d.dif)} / ${formatVal(d.dea)}` },
    { label: 'KDJ', value: `${formatVal(d.kdj_k)} / ${formatVal(d.kdj_d)} / ${formatVal(d.kdj_j)}` },
    { label: 'RSI14', value: formatVal(d.rsi14) },
    { label: '量比', value: d.volume_ratio || '-' },
    { label: '振幅', value: signedPercent(d.amplitude) },
  ]
})

function kLineTooltipFormatter(params: any[]) {
  if (!params || !params.length) return ''
  const klineParam = params.find(p => p.seriesType === 'candlestick')
  if (!klineParam) return ''
  const [open, close, low, high] = klineParam.data.slice(1)
  const prev = klineParam.dataIndex > 0 ? rows.value[klineParam.dataIndex - 1] : null
  const changeAmt = prev ? close - Number(prev.close || 0) : 0
  const changePctVal = prev && Number(prev.close) ? (changeAmt / Number(prev.close)) * 100 : 0
  const colorChange = changeAmt >= 0 ? '#dc2626' : '#16a34a'
  const row = rows.value[klineParam.dataIndex]

  return [
    `<div style="font-weight:600;margin-bottom:6px;">${klineParam.axisValue}</div>`,
    `<div style="display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12px;">`,
    `<span>开盘</span><span>${formatVal(open)}</span>`,
    `<span>最高</span><span style="color:#dc2626">${formatVal(high)}</span>`,
    `<span>最低</span><span style="color:#16a34a">${formatVal(low)}</span>`,
    `<span>收盘</span><span style="color:${colorChange};font-weight:600;">${formatVal(close)}</span>`,
    `<span>涨跌</span><span style="color:${colorChange};">${signedAmount(changeAmt)} (${signedPercent(changePctVal)})</span>`,
    row?.volume ? `<span>成交量</span><span>${formatVolume(row.volume)}</span>` : '',
    row?.turnover ? `<span>成交额</span><span>${formatTurnover(row.turnover)}</span>` : '',
    row?.macd ? `<span>MACD</span><span style="color:${Number(row.macd) >= 0 ? '#dc2626' : '#16a34a'}">${formatVal(row.macd)}</span>` : '',
    `</div>`,
  ].filter(Boolean).join('')
}

const chartOption = computed(() => {
  const data = rows.value
  if (period.value === 'intraday') {
    return {
      animation: false,
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross', label: { show: true } } },
      legend: { top: 4, data: ['分时', '均价', '成交量'] },
      grid: [
        { left: 60, right: 36, top: '6%', height: '64%' },
        { left: 60, right: 36, top: '76%', height: '14%' },
      ],
      xAxis: [
        { type: 'category', data: data.map((d: any) => shortTime(d.time)), boundaryGap: false },
        { type: 'category', data: data.map((d: any) => shortTime(d.time)), gridIndex: 1, axisLabel: { show: false } },
      ],
      yAxis: [
        { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(2) } },
        { type: 'value', gridIndex: 1, scale: true, splitNumber: 2 },
      ],
      axisPointer: { link: [{ xAxisIndex: [0, 1] }], label: { backgroundColor: '#1e293b' } },
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }, { type: 'slider', xAxisIndex: [0, 1], bottom: 8, height: 22 }],
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
  const subSeries = buildSubSeries(data)
  const subNames = subSeries.map((s: any) => s.name)
  const defaultStart = Math.max(0, 100 - (120 / Math.max(data.length, 1)) * 100)

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
      data: ['K线', ...mainLines.map(l => l.name), '成交量', ...subNames],
      selected: { 'MA5': true, 'MA10': false, 'MA20': true, 'MA60': true },
    },
    // V2: grid 用百分比，任何容器高度都能完整显示三栏（主图/量/副指标）
    grid: [
      { left: 60, right: 36, top: '6%', height: '48%' },
      { left: 60, right: 36, top: '58%', height: '15%' },
      { left: 60, right: 36, top: '77%', height: '15%' },
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
      { type: 'inside', xAxisIndex: [0, 1, 2], start: defaultStart, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2], start: defaultStart, end: 100, bottom: 8, height: 22 },
    ],
    series: [
      { name: 'K线', type: 'candlestick', data: data.map((d: any) => [d.open, d.close, d.low, d.high]), itemStyle: { color: '#dc2626', color0: '#16a34a', borderColor: '#dc2626', borderColor0: '#16a34a' } },
      ...mainLines,
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: data.map((d: any) => d.volume), itemStyle: { color: (p: any) => Number(data[p.dataIndex]?.close || 0) >= Number(data[p.dataIndex]?.open || 0) ? '#dc2626' : '#16a34a' } },
      ...subSeries,
    ],
  }
})

function buildSubSeries(data: any[]) {
  if (subIndicator.value === 'kdj') {
    return [
      { name: 'K', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.kdj_k), symbol: 'none', lineStyle: { color: '#fb923c', width: 1 } },
      { name: 'D', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.kdj_d), symbol: 'none', lineStyle: { color: '#0ea5e9', width: 1 } },
      { name: 'J', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.kdj_j), symbol: 'none', lineStyle: { color: '#a855f7', width: 1 } },
    ]
  }
  if (subIndicator.value === 'rsi') {
    return [{ name: 'RSI14', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.rsi14), symbol: 'none', lineStyle: { color: '#7c3aed', width: 1.5 } }]
  }
  return [
    { name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.macd), itemStyle: { color: (p: any) => p.value >= 0 ? '#dc2626' : '#16a34a' } },
    { name: 'DIF', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.dif), symbol: 'none', lineStyle: { width: 1, color: '#fb923c' } },
    { name: 'DEA', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: data.map((d: any) => d.dea), symbol: 'none', lineStyle: { width: 1, color: '#0ea5e9' } },
  ]
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
function formatVal(v: any) { const n = Number(v); return Number.isFinite(n) && n !== 0 ? n.toFixed(2) : '-' }
function signedPercent(v: any) { const n = Number(v); return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '-' }
function signedAmount(v: any) { const n = Number(v); return Number.isFinite(n) ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}` : '-' }
function profitClass(v: any) { return Number(v) >= 0 ? 'up' : 'down' }
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
function shortTime(v: string) { return String(v || '').slice(-8, -3) || v }

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getMarketDetail(symbol, {
      name: indexName.value,
      snapshot_type: snapshotType.value,
      period: period.value,
      limit: limit.value,
    }) as any
  } finally {
    loading.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.terminal { display: flex; flex-direction: column; gap: 12px; max-width: var(--content-max-width); }
.terminal-head { display: flex; align-items: center; gap: 12px; }
.instrument { flex: 1; }
.instrument h2 { margin: 0; font-size: 24px; font-weight: 700; color: var(--gray-900); letter-spacing: -0.01em; }
.instrument span, .head-actions, .quote-bar em { color: var(--gray-500); font-size: var(--text-sm); font-style: normal; }
.head-actions { display: flex; align-items: center; gap: 10px; }
.quote-bar, .tool-row, .chart-shell, .indicator-grid, .data-shell {
  background: #fff; border: 1px solid var(--gray-200); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm);
}
.quote-bar { display: flex; align-items: baseline; gap: 16px; padding: 12px 14px; flex-wrap: wrap; }
.quote-bar strong { font-size: 32px; font-weight: 700; }
.tool-row { display: flex; gap: 10px; align-items: center; padding: 10px; flex-wrap: wrap; }
.chart-shell { padding: 8px; }

/* V2 关键改动：高度用 vh，副图永远完整显示 */
.chart { width: 100%; height: min(82vh, 860px); min-height: 600px; }
.chart-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 600px; color: var(--gray-400); gap: 12px; }
.chart-empty p { margin: 0; font-size: 14px; }

.indicator-grid { display: grid; grid-template-columns: repeat(10, 1fr); gap: 0; overflow: hidden; }
.indicator-grid div { padding: 10px 12px; border-right: 1px solid var(--gray-100); }
.indicator-grid div:last-child { border-right: none; }
.indicator-grid span { display: block; font-size: var(--text-xs); color: var(--gray-400); }
.indicator-grid strong { display: block; margin-top: 4px; font-size: 15px; font-weight: 700; color: var(--gray-800); }
.data-shell { padding: 12px 14px; }
.section-title { font-weight: 700; margin-bottom: 8px; font-size: var(--text-sm); color: var(--gray-800); }
.up { color: var(--danger-500); }
.down { color: var(--success-500); }

@media (max-width: 1280px) {
  .indicator-grid { grid-template-columns: repeat(5, 1fr); }
  .chart { height: min(75vh, 720px); min-height: 540px; }
}
</style>
