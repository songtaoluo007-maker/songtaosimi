<template>
  <div class="invest-plan">
    <div class="page-head">
      <div>
        <h2>定投计划</h2>
        <p>按周期自动跟踪 — 微笑曲线告诉你"摊薄成本"vs"当前净值"的真实关系</p>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建定投</el-button>
      </div>
    </div>

    <!-- 顶部统计 -->
    <el-row :gutter="12" class="summary-row">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">今日待定投</div>
          <div class="summary-value" :class="todayCount > 0 ? 'highlight' : ''">{{ todayCount }} 笔</div>
          <small>合计 ¥{{ formatMoney(todayAmount) }}</small>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">本周待定投</div>
          <div class="summary-value">{{ weekCount }} 笔</div>
          <small>合计 ¥{{ formatMoney(weekAmount) }}</small>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">累计已投</div>
          <div class="summary-value">¥{{ formatMoney(totalInvested) }}</div>
          <small>{{ executedTotal }} 期</small>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">当前累计浮盈</div>
          <div class="summary-value" :class="profitClass(totalPnl)">
            {{ totalPnl >= 0 ? '+' : '' }}¥{{ formatMoney(totalPnl) }}
          </div>
          <small :class="profitClass(totalPnlPct)">{{ formatPercent(totalPnlPct) }}</small>
        </el-card>
      </el-col>
    </el-row>

    <!-- 即将到期 -->
    <el-card v-if="upcoming.length" shadow="hover" style="margin-bottom: 16px;">
      <template #header><span style="font-weight: 600;">未来 7 天即将到期</span></template>
      <el-table :data="upcoming" stripe size="small">
        <el-table-column prop="scheduled_date" label="日期" width="120" />
        <el-table-column prop="fund_code" label="代码" width="100" />
        <el-table-column prop="fund_name" label="基金" min-width="140" show-overflow-tooltip />
        <el-table-column prop="plan_amount" label="金额" width="110" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.plan_amount) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 计划卡片列表 -->
    <el-row :gutter="12">
      <el-col v-for="p in plans" :key="p.id" :xs="24" :md="12" :lg="8">
        <el-card shadow="hover" class="plan-card" @click="openSmile(p)">
          <div class="plan-card-head">
            <div>
              <div class="plan-fund-name">{{ p.fund_name || p.fund_code }}</div>
              <div class="plan-code">{{ p.fund_code }} · {{ planTypeLabel(p.plan_type) }} · ¥{{ formatMoney(p.amount) }}/期</div>
            </div>
            <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, p)" @click.stop>
              <el-button text :icon="MoreFilled" @click.stop />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="reconcile">关联交易</el-dropdown-item>
                  <el-dropdown-item command="deactivate" divided>停用</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div class="plan-progress">
            <span>已执行 {{ p.executed_periods }} 期</span>
            <span v-if="p.target_periods">/ 目标 {{ p.target_periods }} 期</span>
            <span v-if="p.next_execution_date">· 下次 {{ p.next_execution_date }}</span>
          </div>
          <el-progress
            v-if="p.target_periods"
            :percentage="Math.min(100, Math.round(p.executed_periods / p.target_periods * 100))"
            :stroke-width="6" :show-text="false"
          />
          <el-row :gutter="8" class="plan-metrics">
            <el-col :span="8">
              <div class="metric-label">累计已投</div>
              <div class="metric-value">¥{{ formatMoney(p.cumulative_amount) }}</div>
            </el-col>
            <el-col :span="8">
              <div class="metric-label">摊薄成本</div>
              <div class="metric-value">{{ p.average_cost ? p.average_cost.toFixed(4) : '-' }}</div>
            </el-col>
            <el-col :span="8">
              <div class="metric-label">当前浮盈</div>
              <div class="metric-value" :class="profitClass(p.current_pnl_pct)">
                {{ formatPercent(p.current_pnl_pct) }}
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
      <el-col v-if="!plans.length" :span="24">
        <el-empty description='还没有定投计划，点击右上角"新建定投"开始'>
          <el-button type="primary" @click="openCreate">新建定投</el-button>
        </el-empty>
      </el-col>
    </el-row>

    <!-- 新建/编辑弹层 -->
    <el-dialog v-model="formVisible" :title="editingId ? '编辑定投' : '新建定投'" width="540px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="基金代码" required>
          <el-input v-model="form.fund_code" :disabled="!!editingId" placeholder="6位代码，如 005827" />
        </el-form-item>
        <el-form-item label="计划名称">
          <el-input v-model="form.plan_name" placeholder="可选，便于区分多个计划" />
        </el-form-item>
        <el-form-item label="周期" required>
          <el-radio-group v-model="form.plan_type">
            <el-radio-button value="daily">每个交易日</el-radio-button>
            <el-radio-button value="weekly">每周</el-radio-button>
            <el-radio-button value="biweekly">每两周</el-radio-button>
            <el-radio-button value="monthly">每月</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.plan_type === 'weekly' || form.plan_type === 'biweekly'" label="星期">
          <el-select v-model="form.day_of_period" placeholder="选择星期几" style="width: 220px;">
            <el-option v-for="(n, i) in weekdays" :key="i" :label="n" :value="i" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.plan_type === 'monthly'" label="每月几号">
          <el-input-number v-model="form.day_of_period" :min="1" :max="28" />
        </el-form-item>
        <el-form-item label="单期金额" required>
          <el-input-number v-model="form.amount" :min="100" :step="500" :precision="2" />
        </el-form-item>
        <el-form-item label="起始日" required>
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="目标总额">
          <el-input-number v-model="form.target_amount" :min="0" :step="1000" :precision="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 微笑曲线弹层 -->
    <el-dialog v-model="smileVisible" :title="smileTitle" width="1080px" top="6vh">
      <div v-if="smileData">
        <el-row :gutter="12" style="margin-bottom: 16px;">
          <el-col :xs="8" :sm="4">
            <div class="metric-label">期数</div>
            <div class="metric-value">{{ smileData.summary.executed_periods }} 期</div>
          </el-col>
          <el-col :xs="8" :sm="4">
            <div class="metric-label">累计投入</div>
            <div class="metric-value">¥{{ formatMoney(smileData.summary.cumulative_amount) }}</div>
          </el-col>
          <el-col :xs="8" :sm="4">
            <div class="metric-label">摊薄成本</div>
            <div class="metric-value">{{ smileData.summary.average_cost?.toFixed(4) }}</div>
          </el-col>
          <el-col :xs="8" :sm="4">
            <div class="metric-label">最新净值</div>
            <div class="metric-value">{{ smileData.summary.latest_nav?.toFixed(4) }}</div>
          </el-col>
          <el-col :xs="8" :sm="4">
            <div class="metric-label">当前市值</div>
            <div class="metric-value">¥{{ formatMoney(smileData.summary.current_value) }}</div>
          </el-col>
          <el-col :xs="8" :sm="4">
            <div class="metric-label">当前浮盈</div>
            <div class="metric-value" :class="profitClass(smileData.summary.current_pnl_pct)">
              {{ formatPercent(smileData.summary.current_pnl_pct) }}
            </div>
          </el-col>
        </el-row>
        <v-chart :option="smileChartOption" style="height: 480px;" autoresize />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MoreFilled, Refresh } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, ScatterChart } from 'echarts/charts'
