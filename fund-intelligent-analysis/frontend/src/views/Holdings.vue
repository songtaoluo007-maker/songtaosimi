<template>
  <div class="holdings-page">
    <header class="page-head">
      <div>
        <div class="eyebrow">PORTFOLIO LEDGER</div>
        <h1>持仓管理</h1>
        <p>按日复盘收益、贡献和风险暴露</p>
      </div>
      <div class="head-actions">
        <el-button @click="togglePrivacy">
          <el-icon><component :is="privacyMode ? View : Hide" /></el-icon>
          {{ privacyMode ? '显示金额' : '隐藏金额' }}
        </el-button>
        <el-button :icon="Refresh" :loading="refreshingEstimates" @click="handleRefreshEstimates">刷新估值</el-button>
        <el-button @click="showGroupDialog = true">基金组</el-button>
        <el-button type="primary" :icon="Plus" @click="showAddDialog = true">手动添加</el-button>
        <el-button :icon="Camera" @click="$router.push('/ocr-import')">截图导入</el-button>
      </div>
    </header>

    <el-row :gutter="14" class="metric-row">
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>总市值</span>
          <strong>{{ privacyMoney(summary.total_value) }}</strong>
          <small>{{ summary.holding_count || holdings.length }} 只基金</small>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>当日盈亏</span>
          <strong :class="profitClass(summary.total_daily_pnl)">{{ signedPrivacyMoney(summary.total_daily_pnl) }}</strong>
          <small>{{ summary.daily_pnl_date || '暂无估值日期' }}</small>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>总盈亏</span>
          <strong :class="profitClass(summary.total_pnl)">{{ signedPrivacyMoney(summary.total_pnl) }}</strong>
          <small :class="profitClass(summary.total_pnl_ratio)">{{ signedPercent(summary.total_pnl_ratio) }}</small>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>年化 XIRR</span>
          <strong :class="profitClass(xirrMetrics.portfolio_xirr)">{{ signedPercent(xirrMetrics.portfolio_xirr) }}</strong>
          <small>现金流加权收益</small>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>最大回撤</span>
          <strong :class="drawdownClass(drawdownMetrics.portfolio?.max_dd)">{{ drawdownPercent(drawdownMetrics.portfolio?.max_dd) }}</strong>
          <small>{{ drawdownMetrics.portfolio?.recovery_days ?? 0 }} 天恢复</small>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="4">
        <div class="metric">
          <span>当前区间超额</span>
          <strong :class="profitClass(performanceCalendar.summary?.excess_return)">
            {{ signedPercent(performanceCalendar.summary?.excess_return) }}
          </strong>
          <small>相对沪深300</small>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="calendar-row">
      <el-col :xs="24" :lg="15">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>收益日历</h2>
              <p>{{ performanceCalendar.data_note || '按日期查看组合收益和贡献基金' }}</p>
            </div>
            <div class="period-tools">
              <el-radio-group v-model="calendarPeriod" size="small" @change="debouncedLoadCalendar">
                <el-radio-button label="day">当日</el-radio-button>
                <el-radio-button label="week">当周</el-radio-button>
                <el-radio-button label="month">当月</el-radio-button>
                <el-radio-button label="year">当年</el-radio-button>
                <el-radio-button label="inception">开户以来</el-radio-button>
              </el-radio-group>
              <el-date-picker v-model="calendarDate" type="date" size="small" :clearable="false" @change="debouncedLoadCalendar" />
            </div>
          </div>

          <div class="calendar-summary">
            <div>
              <span>区间收益</span>
              <strong :class="profitClass(performanceCalendar.summary?.total_pnl)">
                {{ signedPrivacyMoney(performanceCalendar.summary?.total_pnl) }}
              </strong>
            </div>
            <div>
              <span>区间收益率</span>
              <strong :class="profitClass(performanceCalendar.summary?.period_return)">
                {{ signedPercent(performanceCalendar.summary?.period_return) }}
              </strong>
            </div>
            <div>
              <span>跑赢沪深300</span>
              <strong :class="profitClass(performanceCalendar.summary?.excess_return)">
                {{ signedPercent(performanceCalendar.summary?.excess_return) }}
              </strong>
            </div>
            <div>
              <span>胜率</span>
              <strong>{{ percent(performanceCalendar.summary?.win_rate) }}</strong>
            </div>
          </div>

          <el-calendar v-model="calendarDate" class="pnl-calendar">
            <template #date-cell="{ data }">
              <div class="day-cell" :class="[dayClass(data.day), { selected: data.day === selectedDate }]" @click.stop="selectCalendarDay(data.day)">
                <span>{{ dayNumber(data.day) }}</span>
                <strong v-if="calendarMap[data.day]?.daily_pnl !== null && calendarMap[data.day]?.daily_pnl !== undefined">
                  {{ privacyCalendarMoney(calendarMap[data.day]?.daily_pnl) }}
                </strong>
                <small v-if="calendarMap[data.day]?.daily_return !== null && calendarMap[data.day]?.daily_return !== undefined">
                  {{ signedPercent(calendarMap[data.day]?.daily_return) }}
                </small>
                <small v-else class="muted">{{ calendarMap[data.day]?.status === 'rest' ? '休市' : '' }}</small>
              </div>
            </template>
          </el-calendar>
        </section>
      </el-col>

      <el-col :xs="24" :lg="9">
        <section class="panel daily-panel">
          <div class="panel-head compact">
            <div>
              <h2>当日复盘</h2>
              <p>{{ selectedDate }}</p>
            </div>
          </div>
          <div class="selected-day">
            <div>
              <span>日盈亏</span>
              <strong :class="profitClass(selectedDay?.daily_pnl)">{{ signedPrivacyMoney(selectedDay?.daily_pnl) }}</strong>
            </div>
            <div>
              <span>日收益率</span>
              <strong :class="profitClass(selectedDay?.daily_return)">{{ signedPercent(selectedDay?.daily_return) }}</strong>
            </div>
            <div>
              <span>跑赢沪深300</span>
              <strong :class="profitClass(selectedDay?.excess_return)">{{ signedPercent(selectedDay?.excess_return) }}</strong>
            </div>
          </div>
          <el-table :data="performanceCalendar.selected_contributions || []" height="330" stripe>
            <el-table-column prop="fund_name" label="基金" min-width="150" show-overflow-tooltip />
            <el-table-column label="收益率" width="90">
              <template #default="{ row }"><span :class="profitClass(row.daily_return)">{{ signedPercent(row.daily_return) }}</span></template>
            </el-table-column>
            <el-table-column label="盈亏" width="110">
              <template #default="{ row }"><span :class="profitClass(row.daily_pnl)">{{ signedPrivacyMoney(row.daily_pnl) }}</span></template>
            </el-table-column>
          </el-table>
        </section>
      </el-col>
    </el-row>

    <section v-if="groups.length" class="panel group-section">
      <div class="panel-head compact">
        <h2>基金组</h2>
        <el-button text @click="showGroupDialog = true">管理分组</el-button>
      </div>
      <div class="group-grid">
        <div v-for="g in groups" :key="g.id" class="group-card" :style="{ borderColor: g.color }">
          <div class="group-title"><span :style="{ background: g.color }"></span>{{ g.name }}</div>
          <p>{{ g.holding_count }} 只 · {{ privacyMoney(g.total_value) }}</p>
          <strong :class="profitClass(g.total_pnl)">{{ signedPrivacyMoney(g.total_pnl) }}</strong>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>基金持仓</h2>
          <p>默认按当日收益排序，可点击列头切换升降序</p>
        </div>
      </div>
      <el-table
        :data="holdings"
        stripe
        style="width: 100%"
        v-loading="loading"
        :default-sort="{ prop: 'daily_pnl_ratio', order: 'descending' }"
        @row-dblclick="goFundDetail"
      >
        <el-table-column prop="daily_pnl_ratio" label="当日收益率" width="120" sortable fixed="left">
          <template #default="{ row }">
            <strong :class="profitClass(row.daily_pnl_ratio)">{{ signedPercent(row.daily_pnl_ratio) }}</strong>
            <small class="table-sub">{{ row.daily_pnl_date || '-' }}</small>
          </template>
        </el-table-column>
        <el-table-column prop="fund_name" label="基金名称" min-width="230" fixed="left" sortable>
          <template #default="{ row }">
            <RouterLink class="fund-link" :to="`/fund/${row.fund_code}`">{{ row.fund_name || row.fund_code }}</RouterLink>
            <small class="table-sub">{{ row.fund_code }} · {{ row.fund_type || '基金' }}</small>
          </template>
        </el-table-column>
        <el-table-column prop="daily_pnl" label="当日盈亏" width="130" sortable>
          <template #default="{ row }"><span :class="profitClass(row.daily_pnl)">{{ signedPrivacyMoney(row.daily_pnl) }}</span></template>
        </el-table-column>
        <el-table-column prop="current_value" label="持仓市值" width="130" sortable>
          <template #default="{ row }">{{ privacyMoney(row.current_value) }}</template>
        </el-table-column>
        <el-table-column prop="shares" label="份额" width="120" sortable>
          <template #default="{ row }">{{ privacyShares(row.shares) }}</template>
        </el-table-column>
        <el-table-column prop="cost_amount" label="成本" width="120" sortable>
          <template #default="{ row }">{{ privacyMoney(row.cost_amount) }}</template>
        </el-table-column>
        <el-table-column prop="pnl_amount" label="持有盈亏" width="130" sortable>
          <template #default="{ row }"><span :class="profitClass(row.pnl_amount)">{{ signedPrivacyMoney(row.pnl_amount) }}</span></template>
        </el-table-column>
        <el-table-column prop="pnl_ratio" label="持有收益率" width="120" sortable>
          <template #default="{ row }"><span :class="profitClass(row.pnl_ratio)">{{ signedPercent(row.pnl_ratio) }}</span></template>
        </el-table-column>
        <el-table-column prop="xirr" label="XIRR年化" width="120" sortable>
          <template #default="{ row }">
            <span :class="profitClass(row.xirr)">{{ row.xirr === null || row.xirr === undefined ? '-' : signedPercent(row.xirr) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="max_drawdown" label="最大回撤" width="120" sortable>
          <template #default="{ row }">
            <span :class="drawdownClass(row.max_drawdown)">{{ row.max_drawdown === null || row.max_drawdown === undefined ? '-' : drawdownPercent(row.max_drawdown) }}</span>
            <small class="table-sub">{{ row.recovery_days ?? 0 }} 天恢复</small>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.source === 'manual' ? 'info' : 'warning'">
              {{ row.source === 'manual' ? '手动' : 'OCR' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/fund/${row.fund_code}`)">详情</el-button>
            <el-button size="small" @click="editHolding(row)">编辑</el-button>
            <el-popconfirm title="确认清除该持仓？" @confirm="handleDelete(row.fund_code)">
              <template #reference><el-button size="small" type="danger">清除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="showAddDialog" :title="addForm.fund_code && holdings.find(h => h.fund_code === addForm.fund_code) ? '编辑持仓' : '添加持仓'" width="520px">
      <el-form :model="addForm" label-width="90px">
        <el-form-item label="基金代码">
          <el-input v-model="addForm.fund_code" placeholder="6位基金代码" maxlength="6" @blur="onFundCodeChange(addForm.fund_code)">
            <template #suffix><el-icon v-if="searchingFund" class="is-loading"><Loading /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="基金名称" v-if="fundNameDisplay || searchingFund">
          <span :class="{ error: fundNameDisplay === '未找到该基金' }">{{ fundNameDisplay || '搜索中...' }}</span>
        </el-form-item>
        <el-form-item label="持有份额">
          <el-input-number v-model="addForm.shares" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="成本单价">
          <el-input-number v-model="addForm.cost_price" :min="0" :precision="4" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="投入金额">
          <el-input-number v-model="addForm.cost_amount" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleAdd">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showGroupDialog" title="基金组管理" width="900px">
      <div class="group-editor">
        <el-input v-model="groupForm.name" placeholder="组名，如 半导体、医药、黄金" />
        <el-input v-model="groupForm.description" placeholder="备注" />
        <el-color-picker v-model="groupForm.color" />
        <el-button type="primary" @click="handleCreateGroup">新建组</el-button>
      </div>
      <el-table :data="groups" stripe height="420">
        <el-table-column prop="name" label="组名" width="130" />
        <el-table-column prop="description" label="备注" />
        <el-table-column label="组内基金" min-width="280">
          <template #default="{ row }">
            <el-select
              :model-value="row.fund_codes"
              multiple
              filterable
              collapse-tags
              style="width: 100%;"
              @change="(codes: string[]) => handleUpdateGroupMembers(row.id, codes)"
            >
              <el-option v-for="h in holdings" :key="h.fund_code" :label="`${h.fund_code} ${h.fund_name}`" :value="h.fund_code" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="盈亏" width="120">
          <template #default="{ row }"><span :class="profitClass(row.total_pnl)">{{ signedPrivacyMoney(row.total_pnl) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="210">
          <template #default="{ row }">
            <el-popconfirm title="只删除该基金组，不删除持仓？" @confirm="handleDeleteGroup(row.id, false)">
              <template #reference><el-button size="small">删组</el-button></template>
            </el-popconfirm>
            <el-popconfirm title="确认删除该组，并清除组内所有持仓？" @confirm="handleDeleteGroup(row.id, true)">
              <template #reference><el-button size="small" type="danger">删组和持仓</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Camera, Hide, Loading, Plus, Refresh, View } from '@element-plus/icons-vue'
import {
  addHolding,
  createGroup,
  deleteGroup,
  deleteHolding,
  getGroups,
  getHoldingPerformance,
  getHoldingPerformanceCalendar,
  getHoldingDrawdownMetrics,
  getHoldingXirrMetrics,
  getHoldings,
  getHoldingsSummary,
  refreshHoldingEstimates,
  searchFundOnline,
  updateGroupMembers,
  updateHolding,
} from '../api'

const router = useRouter()
const holdings = ref<any[]>([])
const summary = ref<any>({})
const performance = ref<any[]>([])
const performanceCalendar = ref<any>({ summary: {}, days: [], selected_contributions: [] })
const xirrMetrics = ref<any>({ portfolio_xirr: 0, per_fund: [] })
const drawdownMetrics = ref<any>({ portfolio: {}, per_fund: [] })
const groups = ref<any[]>([])
const loading = ref(true)
const saving = ref(false)
const refreshingEstimates = ref(false)
const showAddDialog = ref(false)
const showGroupDialog = ref(false)
const addForm = ref({ fund_code: '', shares: 0, cost_price: 0, cost_amount: 0 })
const groupForm = ref({ name: '', description: '', color: '#2563eb' })
const searchingFund = ref(false)
const fundNameDisplay = ref('')
const privacyMode = ref(localStorage.getItem('fund-ai-privacy-mode') === '1')
const calendarPeriod = ref('month')
const calendarDate = ref(new Date())
const selectedDate = ref(formatDate(new Date()))

const calendarMap = computed<Record<string, any>>(() => {
  const map: Record<string, any> = {}
  ;(performanceCalendar.value.days || []).forEach((d: any) => { map[d.date] = d })
  return map
})
const selectedDay = computed(() => performanceCalendar.value.selected_day || calendarMap.value[selectedDate.value] || {})

function formatDate(date: Date | string) {
  const d = typeof date === 'string' ? new Date(date) : date
  const y = d.getFullYear()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${y}-${m}-${day}`
}
function dayNumber(day: string) {
  return Number(day.slice(-2))
}
function formatMoney(val: any) {
  const num = Number(val)
  if (!Number.isFinite(num)) return '0.00'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function signedMoney(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : '-'}¥${formatMoney(Math.abs(n))}`
}
function privacyMoney(val: any) {
  if (privacyMode.value) return '¥****'
  return `¥${formatMoney(val)}`
}
function signedPrivacyMoney(val: any) {
  if (privacyMode.value) return '****'
  return signedMoney(val)
}
function privacyCalendarMoney(val: any) {
  if (privacyMode.value) return '****'
  const n = Number(val) || 0
  if (Math.abs(n) >= 1000) return `${n >= 0 ? '+' : ''}${(n / 1000).toFixed(1)}k`
  return `${n >= 0 ? '+' : ''}${n.toFixed(0)}`
}
function privacyShares(val: any) {
  if (privacyMode.value) return '****'
  return (Number(val) || 0).toFixed(2)
}
function signedPercent(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function percent(val: any) {
  return `${(Number(val) || 0).toFixed(2)}%`
}
function drawdownPercent(val: any) {
  const n = Math.abs(Number(val) || 0)
  return n > 0 ? `-${n.toFixed(2)}%` : '0.00%'
}
function profitClass(val: any) {
  return Number(val || 0) >= 0 ? 'up' : 'down'
}
function drawdownClass(val: any) {
  return Math.abs(Number(val) || 0) >= 15 ? 'down' : 'up'
}
function dayClass(day: string) {
  const item = calendarMap.value[day]
  if (!item || item.daily_pnl === null || item.daily_pnl === undefined) return 'empty'
  return Number(item.daily_pnl) >= 0 ? 'gain' : 'loss'
}
function togglePrivacy() {
  privacyMode.value = !privacyMode.value
  localStorage.setItem('fund-ai-privacy-mode', privacyMode.value ? '1' : '0')
}
function selectCalendarDay(day: string) {
  selectedDate.value = day
  calendarDate.value = new Date(day)
  loadCalendar()
}
function goFundDetail(row: any) {
  if (row?.fund_code) router.push(`/fund/${row.fund_code}`)
}

async function loadCalendar() {
  selectedDate.value = formatDate(calendarDate.value)
  performanceCalendar.value = await getHoldingPerformanceCalendar({
    period: calendarPeriod.value,
    date: selectedDate.value,
  })
}
async function loadData() {
  loading.value = true
  try {
    const [h, s, perf, groupRows, xirr, drawdown] = await Promise.all([
      getHoldings(),
      getHoldingsSummary(),
      getHoldingPerformance(),
      getGroups(),
      getHoldingXirrMetrics(),
      getHoldingDrawdownMetrics(),
    ])
    xirrMetrics.value = xirr as any
    drawdownMetrics.value = drawdown as any
    const xirrByCode = new Map<string, any>((xirrMetrics.value.per_fund || []).map((m: any) => [m.fund_code, m]))
    const drawdownByCode = new Map<string, any>((drawdownMetrics.value.per_fund || []).map((m: any) => [m.fund_code, m]))
    holdings.value = (h as any[]).map((item: any) => ({
      ...item,
      ...(xirrByCode.get(item.fund_code) || {}),
      ...(drawdownByCode.get(item.fund_code) || {}),
      shares: Number(item.shares) || 0,
      cost_price: Number(item.cost_price) || 0,
      cost_amount: Number(item.cost_amount) || 0,
      current_nav: Number(item.current_nav) || 0,
      current_value: Number(item.current_value) || 0,
      pnl_amount: Number(item.pnl_amount) || 0,
      pnl_ratio: Number(item.pnl_ratio) || 0,
      daily_pnl: Number(item.daily_pnl) || 0,
      daily_pnl_ratio: Number(item.daily_pnl_ratio) || 0,
      xirr: xirrByCode.get(item.fund_code)?.xirr ?? item.xirr ?? null,
      max_drawdown: drawdownByCode.get(item.fund_code)?.max_dd ?? item.max_drawdown ?? null,
      recovery_days: drawdownByCode.get(item.fund_code)?.recovery_days ?? item.recovery_days ?? null,
    }))
    summary.value = s as any
    performance.value = perf as any[]
    groups.value = groupRows as any[]
    await loadCalendar()
  } catch (e: any) {
    ElMessage.error('持仓数据加载失败: ' + (e?.response?.data?.detail || e?.message || ''))
  } finally {
    loading.value = false
  }
}
async function handleRefreshEstimates() {
  refreshingEstimates.value = true
  try {
    await refreshHoldingEstimates()
    ElMessage.success('实时估值已刷新')
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '刷新失败')
  } finally {
    refreshingEstimates.value = false
  }
}
async function onFundCodeChange(val: string) {
  fundNameDisplay.value = ''
  const code = val?.trim()
  if (!code || code.length !== 6 || !/^\d{6}$/.test(code)) return
  searchingFund.value = true
  try {
    const res = await searchFundOnline(code) as any
    fundNameDisplay.value = res?.fund_name || '未找到该基金'
  } catch (err) {
    fundNameDisplay.value = '未找到该基金'
  } finally {
    searchingFund.value = false
  }
}
function editHolding(row: any) {
  addForm.value = { fund_code: row.fund_code, shares: row.shares, cost_price: row.cost_price, cost_amount: row.cost_amount }
  fundNameDisplay.value = row.fund_name || ''
  showAddDialog.value = true
}
async function handleAdd() {
  if (!addForm.value.fund_code) {
    ElMessage.warning('请输入基金代码')
    return
  }
  saving.value = true
  try {
    const existing = holdings.value.find(h => h.fund_code === addForm.value.fund_code)
    if (existing) await updateHolding(addForm.value.fund_code, addForm.value)
    else await addHolding(addForm.value)
    ElMessage.success('保存成功')
    showAddDialog.value = false
    addForm.value = { fund_code: '', shares: 0, cost_price: 0, cost_amount: 0 }
    fundNameDisplay.value = ''
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
async function handleDelete(code: string) {
  try {
    await deleteHolding(code)
    ElMessage.success('已清除')
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}
async function handleCreateGroup() {
  if (!groupForm.value.name) {
    ElMessage.warning('请输入组名')
    return
  }
  try {
    await createGroup(groupForm.value)
    groupForm.value = { name: '', description: '', color: '#2563eb' }
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建基金组失败')
  }
}
async function handleUpdateGroupMembers(id: number, codes: string[]) {
  try {
    await updateGroupMembers(id, codes)
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新组成员失败')
  }
}
async function handleDeleteGroup(id: number, deleteHoldingsFlag: boolean) {
  try {
    await deleteGroup(id, deleteHoldingsFlag)
    ElMessage.success(deleteHoldingsFlag ? '已删除基金组并清除组内持仓' : '已删除基金组')
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除基金组失败')
  }
}

let calendarTimer: ReturnType<typeof setTimeout> | null = null
function debouncedLoadCalendar(date?: string) {
  if (calendarTimer) clearTimeout(calendarTimer)
  calendarTimer = setTimeout(() => loadCalendar(date as any), 300)
}

onMounted(loadData)
onUnmounted(() => {
  if (calendarTimer) clearTimeout(calendarTimer)
})
</script>

<style scoped>
.holdings-page {
  max-width: var(--content-max-width);
}

/* Header - use page-header pattern */
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.page-head h1 {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 700;
  color: var(--gray-900);
  letter-spacing: -0.01em;
}

.page-head p {
  margin: 0;
  color: var(--gray-500);
  font-size: var(--text-sm);
}

.eyebrow {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--gray-400);
}

.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Metric Cards */
.metric-row,
.calendar-row {
  margin-bottom: var(--space-4);
}

.metric {
  background: #fff;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  min-height: 108px;
  transition: all var(--transition-base);
}

.metric:hover {
  border-color: var(--brand-200);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.metric span {
  display: block;
  font-size: var(--text-xs);
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.metric strong {
  display: block;
  margin: 10px 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: var(--gray-900);
  font-variant-numeric: tabular-nums;
}

.metric small {
  display: block;
  font-size: var(--text-xs);
  color: var(--gray-400);
}

/* Panel */
.panel {
  background: #fff;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: var(--space-4);
}

.panel-head.compact {
  align-items: center;
}

.panel-head h2 {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--gray-800);
}

.panel-head p {
  margin: 2px 0 0;
  font-size: var(--text-xs);
  color: var(--gray-400);
}

.period-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

/* Calendar */
.calendar-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.calendar-summary div,
.selected-day div {
  background: var(--gray-50);
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-md);
  padding: 12px;
  transition: all var(--transition-fast);
}

.calendar-summary div:hover,
.selected-day div:hover {
  border-color: var(--gray-200);
}

.calendar-summary span,
.selected-day span {
  display: block;
  font-size: var(--text-xs);
  color: var(--gray-400);
}

.calendar-summary strong,
.selected-day strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-800);
}

.pnl-calendar :deep(.el-calendar-table .el-calendar-day) {
  height: 82px;
  padding: 4px;
}

.day-cell {
  height: 100%;
  border-radius: var(--radius-sm);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.day-cell span {
  font-size: 12px;
  color: var(--gray-400);
}

.day-cell strong {
  font-size: 13px;
  font-weight: 600;
}

.day-cell small {
  font-size: 11px;
}

.day-cell.gain {
  background: #FEF2F2;
}

.day-cell.gain strong,
.day-cell.gain small {
  color: var(--danger-500);
}

.day-cell.loss {
  background: #F0FDF4;
}

.day-cell.loss strong,
.day-cell.loss small {
  color: var(--success-500);
}

.day-cell.empty {
  background: var(--gray-50);
}

.day-cell.selected {
  border-color: var(--brand-500);
  box-shadow: inset 0 0 0 1px var(--brand-500);
}

.daily-panel {
  min-height: 100%;
}

.selected-day {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

/* Groups */
.group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-3);
}

.group-card {
  border: 1px solid var(--gray-200);
  border-left: 4px solid var(--gray-300);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  transition: all var(--transition-fast);
}

.group-card:hover {
  box-shadow: var(--shadow-md);
}

.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: var(--text-sm);
}

.group-title span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.group-card p {
  margin: 8px 0;
  font-size: var(--text-xs);
  color: var(--gray-400);
}

.group-card strong {
  font-size: var(--text-lg);
}

.group-editor {
  display: grid;
  grid-template-columns: 1fr 1fr auto auto;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  align-items: center;
}

/* Links */
.fund-link {
  color: var(--brand-600);
  font-weight: 600;
  text-decoration: none;
}

.fund-link:hover {
  color: var(--brand-500);
  text-decoration: underline;
}

.table-sub {
  display: block;
  color: var(--gray-400);
  font-size: var(--text-xs);
  margin-top: 2px;
}

/* Colors */
.up { color: var(--danger-500) !important; }
.down { color: var(--success-500) !important; }
.muted { color: var(--gray-400) !important; }
.error { color: var(--danger-500); font-weight: 600; }

/* Group section */
.group-section {
  margin-bottom: var(--space-4);
}

/* Responsive */
@media (max-width: 980px) {
  .page-head {
    display: grid;
  }
  .calendar-summary,
  .selected-day {
    grid-template-columns: 1fr;
  }
  .group-editor {
    grid-template-columns: 1fr;
  }
}
</style>
