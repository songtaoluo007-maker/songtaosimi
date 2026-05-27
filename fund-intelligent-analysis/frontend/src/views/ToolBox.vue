<template>
  <div class="toolbox">
    <div class="page-head">
      <div>
        <h2>老基民工具箱</h2>
        <p>持有时长里程碑 · 季报披露 · 同公司转换 · 节假日 · 费率体检 — 五个小工具集中入口</p>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="toolbox-tabs">
      <!-- 1. 持有时长里程碑 -->
      <el-tab-pane label="持有里程碑" name="milestones">
        <el-alert :title="milestones.summary || '加载中...'" type="info" show-icon :closable="false" style="margin-bottom: 14px;" />
        <el-card v-if="milestones.imminent?.length" shadow="hover" style="margin-bottom: 14px;">
          <template #header><span style="font-weight: 600; color: var(--danger-500);">⏰ 近 7 天即将到达里程碑/降费档</span></template>
          <el-table :data="milestones.imminent" stripe size="small">
            <el-table-column prop="fund_code" label="代码" width="100" />
            <el-table-column prop="fund_name" label="基金" min-width="160" show-overflow-tooltip />
            <el-table-column prop="holding_days" label="已持有" width="90" align="right">
              <template #default="{ row }">{{ row.holding_days }} 天</template>
            </el-table-column>
            <el-table-column label="距下个降费档" width="130" align="right">
              <template #default="{ row }">
                <strong v-if="row.days_to_fee_drop !== null" :class="row.days_to_fee_drop <= 3 ? 'text-up' : ''">
                  {{ row.days_to_fee_drop }} 天 → {{ ((row.next_fee_rate || 0) * 100).toFixed(2) }}%
                </strong>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="可节省" width="110" align="right">
              <template #default="{ row }">
                <strong v-if="row.savings_at_fee_drop !== null" class="text-up">¥{{ formatMoney(row.savings_at_fee_drop) }}</strong>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card shadow="hover">
          <template #header><span style="font-weight: 600;">全部持仓里程碑</span></template>
          <el-table :data="milestones.items" stripe>
            <el-table-column prop="fund_code" label="代码" width="100" />
            <el-table-column prop="fund_name" label="基金" min-width="160" show-overflow-tooltip />
            <el-table-column prop="holding_days" label="已持有" width="90" align="right">
              <template #default="{ row }">{{ row.holding_days }} 天</template>
            </el-table-column>
            <el-table-column label="下个里程碑" width="120" align="right">
              <template #default="{ row }">
                <span v-if="row.next_milestone">{{ row.next_milestone }} 天 · 还有 {{ row.days_to_milestone }} 天</span>
                <span v-else style="color: var(--gray-400);">已过最高</span>
              </template>
            </el-table-column>
            <el-table-column label="下个降费档" width="160" align="right">
              <template #default="{ row }">
                <span v-if="row.days_to_fee_drop !== null">
                  {{ row.days_to_fee_drop }} 天 → {{ ((row.next_fee_rate || 0) * 100).toFixed(2) }}%
                </span>
                <span v-else style="color: var(--gray-400);">无更低档或未配置</span>
              </template>
            </el-table-column>
            <el-table-column label="可节省" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.savings_at_fee_drop !== null" class="text-up">¥{{ formatMoney(row.savings_at_fee_drop) }}</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 2. 季报披露日历 -->
      <el-tab-pane label="季报披露" name="quarterly">
        <el-alert :title="quarterly.summary || '加载中...'" type="info" show-icon :closable="false" style="margin-bottom: 14px;" />
        <el-row :gutter="12">
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="window-card">
              <div class="window-label">上次披露</div>
              <template v-if="quarterly.last_window">
                <div class="window-quarter">{{ quarterly.last_window.quarter_label }}</div>
                <div class="window-range">{{ quarterly.last_window.disclosure_start }} — {{ quarterly.last_window.disclosure_end }}</div>
              </template>
              <div v-else class="window-empty">无</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="window-card highlight">
              <div class="window-label">当前披露窗口</div>
              <template v-if="quarterly.current_window">
                <div class="window-quarter">{{ quarterly.current_window.quarter_label }}</div>
                <div class="window-range">{{ quarterly.current_window.disclosure_start }} — {{ quarterly.current_window.disclosure_end }}</div>
                <div style="color: var(--danger-500); font-size: 12px; margin-top: 4px;">距结束还有 {{ quarterly.current_window.days_to_end }} 天</div>
              </template>
              <div v-else class="window-empty">未在披露窗口内</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="window-card">
              <div class="window-label">下次披露</div>
              <template v-if="quarterly.next_window">
                <div class="window-quarter">{{ quarterly.next_window.quarter_label }}</div>
                <div class="window-range">{{ quarterly.next_window.disclosure_start }} — {{ quarterly.next_window.disclosure_end }}</div>
                <div style="color: var(--brand-500); font-size: 12px; margin-top: 4px;">还有 {{ quarterly.next_window.days_to_start }} 天</div>
              </template>
              <div v-else class="window-empty">无</div>
            </el-card>
          </el-col>
        </el-row>
        <el-card v-if="quarterly.fund_disclosure_status?.length" shadow="hover" style="margin-top: 14px;">
          <template #header><span style="font-weight: 600;">持仓基金披露状态（{{ quarterly.last_window?.quarter_label }}）</span></template>
          <el-table :data="quarterly.fund_disclosure_status" stripe size="small">
            <el-table-column prop="fund_code" label="代码" width="100" />
            <el-table-column prop="fund_name" label="基金" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.has_data" type="success" size="small">已披露</el-tag>
                <el-tag v-else type="warning" size="small">缺数据</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 3. 同公司基金转换 -->
      <el-tab-pane label="同公司转换" name="switch">
        <el-card shadow="hover">
          <template #header><span style="font-weight: 600;">同公司基金转换费率计算器</span></template>
          <el-form :inline="true" :model="switchForm" label-width="80px">
            <el-form-item label="转出基金"><el-input v-model="switchForm.from_code" placeholder="如 005827" /></el-form-item>
            <el-form-item label="转入基金"><el-input v-model="switchForm.to_code" placeholder="如 110011" /></el-form-item>
            <el-form-item label="金额">
              <el-input-number v-model="switchForm.amount" :min="0" :step="1000" :precision="2" placeholder="留空 = 全部" />
            </el-form-item>
            <el-form-item label="转换费率">
              <el-input-number v-model="switchForm.convert_fee_rate" :min="0" :max="0.05" :step="0.001" :precision="4" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="switching" @click="calcSwitch">对比节省</el-button>
            </el-form-item>
          </el-form>

          <div v-if="switchResult && !switchResult.error" style="margin-top: 14px;">
            <el-alert :type="switchResult.savings > 0 ? 'success' : 'warning'" show-icon :closable="false"
                      :title="switchResult.recommendation">
              <template #default>
                <el-row :gutter="12" style="margin-top: 8px;">
                  <el-col :xs="12" :sm="6">
                    <div class="kv"><span>赎回费</span><strong>¥{{ formatMoney(switchResult.from.redemption_fee) }}</strong></div>
                  </el-col>
                  <el-col :xs="12" :sm="6">
                    <div class="kv"><span>申购费</span><strong>¥{{ formatMoney(switchResult.to.purchase_fee) }}</strong></div>
                  </el-col>
                  <el-col :xs="12" :sm="6">
                    <div class="kv"><span>直接两步总费用</span><strong>¥{{ formatMoney(switchResult.direct_total_fee) }}</strong></div>
                  </el-col>
                  <el-col :xs="12" :sm="6">
                    <div class="kv"><span>转换费用</span><strong>¥{{ formatMoney(switchResult.convert_fee) }}</strong></div>
                  </el-col>
                </el-row>
              </template>
            </el-alert>
          </div>
          <el-alert v-if="switchResult?.error" type="error" :closable="false" :title="switchResult.error" style="margin-top: 12px;" />
        </el-card>
      </el-tab-pane>

      <!-- 4. 节假日提醒 -->
      <el-tab-pane label="节假日" name="holidays">
        <el-alert :title="holidays.summary || '加载中...'" type="info" show-icon :closable="false" style="margin-bottom: 14px;" />
        <el-card v-if="holidays.items?.length" shadow="hover">
          <el-timeline>
            <el-timeline-item v-for="(h, i) in holidays.items" :key="i"
                              :type="h.is_imminent ? 'danger' : (h.is_long ? 'warning' : 'primary')"
                              :timestamp="`${h.start} → ${h.end}（${h.length} 天）`">
              <strong v-if="h.is_long">长假</strong>
              <strong v-else>假期</strong>
              · 距开始 <strong :class="h.is_imminent ? 'text-up' : ''">{{ h.days_to_start }} 天</strong>
              <div v-if="h.advice" style="margin-top: 4px; color: var(--gray-700); font-size: 13px;">{{ h.advice }}</div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
        <el-empty v-else description="近 30 天无重要假期" />
      </el-tab-pane>

      <!-- 5. 费率体检 -->
      <el-tab-pane label="费率体检" name="fee-health">
        <el-alert :title="feeHealth.summary || '加载中...'" type="info" show-icon :closable="false" style="margin-bottom: 14px;" />
        <el-row :gutter="12" style="margin-bottom: 14px;">
          <el-col :xs="12" :sm="8">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">年化总费用</div>
              <div class="summary-value highlight">¥{{ formatMoney(feeHealth.total_annual_cost) }}</div>
            </el-card>
          </el-col>
          <el-col :xs="12" :sm="8">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">加权年费率</div>
              <div class="summary-value">{{ (feeHealth.avg_rate_pct || 0).toFixed(3) }}%</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">高费率 / 缺配置</div>
              <div class="summary-value">{{ (feeHealth.high_fee_funds || []).length }} / {{ (feeHealth.missing_fee_data || []).length }}</div>
              <small>≥2% 视为高费率</small>
            </el-card>
          </el-col>
        </el-row>
        <el-card shadow="hover">
          <el-table :data="feeHealth.items" stripe>
            <el-table-column prop="fund_code" label="代码" width="100" />
            <el-table-column prop="fund_name" label="基金" min-width="160" show-overflow-tooltip />
            <el-table-column label="当前市值" width="120" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.current_value) }}</template>
            </el-table-column>
            <el-table-column label="年费率" width="100" align="right">
              <template #default="{ row }">
                <strong :class="row.is_high_fee ? 'text-up' : ''">{{ row.annual_rate_pct }}%</strong>
              </template>
            </el-table-column>
            <el-table-column label="年化费用" width="120" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.annual_cost) }}</template>
            </el-table-column>
            <el-table-column label="提示" min-width="120">
              <template #default="{ row }">
                <el-tag v-if="row.is_high_fee" type="warning" size="small">高费率</el-tag>
                <span v-else style="color: var(--gray-400);">正常</span>
              </template>
            </el-table-column>
          </el-table>
          <el-alert v-if="(feeHealth.missing_fee_data || []).length" type="warning" :closable="false" show-icon style="margin-top: 12px;"
                    :title="`以下基金未配置费率，无法纳入计算：${feeHealth.missing_fee_data.join('、')}`" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  getFeeHealth, getHolidayAlerts, getHoldingMilestones,
  getQuarterlyDisclosure, getSwitchSavings,
} from '../api'

