<template>
  <div class="capital-flow-page">
    <header class="page-head">
      <div>
        <h2>资金流向追踪</h2>
        <p>北向资金 · 主力动向 · 融资融券 · 龙虎榜机构</p>
      </div>
      <el-button :loading="refreshing" @click="handleRefresh">
        <el-icon><Refresh /></el-icon>刷新数据
      </el-button>
    </header>

    <div class="summary-cards" v-loading="loading">
      <div class="flow-card" v-for="card in summaryCards" :key="card.label">
        <span>{{ card.label }}</span>
        <strong :class="card.cls">{{ card.value }}</strong>
        <small>{{ card.sub }}</small>
      </div>
      <div class="flow-card national-card">
        <span>国家队动向</span>
        <strong :class="nationalTeamCls">{{ nationalTeamValue }}</strong>
        <small>{{ nationalTeamSub }}</small>
      </div>
    </div>

    <div class="charts-grid">
      <section class="chart-panel" v-if="northHistory.length">
        <h3>北向资金净流入（亿元）</h3>
        <v-chart :option="northOption" autoresize style="height:300px" />
      </section>
      <section class="chart-panel">
        <h3>主力资金分层（亿元）</h3>
        <v-chart :option="forceOption" autoresize style="height:300px" />
      </section>
      <section class="chart-panel" v-if="topSectors.length">
        <h3>行业主力净流入 TOP10</h3>
        <v-chart :option="sectorOption" autoresize style="height:360px" />
      </section>
      <section class="chart-panel">
        <h3>龙虎榜机构动向</h3>
        <v-chart :option="lhbOption" autoresize style="height:300px" />
      </section>
      <section class="chart-panel" v-if="nationalStocks.length">
        <h3>机构席位标的明细</h3>
        <el-table :data="nationalStocks.slice(0, 30)" stripe size="small" max-height="360">
          <el-table-column prop="name" label="股票" width="90" />
          <el-table-column label="净买卖(亿)" width="110">
            <template #default="{ row }">
              <span :style="{ color: (row.net_inflow ?? 0) >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
                {{ (row.net_inflow ?? 0) >= 0 ? '+' : '' }}{{ (row.net_inflow ?? 0).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="机构买入(亿)" width="110">
            <template #default="{ row }">{{ (row.institution_buy ?? 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="机构卖出(亿)" width="110">
            <template #default="{ row }">{{ (row.institution_sell ?? 0).toFixed(2) }}</template>
          </el-table-column>
        </el-table>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const loading = ref(false)
const refreshing = ref(false)
const data = ref<any>({})
const northHistory = ref<any[]>([])

const summaryCards = computed(() => {
  const d = data.value
  const nb = d.north_bound?.total_net ?? 0
  const mf = d.main_force?.summary
  const lhb = d.lhb?.net_institution ?? 0
  return [
    { label: '北向资金', value: `${nb >= 0 ? '+' : ''}${nb.toFixed(1)}亿`, cls: nb >= 0 ? 'up' : 'down', sub: '沪深港通净流入' },
    { label: '超大单', value: `${(mf?.super_large_net ?? 0) >= 0 ? '+' : ''}${(mf?.super_large_net ?? 0).toFixed(1)}亿`, cls: (mf?.super_large_net ?? 0) >= 0 ? 'up' : 'down', sub: '机构主力动向' },
    { label: '大单', value: `${(mf?.large_net ?? 0) >= 0 ? '+' : ''}${(mf?.large_net ?? 0).toFixed(1)}亿`, cls: (mf?.large_net ?? 0) >= 0 ? 'up' : 'down', sub: '游资大户动向' },
    { label: '机构席位', value: `${lhb >= 0 ? '+' : ''}${lhb.toFixed(1)}亿`, cls: lhb >= 0 ? 'up' : 'down', sub: '龙虎榜净买卖' },
  ]
})

const topSectors = computed(() => data.value.main_force?.top_sectors ?? [])
const nationalStocks = computed(() => data.value.lhb?.items?.filter((i: any) => i.symbol !== 'all') ?? [])
const nationalTeamValue = computed(() => {
  const net = data.value.lhb?.net_institution ?? 0
  return `${net >= 0 ? '+' : ''}${net.toFixed(1)}亿`
})
const nationalTeamCls = computed(() => (data.value.lhb?.net_institution ?? 0) >= 0 ? 'up' : 'down')
const nationalTeamSub = computed(() => {
  const n = nationalStocks.value.length
  return n > 0 ? `${n} 只标的龙虎榜机构席位` : '暂无数据'
})

function emptyChart(text: string) {
  return {
    title: { text, left: 'center', top: 'center', textStyle: { color: '#94A3B8', fontSize: 14 } },
  }
}

const forceOption = computed(() => {
  const mf = data.value.main_force?.summary
  if (!mf) return emptyChart('暂无主力资金数据')
  const items = [
    { name: '超大单', value: mf.super_large_net ?? 0 },
    { name: '大单', value: mf.large_net ?? 0 },
    { name: '中单', value: mf.medium_net ?? 0 },
    { name: '小单', value: mf.small_net ?? 0 },
  ]
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: items.map(i => i.name) },
    yAxis: { type: 'value', name: '亿元' },
    series: [{
      type: 'bar',
      data: items.map(i => ({
        value: i.value,
        itemStyle: { color: i.value >= 0 ? '#f56c6c' : '#67c23a' },
      })),
    }],
  }
})

