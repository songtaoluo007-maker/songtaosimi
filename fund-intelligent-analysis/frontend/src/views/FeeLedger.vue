<template>
  <div class="fee-ledger">
    <div class="page-head">
      <div>
        <h2>费率账本</h2>
        <p>10 年管理费可能吃掉 14% 收益 — 让"长期被扣的真实成本"可见</p>
      </div>
      <div class="head-actions">
        <el-select v-model="selectedYear" size="small" style="width: 110px;" @change="loadLedger">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y} 年`" :value="y" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="loadLedger">刷新</el-button>
        <el-button type="primary" :loading="accruing" @click="runAccrual">立即计提今日</el-button>
      </div>
    </div>

    <!-- 顶部统计 -->
    <el-row :gutter="12" class="summary-row">
      <el-col :xs="12" :sm="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">{{ ledger.year || selectedYear }}年累计被扣</div>
          <div class="summary-value highlight">¥{{ formatMoney(ledger.total_fee) }}</div>
          <small>包含管理费/托管费/销售服务费</small>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">平均组合规模</div>
          <div class="summary-value">¥{{ formatMoney(ledger.avg_total_value) }}</div>
          <small>用于年化拖累计算</small>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">费率拖累（按已计提天数）</div>
          <div class="summary-value" :class="(ledger.drag_pct || 0) > 1 ? 'highlight' : ''">
            {{ (ledger.drag_pct || 0).toFixed(3) }}%
          </div>
          <small>累计费用 / 平均组合市值</small>
        </el-card>
      </el-col>
    </el-row>

    <el-alert v-if="ledger.message" :title="ledger.message" type="info" show-icon
              :closable="false" style="margin-bottom: 16px;" />

    <el-row :gutter="12">
      <el-col :xs="24" :lg="14">
        <el-card shadow="hover">
          <template #header><span style="font-weight: 600;">按基金累计费用</span></template>
          <el-table :data="ledger.by_fund || []" stripe height="380">
            <el-table-column label="代码" prop="fund_code" width="100" />
            <el-table-column label="基金" prop="fund_name" min-width="160" show-overflow-tooltip />
            <el-table-column label="管理费" width="110" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.mgmt_fee) }}</template>
            </el-table-column>
            <el-table-column label="托管费" width="110" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.custody_fee) }}</template>
            </el-table-column>
            <el-table-column label="销售费" width="110" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.sales_fee) }}</template>
            </el-table-column>
            <el-table-column label="合计" width="110" align="right">
              <template #default="{ row }">
                <strong>¥{{ formatMoney(row.total_fee) }}</strong>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button text size="small" @click="openSchedule(row.fund_code)">配置费率</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="hover">
          <template #header><span style="font-weight: 600;">月度费率趋势</span></template>
          <v-chart v-if="(ledger.by_month || []).length" :option="monthlyChartOption"
                   style="height: 320px;" autoresize />
          <div v-else class="empty-state">本年度暂无计提数据</div>
        </el-card>

        <el-card shadow="hover" style="margin-top: 12px;">
          <template #header><span style="font-weight: 600;">赎回费预估器</span></template>
          <el-form label-width="90px" size="small">
            <el-form-item label="基金代码">
              <el-input v-model="redeemForm.fund_code" placeholder="6位代码" />
            </el-form-item>
            <el-form-item label="赎回份额">
              <el-input-number v-model="redeemForm.shares" :min="0" :step="100" :precision="2" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="small" :loading="estimating" @click="handleEstimate">预估扣费</el-button>
            </el-form-item>
          </el-form>
          <el-alert v-if="estimateResult" :type="estimateResult.matched_rate === 0 ? 'success' : 'warning'"
                    show-icon :closable="false">
            <template #title>持有 {{ estimateResult.holding_days }} 天 · 费率 {{ estimateResult.matched_rate_pct }}%</template>
            <template #default>
              <p style="margin: 4px 0;">
                赎回 ¥{{ formatMoney(estimateResult.redeem_amount) }}，扣费
                <strong style="color: var(--danger-500);">¥{{ formatMoney(estimateResult.fee_amount) }}</strong>，
                到手 ¥{{ formatMoney(estimateResult.net_amount) }}
              </p>
              <p v-if="estimateResult.warning" style="margin: 4px 0; font-size: 12px; color: var(--gray-600);">
                {{ estimateResult.warning }}
              </p>
            </template>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置费率弹层 -->
    <el-dialog v-model="scheduleVisible" :title="`配置费率 — ${scheduleForm.fund_code}`" width="560px">
      <el-form :model="scheduleForm" label-width="140px">
        <el-form-item label="管理费率（年）">
          <el-input-number v-model="scheduleForm.management_fee_rate" :min="0" :max="0.05"
                           :precision="5" :step="0.001" />
          <span style="margin-left: 8px; color: var(--gray-500); font-size: 12px;">小数，如 0.015 = 1.5%</span>
        </el-form-item>
        <el-form-item label="托管费率（年）">
          <el-input-number v-model="scheduleForm.custody_fee_rate" :min="0" :max="0.01"
                           :precision="5" :step="0.0005" />
        </el-form-item>
        <el-form-item label="销售服务费率（年）">
          <el-input-number v-model="scheduleForm.sales_service_fee_rate" :min="0" :max="0.01"
                           :precision="5" :step="0.0005" />
        </el-form-item>
        <el-form-item label="申购费率（基础）">
          <el-input-number v-model="scheduleForm.purchase_fee_rate" :min="0" :max="0.05"
                           :precision="5" :step="0.001" />
        </el-form-item>
        <el-form-item label="申购费折扣">
          <el-input-number v-model="scheduleForm.purchase_fee_discount" :min="0" :max="1"
                           :precision="3" :step="0.05" />
          <span style="margin-left: 8px; color: var(--gray-500); font-size: 12px;">天天基金常 0.1（即 1 折）</span>
        </el-form-item>
        <el-form-item label="赎回费档（JSON）">
          <el-input v-model="scheduleForm.redemption_fee_text" type="textarea" :rows="4"
                    placeholder='[{"min_days":0,"max_days":6,"rate":0.015},{"min_days":7,"max_days":29,"rate":0.005},{"min_days":30,"max_days":99999,"rate":0}]' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scheduleVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingSchedule" @click="handleSaveSchedule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  estimateRedemption, getFeeSchedule, getYearlyLedger,
  runFeeAccrual, saveFeeSchedule,
} from '../api'

use([BarChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const today = new Date()
const selectedYear = ref(today.getFullYear())
const yearOptions = computed(() => {
  const arr = []
  for (let y = today.getFullYear(); y >= today.getFullYear() - 4; y--) arr.push(y)
  return arr
})

const loading = ref(false)
const accruing = ref(false)
const ledger = ref<any>({})

const redeemForm = reactive({ fund_code: '', shares: 0 })
const estimateResult = ref<any>(null)
const estimating = ref(false)

const scheduleVisible = ref(false)
const savingSchedule = ref(false)
const scheduleForm = reactive<any>({
  fund_code: '',
  management_fee_rate: 0.015,
  custody_fee_rate: 0.0025,
  sales_service_fee_rate: 0,
  purchase_fee_rate: 0.012,
  purchase_fee_discount: 0.1,
  redemption_fee_text: '[{"min_days":0,"max_days":6,"rate":0.015},{"min_days":7,"max_days":29,"rate":0.005},{"min_days":30,"max_days":99999,"rate":0}]',
})

const monthlyChartOption = computed(() => ({
  animation: false,
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 20, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: (ledger.value.by_month || []).map((m: any) => m.month?.slice(5)),
    axisLabel: { fontSize: 11 },
  },
  yAxis: { type: 'value', axisLabel: { formatter: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0) } },
  series: [{
    type: 'bar',
    data: (ledger.value.by_month || []).map((m: any) => m.total_fee),
    itemStyle: { color: '#dc2626' },
    barWidth: '60%',
  }],
}))

function formatMoney(v: any) {
  return (Number(v) || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function loadLedger() {
  loading.value = true
  try {
    ledger.value = await getYearlyLedger(selectedYear.value)
  } finally {
    loading.value = false
  }
}

async function runAccrual() {
  accruing.value = true
  try {
    const res: any = await runFeeAccrual()
    ElMessage.success(`计提完成：新增 ${res.inserted || 0} / 更新 ${res.updated || 0} 条`)
    await loadLedger()
  } catch (e: any) {
    ElMessage.error('计提失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    accruing.value = false
  }
}

async function handleEstimate() {
  if (!redeemForm.fund_code) {
    ElMessage.warning('请输入基金代码')
    return
  }
  estimating.value = true
  try {
    estimateResult.value = await estimateRedemption(redeemForm.fund_code, {
      redeem_shares: redeemForm.shares > 0 ? redeemForm.shares : undefined,
    })
  } catch (e: any) {
    ElMessage.error('预估失败: ' + (e.response?.data?.detail || e.message))
    estimateResult.value = null
  } finally {
    estimating.value = false
  }
}

async function openSchedule(fundCode: string) {
  scheduleForm.fund_code = fundCode
  try {
    const existing: any = await getFeeSchedule(fundCode)
    Object.assign(scheduleForm, {
      management_fee_rate: existing.management_fee_rate ?? 0.015,
      custody_fee_rate: existing.custody_fee_rate ?? 0.0025,
      sales_service_fee_rate: existing.sales_service_fee_rate ?? 0,
      purchase_fee_rate: existing.purchase_fee_rate ?? 0.012,
      purchase_fee_discount: existing.purchase_fee_discount ?? 0.1,
      redemption_fee_text: JSON.stringify(existing.redemption_fee_schedule || []),
    })
  } catch {
    // 第一次配置，保留默认值
  }
  scheduleVisible.value = true
}

async function handleSaveSchedule() {
  savingSchedule.value = true
  try {
    let redemption: any[] = []
    try { redemption = JSON.parse(scheduleForm.redemption_fee_text || '[]') }
    catch { ElMessage.error('赎回费档 JSON 解析失败'); savingSchedule.value = false; return }

    await saveFeeSchedule(scheduleForm.fund_code, {
      management_fee_rate: scheduleForm.management_fee_rate,
      custody_fee_rate: scheduleForm.custody_fee_rate,
      sales_service_fee_rate: scheduleForm.sales_service_fee_rate,
      purchase_fee_rate: scheduleForm.purchase_fee_rate,
      purchase_fee_discount: scheduleForm.purchase_fee_discount,
      redemption_fee_schedule: redemption,
    })
    ElMessage.success('已保存')
    scheduleVisible.value = false
    await loadLedger()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingSchedule.value = false
  }
}

onMounted(loadLedger)
</script>

<style scoped>
.fee-ledger { max-width: var(--content-max-width, 1400px); }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-head h2 { margin: 0; }
.page-head p { margin: 4px 0 0; color: var(--gray-400); font-size: 13px; }
.head-actions { display: flex; gap: 8px; align-items: center; }

.summary-row { margin-bottom: 16px; }
.summary-card { text-align: center; padding: 4px 0; }
.summary-label { font-size: 12px; color: var(--gray-400); text-transform: uppercase; }
.summary-value { font-size: 24px; font-weight: 700; color: var(--gray-900); margin: 6px 0 2px; }
.summary-value.highlight { color: var(--danger-500); }
.summary-card small { color: var(--gray-500); font-size: 12px; }
.empty-state { height: 200px; display: flex; align-items: center; justify-content: center; color: var(--gray-400); }
</style>