const activeTab = ref('milestones')
const loading = ref(false)

const milestones = ref<any>({})
const quarterly = ref<any>({})
const holidays = ref<any>({})
const feeHealth = ref<any>({})

const switchForm = reactive({
  from_code: '', to_code: '', amount: 0,
  convert_fee_rate: 0.005,
})
const switching = ref(false)
const switchResult = ref<any>(null)

function formatMoney(v: any) {
  return (Number(v) || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function loadAll() {
  loading.value = true
  try {
    const [m, q, h, f]: any = await Promise.all([
      getHoldingMilestones(),
      getQuarterlyDisclosure(),
      getHolidayAlerts(),
      getFeeHealth(),
    ])
    milestones.value = m || {}
    quarterly.value = q || {}
    holidays.value = h || {}
    feeHealth.value = f || {}
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function calcSwitch() {
  if (!switchForm.from_code || !switchForm.to_code) {
    ElMessage.warning('请填写转出 / 转入基金代码')
    return
  }
  switching.value = true
  try {
    switchResult.value = await getSwitchSavings({
      from_code: switchForm.from_code,
      to_code: switchForm.to_code,
      amount: switchForm.amount > 0 ? switchForm.amount : undefined,
      convert_fee_rate: switchForm.convert_fee_rate,
    })
  } catch (e: any) {
    ElMessage.error('计算失败: ' + (e.response?.data?.detail || e.message))
    switchResult.value = null
  } finally {
    switching.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.toolbox { max-width: var(--content-max-width, 1400px); }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-head h2 { margin: 0; }
.page-head p { margin: 4px 0 0; color: var(--gray-400); font-size: 13px; }
.head-actions { display: flex; gap: 8px; }
.toolbox-tabs :deep(.el-tabs__item) { font-size: 14px; }

.window-card { text-align: center; padding: 4px 0; }
.window-card.highlight { border-color: var(--brand-300); }
.window-label { font-size: 12px; color: var(--gray-400); text-transform: uppercase; }
.window-quarter { font-size: 22px; font-weight: 700; color: var(--gray-900); margin: 6px 0 2px; }
.window-range { font-size: 12px; color: var(--gray-500); }
.window-empty { color: var(--gray-400); padding: 12px 0; }

.summary-card { text-align: center; padding: 4px 0; }
.summary-label { font-size: 12px; color: var(--gray-400); text-transform: uppercase; }
.summary-value { font-size: 22px; font-weight: 700; color: var(--gray-900); margin: 6px 0 2px; }
.summary-value.highlight { color: var(--danger-500); }
.summary-card small { color: var(--gray-500); font-size: 12px; }

.kv { display: flex; flex-direction: column; gap: 2px; padding: 6px 0; }
.kv span { font-size: 11px; color: var(--gray-500); }
.kv strong { font-size: 14px; color: var(--gray-900); font-weight: 600; }

.text-up { color: var(--danger-500); }
</style>
