<template>
  <div>
    <!-- 概览卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总建议数" :value="memorySummary.total || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="已采纳" :value="memorySummary.accepted || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="已拒绝" :value="memorySummary.rejected || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="平均评分" :value="outcomeSummary.avg_score || 0" :precision="1" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 复盘统计 -->
    <el-card shadow="hover" style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold;">复盘统计</span>
          <el-button size="small" :loading="loading" @click="loadReport">刷新</el-button>
        </div>
      </template>

      <div v-if="outcomeSummary.total > 0">
        <el-row :gutter="16">
          <el-col v-for="(data, horizon) in outcomeSummary.by_horizon" :key="horizon" :span="6">
            <div class="horizon-stat">
              <div class="horizon-label">{{ horizon }}</div>
              <div class="horizon-score">{{ data.avg_score?.toFixed(1) || '—' }}</div>
              <div class="horizon-count">{{ data.count || 0 }} 条</div>
            </div>
          </el-col>
        </el-row>
      </div>
      <el-empty v-else description="暂无复盘数据，等待系统自动生成" :image-size="60" />
    </el-card>

    <!-- 采纳率 -->
    <el-card shadow="hover" style="margin-bottom: 20px;">
      <template #header><span style="font-weight: bold;">建议采纳率</span></template>
      <div v-if="memorySummary.total > 0" style="display: flex; align-items: center; gap: 20px;">
        <el-progress
          type="circle"
          :percentage="acceptanceRate"
          :width="120"
          :stroke-width="12"
          :color="acceptanceColor"
        />
        <div>
          <div style="font-size: 16px; font-weight: bold; margin-bottom: 8px;">
            {{ acceptanceRate }}% 采纳率
          </div>
          <div style="color: #606266; font-size: 13px;">
            共 {{ memorySummary.total }} 条建议，采纳 {{ memorySummary.accepted }} 条，拒绝 {{ memorySummary.rejected }} 条
          </div>
          <div style="color: #909399; font-size: 12px; margin-top: 8px;">
            {{ acceptanceAdvice }}
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无建议数据" :image-size="60" />
    </el-card>

    <!-- 最近复盘记录 -->
    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">最近复盘记录</span></template>
      <el-table :data="outcomes" stripe style="width: 100%;">
        <el-table-column prop="memory_id" label="建议ID" width="80" />
        <el-table-column label="窗口" width="80">
          <template #default="{ row }">{{ row.review_horizon }}天</template>
        </el-table-column>
        <el-table-column prop="review_date" label="复盘日期" width="120" />
        <el-table-column label="评分" width="100">
          <template #default="{ row }">
            <el-tag :type="scoreType(row.score)" size="small">{{ row.score?.toFixed(0) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="方向正确" width="100">
          <template #default="{ row }">{{ row.direction_correct?.toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column label="优于持有" width="100">
          <template #default="{ row }">{{ row.beat_hold?.toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column label="优于基准" width="100">
          <template #default="{ row }">{{ row.beat_benchmark?.toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column prop="outcome_summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column label="错误" width="120">
          <template #default="{ row }">
            <span v-if="row.error_reason" style="color: #f56c6c;">{{ row.error_reason }}</span>
            <span v-else style="color: #67c23a;">正常</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getPersonalAnalystReport, getPersonalAnalystOutcomes } from '../../api'

const loading = ref(false)
const memorySummary = ref<any>({ total: 0, accepted: 0, rejected: 0 })
const outcomeSummary = ref<any>({ total: 0, avg_score: 0, by_horizon: {} })
const outcomes = ref<any[]>([])

const acceptanceRate = computed(() => {
  if (!memorySummary.value.total) return 0
  return Math.round((memorySummary.value.accepted / memorySummary.value.total) * 100)
})

const acceptanceColor = computed(() => {
  const rate = acceptanceRate.value
  if (rate >= 70) return '#67c23a'
  if (rate >= 40) return '#e6a23c'
  return '#f56c6c'
})

const acceptanceAdvice = computed(() => {
  const rate = acceptanceRate.value
  if (rate >= 70) return 'AI 建议与你的投资风格高度匹配'
  if (rate >= 40) return 'AI 建议正在学习你的偏好，持续反馈可提升匹配度'
  return '建议差异较大，请在画像中补充更多偏好信息'
})

function scoreType(score: number) {
  if (score >= 70) return 'success'
  if (score >= 40) return 'warning'
  return 'danger'
}

async function loadReport() {
  loading.value = true
  try {
    const [report, outcomesRes] = await Promise.all([
      getPersonalAnalystReport(),
      getPersonalAnalystOutcomes(50),
    ])
    memorySummary.value = (report as any).memory_summary || {}
    outcomeSummary.value = (report as any).outcome_summary || {}
    outcomes.value = (outcomesRes as any).outcomes || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(loadReport)
</script>

<style scoped>
.stat-card {
  text-align: center;
}

.horizon-stat {
  text-align: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.horizon-label {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}

.horizon-score {
  color: #303133;
  font-size: 28px;
  font-weight: 700;
}

.horizon-count {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
