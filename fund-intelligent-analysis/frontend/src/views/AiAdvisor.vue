<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0;">AI投资顾问</h2>
      <el-button type="primary" :loading="generating" @click="handleGenerate">
        <el-icon><MagicStick /></el-icon> 立即生成建议
      </el-button>
    </div>

    <el-alert
      title="尾盘建议会在每个交易日 14:30 自动刷新行情、基金估值和新闻后生成。AI建议仅供个人复盘和决策辅助，不构成收益承诺。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <!-- 最新建议 -->
    <el-card v-if="latestAdvice && latestAdvice.actions" shadow="hover" style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold; font-size: 16px;">
            {{ adviceTitle }} ({{ latestAdvice.advice_date }} {{ latestAdvice.advice_time }})
          </span>
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-tag :type="marketViewType">{{ marketViewText }}</el-tag>
            <el-tag :type="riskType">风险：{{ riskText }}</el-tag>
          </div>
        </div>
      </template>

      <el-row :gutter="12" style="margin-bottom: 16px;">
        <el-col :span="6">
          <el-statistic title="持仓数量" :value="dataQuality.holdings_count || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="近新闻数" :value="dataQuality.recent_news_count || 0" />
        </el-col>
        <el-col :span="6">
          <div class="quality-label">指数时间</div>
          <div class="quality-value">{{ dataQuality.latest_index_time || '暂无' }}</div>
        </el-col>
        <el-col :span="6">
          <div class="quality-label">估值时间</div>
          <div class="quality-value">{{ dataQuality.latest_fund_estimate_time || '暂无' }}</div>
        </el-col>
      </el-row>

      <div v-if="opportunities.length" style="margin-bottom: 16px;">
        <div style="font-weight: bold; margin-bottom: 10px;">未持仓机会提示</div>
        <div
          v-for="item in opportunities"
          :key="`${item.board_type}-${item.name}`"
          style="margin-bottom: 12px; padding: 12px; border-radius: 8px; border: 1px solid #e4e7ed; background: #fcfcfd;"
        >
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px;">
            <div>
              <span style="font-weight: bold; font-size: 15px;">{{ item.name }}</span>
              <el-tag size="small" style="margin-left: 8px;">{{ boardTypeLabel(item.board_type) }}</el-tag>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-tag :type="opportunityType(item.action)" size="large" effect="dark">
                {{ opportunityLabel(item.action) }}
                <span v-if="item.suggested_position_ratio"> {{ (item.suggested_position_ratio * 100).toFixed(0) }}%</span>
              </el-tag>
              <el-progress
                :percentage="Math.round((item.confidence || 0) * 100)"
                :stroke-width="10"
                :width="58"
                type="circle"
              />
            </div>
          </div>
          <div v-if="item.entry_strategy" style="margin-top: 8px; color: #303133; font-size: 13px;">
            买入策略：{{ displayText(item.entry_strategy) }}
          </div>
          <div style="margin-top: 6px; color: #606266; font-size: 13px; line-height: 1.6;">{{ displayText(item.reason) }}</div>
          <div v-if="item.risk" style="margin-top: 6px; color: #b26a00; font-size: 13px;">风险：{{ displayText(item.risk) }}</div>
        </div>
      </div>

      <!-- 操作建议列表 -->
      <div style="font-weight: bold; margin-bottom: 10px;">持仓操作建议</div>
      <div v-for="action in latestAdvice.actions" :key="action.fund_code" style="margin-bottom: 16px; padding: 12px; border-radius: 8px; border: 1px solid #e4e7ed;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <span style="font-weight: bold; font-size: 15px;">{{ action.fund_code }}</span>
            <span style="margin-left: 8px; color: #606266;">{{ action.fund_name }}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <el-tag :type="actionType(action.action)" size="large" effect="dark">
              {{ actionLabel(action.action) }}
              <span v-if="action.suggested_ratio"> {{ (action.suggested_ratio * 100).toFixed(0) }}%</span>
            </el-tag>
            <el-progress
              :percentage="Math.round((action.confidence || 0) * 100)"
              :stroke-width="10"
              :width="60"
              type="circle"
              style="margin-left: 8px;"
            />
          </div>
        </div>
        <div style="margin-top: 8px; color: #606266; font-size: 13px;">{{ displayText(action.reason) }}</div>
      </div>

      <!-- 总体建议 -->
      <div v-if="latestAdvice.reasoning" style="margin-top: 16px; padding: 12px; background: #f4f4f5; border-radius: 8px;">
        <div style="font-weight: bold; margin-bottom: 4px;">市场判断依据：</div>
        <div style="font-size: 13px; color: #606266; line-height: 1.6;">{{ displayText(latestAdvice.reasoning) }}</div>
      </div>

      <div v-if="latestAdvice.overall_suggestion" style="margin-top: 12px; padding: 12px; background: #fff7e6; border: 1px solid #ffd591; border-radius: 8px;">
        <div style="font-weight: bold; margin-bottom: 4px;">总体建议：</div>
        <div style="font-size: 13px; color: #606266; line-height: 1.6;">{{ displayText(latestAdvice.overall_suggestion) }}</div>
      </div>
    </el-card>

    <!-- 无建议提示 -->
    <el-card v-else shadow="hover" style="margin-bottom: 20px; text-align: center; padding: 40px;">
      <el-icon :size="48" color="#c0c4cc"><MagicStick /></el-icon>
      <div style="margin-top: 16px; color: #909399;">暂无AI建议</div>
      <div style="color: #c0c4cc; font-size: 13px; margin-top: 4px;">
        每个交易日14:30自动生成，或点击上方按钮手动触发
      </div>
    </el-card>

    <!-- 历史建议列表 -->
    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">历史建议</span></template>
      <el-table :data="advices" stripe style="width: 100%">
        <el-table-column prop="advice_date" label="日期" width="120" />
        <el-table-column prop="advice_time" label="时间" width="80" />
        <el-table-column label="市场判断" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="marketViewTagType(row.market_view)">
              {{ marketViewLabel(row.market_view) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="riskTagType(row.risk_level)">
              {{ riskLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作数" width="80">
          <template #default="{ row }">
            {{ row.actions?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="140" />
        <el-table-column prop="token_usage" label="Token消耗" width="100" />
        <el-table-column label="已读" width="80">
          <template #default="{ row }">
            <el-icon v-if="row.is_read" color="#67c23a"><Check /></el-icon>
            <el-icon v-else color="#909399"><Close /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="viewAdvice(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 查看详情对话框 -->
    <el-dialog v-model="detailVisible" title="AI建议详情" width="700px">
      <div style="white-space: pre-wrap; line-height: 1.8;">{{ detailContent }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAiAdvices, getLatestAdvice, generateAdvice, markAdviceRead } from '../api'

const latestAdvice = ref<any>({})
const advices = ref<any[]>([])
const generating = ref(false)
const detailVisible = ref(false)
const detailContent = ref('')

const marketViewText = computed(() => {
  return marketViewLabel(latestAdvice.value?.market_view)
})

const marketViewType = computed(() => {
  return marketViewTagType(latestAdvice.value?.market_view)
})

const riskText = computed(() => riskLabel(latestAdvice.value?.risk_level))
const riskType = computed(() => riskTagType(latestAdvice.value?.risk_level))
const dataQuality = computed(() => latestAdvice.value?.data_quality || {})
const opportunities = computed(() => latestAdvice.value?.opportunities || [])
const adviceTitle = computed(() => dataQuality.value?.is_trading_day === false ? '休市期间AI复盘建议' : '本次AI投资建议')
const isRestContext = computed(() => dataQuality.value?.is_trading_day === false || isKnownHolidayToday())

function marketViewLabel(view: string) {
  if (view === 'bullish') return '看多'
  if (view === 'bearish') return '看空'
  return '中性'
}

function marketViewTagType(view: string) {
  if (view === 'bullish') return 'danger'
  if (view === 'bearish') return 'success'
  return 'info'
}

function riskLabel(risk: string) {
  if (risk === 'high') return '高'
  if (risk === 'low') return '低'
  return '中'
}

function riskTagType(risk: string) {
  if (risk === 'high') return 'danger'
  if (risk === 'low') return 'success'
  return 'warning'
}

function actionType(action: string) {
  if (action === 'add') return 'danger'
  if (action === 'reduce') return 'success'
  return 'info'
}

function actionLabel(action: string) {
  if (action === 'add') return '加仓'
  if (action === 'reduce') return '减仓'
  return '持有'
}

function opportunityType(action: string) {
  if (action === 'buy') return 'danger'
  if (action === 'avoid') return 'success'
  return 'warning'
}

function opportunityLabel(action: string) {
  if (action === 'buy') return '建议买入'
  if (action === 'avoid') return '暂不买入'
  return '观察'
}

function boardTypeLabel(type: string) {
  return type === 'concept' ? '概念' : '行业'
}

function displayText(value: any) {
  const text = String(value || '')
  if (!isRestContext.value) return text
  return text
    .replaceAll('今日尾盘', '休市期间')
    .replaceAll('今日主力', '最近交易日主力')
    .replaceAll('今日资金', '最近交易日资金')
    .replaceAll('今日行情', '最近交易日行情')
    .replaceAll('今日涨跌', '最近交易日涨跌')
    .replaceAll('今日', '最近交易日')
    .replaceAll('当天', '最近交易日')
}

function isKnownHolidayToday() {
  const d = new Date()
  const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return ['2026-05-01', '2026-05-04', '2026-05-05'].includes(key)
}

async function handleGenerate() {
  generating.value = true
  try {
    const res = await generateAdvice()
    if ((res as any).error) {
      ElMessage.error((res as any).error)
    } else {
      ElMessage.success('AI建议生成成功')
      await loadData()
    }
  } catch (e: any) {
    ElMessage.error('生成失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    generating.value = false
  }
}

function viewAdvice(row: any) {
  detailContent.value = row.advice_content || JSON.stringify(row.actions, null, 2)
  detailVisible.value = true
  if (!row.is_read) {
    markAdviceRead(row.id)
  }
}

async function loadData() {
  try {
    const [latest, list] = await Promise.all([
      getLatestAdvice(),
      getAiAdvices(30),
    ])
    latestAdvice.value = (latest as any).advice || latest
    advices.value = list as any
  } catch (e) {
    console.error(e)
  }
}

onMounted(loadData)
</script>

<style scoped>
.quality-label {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}

.quality-value {
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}
</style>
