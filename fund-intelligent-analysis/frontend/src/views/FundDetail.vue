<template>
  <div>
    <div class="header">
      <el-button :icon="ArrowLeft" text @click="$router.push('/holdings')">返回持仓</el-button>
      <div class="title">
        <h2>{{ data.fund_name || code }}</h2>
        <span>{{ code }} · {{ data.fund_type || '基金' }} · {{ data.updated_at || '-' }}</span>
      </div>
      <el-button :loading="loading" @click="loadData">刷新</el-button>
    </div>

    <el-row :gutter="12" class="cards">
      <el-col :xs="12" :sm="8" :md="6" :lg="4" v-for="item in returnCards" :key="item.label">
        <div class="mini-card">
          <span>{{ item.label }}</span>
          <strong :class="profitClass(item.value)">{{ formatPercent(item.value) }}</strong>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="15">
        <section class="panel" v-loading="loading">
          <div class="panel-head"><h3>净值走势与日收益</h3></div>
          <v-chart :option="navOption" class="chart" autoresize />
        </section>
      </el-col>
      <el-col :xs="24" :lg="9">
        <section class="panel" v-loading="loading">
          <div class="panel-head"><h3>行业配置</h3></div>
          <v-chart :option="industryOption" class="small-chart" autoresize />
        </section>
      </el-col>
    </el-row>

    <section class="panel">
      <div class="panel-head"><h3>重仓股票</h3></div>
      <el-table :data="data.stock_holdings || []" height="420" stripe>
        <el-table-column prop="stock_code" label="代码" width="100" />
        <el-table-column prop="stock_name" label="股票" min-width="140" />
        <el-table-column label="占净值" width="100"><template #default="{ row }">{{ formatPercent(row.ratio) }}</template></el-table-column>
        <el-table-column label="持股数" width="120"><template #default="{ row }">{{ number(row.shares) }}</template></el-table-column>
        <el-table-column label="持仓市值" width="130"><template #default="{ row }">{{ number(row.market_value) }}</template></el-table-column>
        <el-table-column prop="quarter" label="季度" min-width="180" />
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getFundAnalysis } from '../api'

use([LineChart, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const code = route.params.code as string
const data = ref<any>({})
const loading = ref(false)

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
    legend: { top: 0, data: ['单位净值', '日增长率'] },
    grid: [{ left: 55, right: 40, top: 38, height: 260 }, { left: 55, right: 40, top: 330, height: 90 }],
    xAxis: [{ type: 'category', data: rows.map((r: any) => r.date) }, { type: 'category', data: rows.map((r: any) => r.date), gridIndex: 1, axisLabel: { show: false } }],
    yAxis: [{ type: 'value', scale: true }, { type: 'value', gridIndex: 1 }],
    series: [
      { name: '单位净值', type: 'line', data: rows.map((r: any) => r.nav), symbol: 'none', smooth: true, lineStyle: { color: '#2f6fef' } },
      { name: '日增长率', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: rows.map((r: any) => r.daily_return), itemStyle: { color: (p: any) => p.value >= 0 ? '#d94b64' : '#259b72' } },
    ],
  }
})

const industryOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['42%', '68%'],
    data: (data.value.industry_allocation || []).map((i: any) => ({ name: i.industry, value: i.ratio || i.market_value })),
  }],
}))

function formatPercent(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function profitClass(v: any) {
  return Number(v) >= 0 ? 'up' : 'down'
}
function number(v: any) {
  const n = Number(v) || 0
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
async function loadData() {
  loading.value = true
  try {
    data.value = await getFundAnalysis(code, 240) as any
  } finally {
    loading.value = false
  }
}
onMounted(loadData)
</script>

<style scoped>
.header { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
.title { flex: 1; }
.title h2 { margin: 0; }
.title span { color: #64748b; font-size: 13px; }
.cards { margin-bottom: 16px; }
.mini-card, .panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; }
.mini-card span { display: block; color: #64748b; font-size: 12px; }
.mini-card strong { display: block; margin-top: 6px; font-size: 20px; }
.panel { margin-bottom: 16px; }
.panel-head h3 { margin: 0 0 12px; }
.chart { height: 450px; }
.small-chart { height: 450px; }
.up { color: #d94b64; }
.down { color: #259b72; }
</style>