import {
  TooltipComponent, GridComponent, LegendComponent, DataZoomComponent,
  MarkLineComponent, AxisPointerComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  createInvestmentPlan, deactivateInvestmentPlan, getInvestmentPlans,
  getInvestmentSmileCurve, getUpcomingInvestments, reconcileInvestmentPlan,
  updateInvestmentPlan,
} from '../api'

use([
  LineChart, ScatterChart, TooltipComponent, GridComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent, AxisPointerComponent, CanvasRenderer,
])

const plans = ref<any[]>([])
const upcoming = ref<any[]>([])
const loading = ref(false)

const formVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive<any>({
  fund_code: '', plan_name: '', plan_type: 'monthly',
  day_of_period: 10, amount: 1000, start_date: new Date().toISOString().slice(0, 10),
  target_amount: null, notes: '',
})

const smileVisible = ref(false)
const smileData = ref<any>(null)
const smileTitle = ref('')

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const todayStr = computed(() => new Date().toISOString().slice(0, 10))
const todayCount = computed(() =>
  upcoming.value.filter(u => u.scheduled_date === todayStr.value).length)
const todayAmount = computed(() =>
  upcoming.value
    .filter(u => u.scheduled_date === todayStr.value)
    .reduce((sum, u) => sum + Number(u.plan_amount || 0), 0))

const weekStart = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() - d.getDay() + 1)
  return d.toISOString().slice(0, 10)
})
const weekEnd = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + (7 - d.getDay()))
  return d.toISOString().slice(0, 10)
})
const weekCount = computed(() =>
  upcoming.value.filter(u => u.scheduled_date >= weekStart.value && u.scheduled_date <= weekEnd.value).length)
const weekAmount = computed(() =>
  upcoming.value
    .filter(u => u.scheduled_date >= weekStart.value && u.scheduled_date <= weekEnd.value)
    .reduce((sum, u) => sum + Number(u.plan_amount || 0), 0))

const totalInvested = computed(() =>
  plans.value.reduce((sum, p) => sum + Number(p.cumulative_amount || 0), 0))
const executedTotal = computed(() =>
  plans.value.reduce((sum, p) => sum + Number(p.executed_periods || 0), 0))
const totalPnl = computed(() =>
  plans.value.reduce((sum, p) => sum + Number(p.current_pnl || 0), 0))
const totalPnlPct = computed(() => {
  const inv = totalInvested.value
  return inv > 0 ? totalPnl.value / inv * 100 : 0
})

