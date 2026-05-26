<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0;">交易记录</h2>
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon> 新增交易
      </el-button>
    </div>

    <!-- 统计 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">总买入</div>
          <div style="font-size: 20px; font-weight: bold; color: #f56c6c;">¥{{ (stats.buy_total ?? 0).toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">总卖出</div>
          <div style="font-size: 20px; font-weight: bold; color: #67c23a;">¥{{ (stats.sell_total ?? 0).toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px;">总手续费</div>
          <div style="font-size: 20px; font-weight: bold;">¥{{ (stats.fee_total ?? 0).toLocaleString() }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选 -->
    <el-card shadow="hover" style="margin-bottom: 20px;">
      <el-form :inline="true">
        <el-form-item label="基金代码">
          <el-input v-model="filterFundCode" placeholder="输入基金代码" clearable style="width: 120px;" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filterType" clearable placeholder="全部" style="width: 100px;">
            <el-option label="买入" value="买入" />
            <el-option label="卖出" value="卖出" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTrades">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 交易表格 -->
    <el-card shadow="hover">
      <el-table :data="trades" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="trade_date" label="交易日期" width="120" />
        <el-table-column prop="fund_code" label="基金代码" width="100" />
        <el-table-column prop="fund_name" label="基金名称" min-width="160" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.trade_type === '买入' ? 'danger' : 'success'">{{ row.trade_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="份额" width="100">
          <template #default="{ row }">{{ row.shares?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="净值" width="80">
          <template #default="{ row }">{{ row.nav_price?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="110">
          <template #default="{ row }">¥{{ row.amount?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="80">
          <template #default="{ row }">¥{{ Number(row.fee || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="120" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该交易记录？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && trades.length === 0" description="暂无交易记录，可手动新增或从截图导入" />
    </el-card>

    <!-- 新增交易对话框 -->
    <el-dialog v-model="showAddDialog" :title="editingId ? '编辑交易' : '新增交易'" width="500px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="基金代码">
          <el-input v-model="addForm.fund_code" placeholder="6位基金代码" maxlength="6" />
        </el-form-item>
        <el-form-item label="交易类型">
          <el-radio-group v-model="addForm.trade_type">
            <el-radio value="买入">买入</el-radio>
            <el-radio value="卖出">卖出</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="份额">
          <el-input-number v-model="addForm.shares" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="成交净值">
          <el-input-number v-model="addForm.nav_price" :min="0" :precision="4" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="成交金额">
          <el-input-number v-model="addForm.amount" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="手续费">
          <el-input-number v-model="addForm.fee" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="交易日期">
          <el-date-picker v-model="addForm.trade_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="addForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTrades, addTrade, updateTrade, deleteTrade, getTradeStats } from '../api'

const trades = ref<any[]>([])
const stats = ref<any>({})
const loading = ref(true)
const saving = ref(false)
const showAddDialog = ref(false)
const filterFundCode = ref('')
const filterType = ref('')
const editingId = ref<number | null>(null)
const addForm = ref({
  fund_code: '', trade_type: '买入', shares: 0, nav_price: 0, amount: 0, fee: 0,
  trade_date: new Date().toISOString().slice(0, 10), note: '',
})

async function loadTrades() {
  loading.value = true
  try {
    const params: any = {}
    if (filterFundCode.value) params.fund_code = filterFundCode.value
    if (filterType.value) params.trade_type = filterType.value
    const [t, s] = await Promise.all([getTrades(params), getTradeStats()])
    trades.value = t as any
    stats.value = s as any
  } catch (e: any) {
    ElMessage.error('交易记录加载失败: ' + (e?.response?.data?.detail || e?.message || ''))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editingId.value = null
  addForm.value = { fund_code: '', trade_type: '买入', shares: 0, nav_price: 0, amount: 0, fee: 0, trade_date: new Date().toISOString().slice(0, 10), note: '' }
}

function openAddDialog() {
  resetForm()
  showAddDialog.value = true
}

function handleEdit(row: any) {
  editingId.value = row.id
  addForm.value = {
    fund_code: row.fund_code,
    trade_type: row.trade_type,
    shares: Number(row.shares) || 0,
    nav_price: Number(row.nav_price) || 0,
    amount: Number(row.amount) || 0,
    fee: Number(row.fee) || 0,
    trade_date: row.trade_date || new Date().toISOString().slice(0, 10),
    note: row.note || '',
  }
  showAddDialog.value = true
}

async function handleSave() {
  if (!addForm.value.fund_code || !addForm.value.trade_date) {
    ElMessage.warning('请填写基金代码和交易日期')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateTrade(editingId.value, addForm.value)
      ElMessage.success('交易记录已更新')
    } else {
      await addTrade(addForm.value)
      ElMessage.success('交易记录已添加')
    }
    showAddDialog.value = false
    resetForm()
    await loadTrades()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deleteTrade(id)
    ElMessage.success('交易记录已删除')
    await loadTrades()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadTrades)
</script>
