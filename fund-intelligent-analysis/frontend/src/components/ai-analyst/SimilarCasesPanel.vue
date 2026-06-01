<template>
  <div>
    <el-alert
      title="相似案例基于历史建议的市场趋势、风险等级、组合特征等维度进行结构化匹配。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <!-- 搜索条件 -->
    <el-card shadow="hover" style="margin-bottom: 20px;">
      <template #header><span style="font-weight: bold;">检索条件</span></template>
      <el-form :inline="true" size="default">
        <el-form-item label="市场趋势">
          <el-select v-model="filters.market_trend" style="width: 120px;">
            <el-option label="上涨" value="up" />
            <el-option label="震荡" value="neutral" />
            <el-option label="下跌" value="down" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="filters.risk_level" style="width: 120px;">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item label="当前回撤">
          <el-input-number v-model="filters.current_drawdown" :min="0" :max="50" :step="5" style="width: 120px;" />
          <span style="color: #909399; margin-left: 4px;">%</span>
        </el-form-item>
        <el-form-item label="行业集中度">
          <el-slider v-model="filters.sector_concentration" :min="0" :max="1" :step="0.1" style="width: 150px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="search">检索</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 结果 -->
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold;">相似案例 ({{ cases.length }})</span>
        </div>
      </template>

      <div v-if="cases.length > 0">
        <div v-for="item in cases" :key="item.memory_id" class="case-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div>
              <el-tag :type="decisionType(item.decision)" size="small">{{ decisionLabel(item.decision) }}</el-tag>
              <span style="margin-left: 8px; color: #606266; font-size: 13px;">{{ item.created_at }}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
              <el-tag type="info" size="small">相似度 {{ (item.similarity_score * 100).toFixed(0) }}%</el-tag>
              <el-tag :type="item.is_user_accepted ? 'success' : (item.is_user_accepted === false ? 'danger' : 'info')" size="small">
                {{ item.is_user_accepted ? '已采纳' : (item.is_user_accepted === false ? '未采纳' : '未知') }}
              </el-tag>
            </div>
          </div>
          <div style="color: #303133; font-size: 13px; margin-bottom: 6px;">{{ item.advice_summary }}</div>
          <div v-if="item.reason_tags?.length" style="margin-bottom: 6px;">
            <el-tag v-for="tag in item.reason_tags" :key="tag" size="small" style="margin-right: 4px;">{{ tag }}</el-tag>
          </div>
          <div v-if="item.outcomes?.length" style="color: #909399; font-size: 12px;">
            复盘：
            <span v-for="o in item.outcomes" :key="o.horizon" style="margin-right: 8px;">
              {{ o.horizon }}d → {{ o.score?.toFixed(0) }}分
            </span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无相似案例，请调整条件后检索" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { getPersonalAnalystSimilarCases } from '../../api'

const loading = ref(false)
const cases = ref<any[]>([])

const filters = reactive({
  market_trend: 'neutral',
  risk_level: 'medium',
  current_drawdown: 0,
  sector_concentration: 0.5,
})

function decisionType(decision: string) {
  if (decision === 'add' || decision === 'buy') return 'danger'
  if (decision === 'reduce' || decision === 'avoid') return 'success'
  return 'info'
}

function decisionLabel(decision: string) {
  const map: Record<string, string> = {
    add: '加仓', reduce: '减仓', hold: '持有', buy: '买入', avoid: '回避',
  }
  return map[decision] || decision
}

async function search() {
  loading.value = true
  try {
    const res = (await getPersonalAnalystSimilarCases(filters)) as any
    cases.value = res.cases || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(search)
</script>

<style scoped>
.case-card {
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  margin-bottom: 12px;
  background: #fcfcfd;
}

.case-card:last-child {
  margin-bottom: 0;
}
</style>