const northOption = computed(() => {
  const h = northHistory.value
  if (!h.length) {
    return emptyChart('暂无北向资金历史数据，请刷新后再查看')
  }
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: h.map((d: any) => d.date?.slice(5) ?? '') },
    yAxis: { type: 'value', name: '亿元' },
    series: [{
      name: '北向净流入', type: 'bar',
      data: h.map((d: any) => d.net ?? 0),
      itemStyle: {
        color: (p: any) => p.value >= 0 ? '#f56c6c' : '#67c23a',
      },
    }],
  }
})

const sectorOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 110, right: 70, top: 10, bottom: 20 },
  xAxis: { type: 'value', name: '亿元' },
  yAxis: { type: 'category', data: topSectors.value.map((s: any) => s.name).reverse(), inverse: true },
  series: [{
    type: 'bar',
    data: topSectors.value.map((s: any) => ({
      value: s.net_inflow,
      itemStyle: { color: s.net_inflow >= 0 ? '#f56c6c' : '#67c23a' },
    })).reverse(),
    label: { show: true, position: 'right', formatter: '{c:.1f}亿' },
  }],
}))

const lhbOption = computed(() => {
  const items = data.value.lhb?.items ?? []
  if (!items.length) {
    return {
      title: { text: '暂无龙虎榜数据', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
    }
  }
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: ['机构席位'] },
    yAxis: { type: 'value', name: '亿元' },
    series: [
      { name: '买入', type: 'bar', data: [items.reduce((s: number, i: any) => s + (i.institution_buy ?? 0), 0)], itemStyle: { color: '#f56c6c' } },
      { name: '卖出', type: 'bar', data: [items.reduce((s: number, i: any) => s + (i.institution_sell ?? 0), 0)], itemStyle: { color: '#67c23a' } },
    ],
  }
})

import request from '../api/request'

async function loadData() {
  loading.value = true
  try {
    const resp = await request.get('/capital-flow/latest')
    data.value = resp as any
  } catch (e: any) {
    ElMessage.error('加载资金流数据失败: ' + (e.response?.data?.detail || e.message))
    data.value = {}
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await request.post('/capital-flow/refresh')
    await loadData()
    ElMessage.success('资金流向已刷新')
  } catch (e: any) {
    ElMessage.error('刷新失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    refreshing.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.capital-flow-page { max-width: var(--content-max-width); }
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.page-head h2 { margin: 0 0 4px; font-size: var(--text-3xl); font-weight: var(--weight-normal); color: var(--gray-900); letter-spacing: -0.02em; }
.page-head p { margin: 0; color: var(--gray-600); font-size: var(--text-sm); }

/* Summary cards — clean, no text cut-off */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}
.flow-card {
  background: #fff;
  border: none;
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base);
  min-width: 0;
}
.flow-card:hover { box-shadow: var(--shadow-md); }
.flow-card span {
  font-size: 11px;
  color: var(--gray-600);
  font-weight: var(--weight-medium);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.flow-card strong {
  font-size: 20px;
  font-weight: var(--weight-normal);
  display: block;
  margin: 6px 0 2px;
  color: var(--gray-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.flow-card strong.up { color: var(--danger-500); }
.flow-card strong.down { color: var(--success-500); }
.flow-card small {
  font-size: 11px;
  color: var(--gray-600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.national-card { background: linear-gradient(135deg, #e8f0fe, #fff); }

/* Charts */
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); }
.chart-panel {
  background: #fff;
  border: none;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-5) var(--space-6);
}
.chart-panel h3 {
  margin: 0 0 16px;
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
  color: var(--gray-900);
}

@media (max-width: 980px) {
  .summary-cards { grid-template-columns: repeat(3, 1fr); }
  .charts-grid { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .summary-cards { grid-template-columns: 1fr 1fr; }
}
</style>
