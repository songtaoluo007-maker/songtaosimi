<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0;">持仓管理</h2>
      <div>
        <el-button @click="togglePrivacy">
          <el-icon><component :is="privacyMode ? View : Hide" /></el-icon>
          {{ privacyMode ? '显示金额' : '隐藏金额' }}
        </el-button>
        <el-button :loading="refreshingEstimates" @click="handleRefreshEstimates">刷新实时估值</el-button>
        <el-button @click="showGroupDialog = true">基金组管理</el-button>
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon> 手动添加
        </el-button>
        <el-button @click="$router.push('/ocr-import')">
          <el-icon><Camera /></el-icon> 截图导入
        </el-button>
      </div>
    </div>

    <!-- 汇总统计 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">总市值</div>
          <div style="font-size: 22px; font-weight: bold;">{{ privacyMoney(summary.total_value) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">当日盈亏</div>
          <div :style="{ fontSize: '22px', fontWeight: 'bold', color: summary.total_daily_pnl >= 0 ? '#f56c6c' : '#67c23a' }">
            {{ signedPrivacyMoney(summary.total_daily_pnl) }}
          </div>
          <div style="color: #909399; font-size: 12px;">{{ summary.daily_pnl_date || '待刷新/导入' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">总盈亏</div>
          <div :style="{ fontSize: '22px', fontWeight: 'bold', color: summary.total_pnl >= 0 ? '#f56c6c' : '#67c23a' }">
            {{ signedPrivacyMoney(summary.total_pnl) }}
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">盈亏比例</div>
          <div :style="{ fontSize: '22px', fontWeight: 'bold', color: summary.total_pnl_ratio >= 0 ? '#f56c6c' : '#67c23a' }">
            {{ summary.total_pnl_ratio >= 0 ? '+' : '' }}{{ summary.total_pnl_ratio }}%
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-bottom: 20px;">
      <template #header><span style="font-weight: bold;">区间表现 / 沪深300对比</span></template>
      <el-table :data="performance" stripe>
        <el-table-column prop="label" label="区间" width="100" />
        <el-table-column label="组合收益">
          <template #default="{ row }"><span :style="{ color: row.portfolio_return >= 0 ? '#f56c6c' : '#67c23a' }">{{ signed(row.portfolio_return) }}%</span></template>
        </el-table-column>
        <el-table-column label="沪深300">
          <template #default="{ row }"><span :style="{ color: row.hs300_return >= 0 ? '#f56c6c' : '#67c23a' }">{{ signed(row.hs300_return) }}%</span></template>
        </el-table-column>
        <el-table-column label="超额收益">
          <template #default="{ row }"><span :style="{ color: row.excess_return >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">{{ signed(row.excess_return) }}%</span></template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180" />
      </el-table>
    </el-card>

    <el-card v-if="groups.length" shadow="hover" style="margin-bottom: 20px;">
      <template #header><span style="font-weight: bold;">基金组</span></template>
      <el-row :gutter="12">
        <el-col :xs="24" :sm="12" :lg="6" v-for="g in groups" :key="g.id">
          <div class="group-card" :style="{ borderColor: g.color }">
            <div class="group-title"><span :style="{ background: g.color }"></span>{{ g.name }}</div>
            <div>基金数：{{ g.holding_count }}</div>
            <div>市值：{{ privacyMoney(g.total_value) }}</div>
            <div :style="{ color: g.total_pnl >= 0 ? '#f56c6c' : '#67c23a' }">盈亏：{{ signedPrivacyMoney(g.total_pnl) }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 持仓表格 -->
    <el-card shadow="hover">
      <el-table
        :data="holdings"
        stripe
        style="width: 100%"
        v-loading="loading"
        :default-sort="{ prop: 'daily_pnl', order: 'descending' }"
      >
        <el-table-column prop="fund_code" label="基金代码" width="100" />
        <el-table-column prop="fund_name" label="基金名称" min-width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/fund/${row.fund_code}`)">
              {{ row.fund_name || row.fund_code }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="daily_pnl" label="当日收益" width="130" sortable>
          <template #default="{ row }">
            <div :style="{ color: row.daily_pnl >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 700 }">
              {{ signedPrivacyMoney(row.daily_pnl) }}
            </div>
            <div style="font-size: 12px; color: #909399;">{{ row.daily_pnl_date || '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="份额" width="110">
          <template #default="{ row }">{{ privacyShares(row.shares) }}</template>
        </el-table-column>
        <el-table-column label="成本" width="110">
          <template #default="{ row }">{{ privacyMoney(row.cost_amount) }}</template>
        </el-table-column>
        <el-table-column label="现值" width="110">
          <template #default="{ row }">{{ privacyMoney(row.current_value) }}</template>
        </el-table-column>
        <el-table-column label="盈亏" width="140">
          <template #default="{ row }">
            <span :style="{ color: row.pnl_amount >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
              {{ signedPrivacyMoney(row.pnl_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="盈亏%" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.pnl_ratio >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
              {{ row.pnl_ratio >= 0 ? '+' : '' }}{{ row.pnl_ratio?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="100">
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
              <template #reference>
                <el-button size="small" type="danger">清除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加持仓对话框 -->
    <el-dialog v-model="showAddDialog" title="添加持仓" width="500px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="基金代码">
          <el-input v-model="addForm.fund_code" placeholder="6位基金代码" maxlength="6" @blur="onFundCodeChange(addForm.fund_code)">
            <template #suffix>
              <el-icon v-if="searchingFund" class="is-loading"><Loading /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="基金名称" v-if="fundNameDisplay || searchingFund">
          <span v-if="fundNameDisplay" :style="{ color: fundNameDisplay === '未找到该基金' ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
            {{ fundNameDisplay }}
          </span>
          <span v-else-if="searchingFund" style="color: #909399;">搜索中...</span>
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
        <el-button type="primary" :loading="saving" @click="handleAdd">确认添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showGroupDialog" title="基金组管理" width="860px">
      <div style="display: flex; gap: 10px; margin-bottom: 14px;">
        <el-input v-model="groupForm.name" placeholder="组名，如 半导体、医药、港股" />
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
        <el-table-column label="盈亏" width="110">
          <template #default="{ row }">{{ signedPrivacyMoney(row.total_pnl) }}</template>
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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Hide, Loading, View } from '@element-plus/icons-vue'
import { getHoldings, getHoldingsSummary, addHolding, updateHolding, deleteHolding, searchFundOnline, refreshHoldingEstimates, getHoldingPerformance, getGroups, createGroup, updateGroupMembers, deleteGroup } from '../api'

const holdings = ref<any[]>([])
const summary = ref<any>({})
const loading = ref(true)
const saving = ref(false)
const showAddDialog = ref(false)
const showGroupDialog = ref(false)
const addForm = ref({ fund_code: '', shares: 0, cost_price: 0, cost_amount: 0 })
const groupForm = ref({ name: '', description: '', color: '#2f6fef' })
const searchingFund = ref(false)
const fundNameDisplay = ref('')
const refreshingEstimates = ref(false)
const performance = ref<any[]>([])
const groups = ref<any[]>([])
const privacyMode = ref(localStorage.getItem('fund-ai-privacy-mode') === '1')

const onFundCodeChange = async (val: string) => {
  fundNameDisplay.value = ''
  const code = val?.trim()
  if (!code || code.length !== 6 || !/^\d{6}$/.test(code)) return

  searchingFund.value = true
  try {
    const res = await searchFundOnline(code) as any
    if (res?.fund_name) {
      fundNameDisplay.value = res.fund_name
    } else {
      fundNameDisplay.value = '未找到该基金'
    }
  } catch (err) {
    fundNameDisplay.value = '未找到该基金'
  } finally {
    searchingFund.value = false
  }
}

function formatMoney(val: any) {
  const num = Number(val)
  if (!num && num !== 0) return '0.00'  // NaN guard
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function togglePrivacy() {
  privacyMode.value = !privacyMode.value
  localStorage.setItem('fund-ai-privacy-mode', privacyMode.value ? '1' : '0')
}

function privacyMoney(val: any) {
  if (privacyMode.value) return '¥****'
  return `¥${formatMoney(val)}`
}

function privacyShares(val: any) {
  if (privacyMode.value) return '****'
  const n = Number(val) || 0
  return n.toFixed(2)
}

async function loadData() {
  loading.value = true
  try {
    const [h, s] = await Promise.all([getHoldings(), getHoldingsSummary()])
    // Ensure all numeric fields are proper JavaScript numbers
    holdings.value = (h as any[]).map((item: any) => ({
      ...item,
      shares: Number(item.shares) || 0,
      cost_price: Number(item.cost_price) || 0,
      cost_amount: Number(item.cost_amount) || 0,
      current_nav: Number(item.current_nav) || 0,
      current_value: Number(item.current_value) || 0,
      pnl_amount: Number(item.pnl_amount) || 0,
      pnl_ratio: Number(item.pnl_ratio) || 0,
      daily_pnl: Number(item.daily_pnl) || 0,
      daily_pnl_ratio: Number(item.daily_pnl_ratio) || 0,
    }))
    summary.value = s as any
    performance.value = await getHoldingPerformance() as any[]
    groups.value = await getGroups() as any[]
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function signed(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
}

function signedMoney(val: any) {
  const n = Number(val) || 0
  return `${n >= 0 ? '+' : '-'}¥${formatMoney(Math.abs(n))}`
}

function signedPrivacyMoney(val: any) {
  if (privacyMode.value) return '****'
  return signedMoney(val)
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

async function handleCreateGroup() {
  if (!groupForm.value.name) {
    ElMessage.warning('请输入组名')
    return
  }
  await createGroup(groupForm.value)
  groupForm.value = { name: '', description: '', color: '#2f6fef' }
  await loadData()
}

async function handleUpdateGroupMembers(id: number, codes: string[]) {
  await updateGroupMembers(id, codes)
  await loadData()
}

async function handleDeleteGroup(id: number, deleteHoldingsFlag: boolean) {
  await deleteGroup(id, deleteHoldingsFlag)
  ElMessage.success(deleteHoldingsFlag ? '已删除基金组并清除组内持仓' : '已删除基金组')
  await loadData()
}

function editHolding(row: any) {
  addForm.value = { fund_code: row.fund_code, shares: row.shares, cost_price: row.cost_price, cost_amount: row.cost_amount }
  showAddDialog.value = true
}

async function handleAdd() {
  if (!addForm.value.fund_code) {
    ElMessage.warning('请输入基金代码')
    return
  }
  saving.value = true
  try {
    // 先检查是否已有持仓
    const existing = holdings.value.find(h => h.fund_code === addForm.value.fund_code)
    if (existing) {
      await updateHolding(addForm.value.fund_code, addForm.value)
    } else {
      await addHolding(addForm.value)
    }
    ElMessage.success('操作成功')
    showAddDialog.value = false
    addForm.value = { fund_code: '', shares: 0, cost_price: 0, cost_amount: 0 }
    fundNameDisplay.value = ''
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
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

onMounted(loadData)
</script>

<style scoped>
.group-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  line-height: 1.9;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
}
.group-title span {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
</style>