const smileChartOption = computed(() => {
  if (!smileData.value) return {}
  const nav = smileData.value.nav_series || []
  const points = smileData.value.execution_points || []
  const costLine = smileData.value.cost_line || []
  const avgCost = smileData.value.summary?.average_cost || 0
  return {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { top: 4, data: ['基金净值', '定投点', '摊薄成本'] },
    grid: { left: 50, right: 36, top: 36, bottom: 60 },
    xAxis: { type: 'time', axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(4) } },
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', bottom: 8, height: 22 },
    ],
    series: [
      {
        name: '基金净值', type: 'line', symbol: 'none', smooth: true,
        data: nav.map((r: any) => [r.date, r.nav]),
        lineStyle: { color: '#2563eb', width: 2 },
        areaStyle: { color: 'rgba(37,99,235,0.08)' },
        markLine: avgCost ? {
          symbol: 'none',
          lineStyle: { color: '#f59e0b', type: 'dashed', width: 2 },
          data: [{ yAxis: avgCost, name: '摊薄成本' }],
          label: { formatter: '摊薄成本 {c}', color: '#f59e0b', fontSize: 11 },
        } : undefined,
      },
      {
        name: '定投点', type: 'scatter',
        data: points.map((p: any) => [p.date, p.nav]),
        symbolSize: 10,
        itemStyle: { color: '#dc2626' },
      },
      {
        name: '摊薄成本', type: 'line',
        data: costLine.map((c: any) => [c.date, c.average_cost]),
        symbol: 'none',
        lineStyle: { color: '#16a34a', width: 1.5, type: 'dashed' },
      },
    ],
  }
})

function planTypeLabel(t: string) {
  return ({ daily: '每日', weekly: '每周', biweekly: '双周', monthly: '每月' } as any)[t] || t
}
function formatMoney(v: any) {
  return (Number(v) || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function formatPercent(v: any) {
  const n = Number(v) || 0
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function profitClass(v: any) {
  return Number(v) >= 0 ? 'up' : 'down'
}

async function loadAll() {
  loading.value = true
  try {
    const [planRes, upRes]: any = await Promise.all([
      getInvestmentPlans(true),
      getUpcomingInvestments(30),
    ])
    plans.value = planRes?.items || []
    upcoming.value = upRes?.items || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    fund_code: '', plan_name: '', plan_type: 'monthly',
    day_of_period: 10, amount: 1000,
    start_date: new Date().toISOString().slice(0, 10),
    target_amount: null, notes: '',
  })
  formVisible.value = true
}

function openEdit(p: any) {
  editingId.value = p.id
  Object.assign(form, {
    fund_code: p.fund_code, plan_name: p.plan_name, plan_type: p.plan_type,
    day_of_period: p.day_of_period, amount: p.amount, start_date: p.start_date,
    target_amount: p.target_amount, notes: p.notes,
  })
  formVisible.value = true
}

async function handleSave() {
  if (!form.fund_code || !form.amount || !form.start_date) {
    ElMessage.warning('请填写代码、金额、起始日')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateInvestmentPlan(editingId.value, form)
      ElMessage.success('已更新')
    } else {
      await createInvestmentPlan(form)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    await loadAll()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function handleAction(cmd: string, p: any) {
  if (cmd === 'edit') openEdit(p)
  else if (cmd === 'reconcile') {
    try {
      const r: any = await reconcileInvestmentPlan(p.id)
      ElMessage.success(`已关联 ${r?.matched || 0} 笔历史交易`)
      await loadAll()
    } catch { ElMessage.error('关联失败') }
  } else if (cmd === 'deactivate') {
    try {
      await ElMessageBox.confirm('确认停用此定投计划？停用后不会再生成提醒，但历史数据保留', '提示')
      await deactivateInvestmentPlan(p.id)
      ElMessage.success('已停用')
      await loadAll()
    } catch { /* 取消 */ }
  }
}

async function openSmile(p: any) {
  try {
    smileData.value = await getInvestmentSmileCurve(p.id)
    smileTitle.value = `微笑曲线 — ${p.fund_name || p.fund_code} (${planTypeLabel(p.plan_type)})`
    smileVisible.value = true
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(loadAll)
</script>

<style scoped>
.invest-plan { max-width: var(--content-max-width, 1400px); }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-head h2 { margin: 0; }
.page-head p { margin: 4px 0 0; color: var(--gray-400); font-size: 13px; }
.head-actions { display: flex; gap: 8px; }

.summary-row { margin-bottom: 16px; }
.summary-card { text-align: center; padding: 4px 0; }
.summary-label { font-size: 12px; color: var(--gray-400); text-transform: uppercase; }
.summary-value { font-size: 22px; font-weight: 700; color: var(--gray-900); margin: 6px 0 2px; }
.summary-value.highlight { color: var(--danger-500); }
.summary-card small { color: var(--gray-500); font-size: 12px; }

.plan-card { cursor: pointer; transition: all 0.15s ease; margin-bottom: 12px; }
.plan-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.plan-card-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.plan-fund-name { font-weight: 600; font-size: 15px; color: var(--gray-900); }
.plan-code { font-size: 12px; color: var(--gray-500); margin-top: 2px; }
.plan-progress { font-size: 12px; color: var(--gray-500); margin-bottom: 6px; }
.plan-metrics { margin-top: 10px; }
.metric-label { font-size: 11px; color: var(--gray-400); }
.metric-value { font-size: 14px; font-weight: 600; color: var(--gray-800); margin-top: 2px; }

.up { color: var(--danger-500); }
.down { color: var(--success-500); }
</style>
