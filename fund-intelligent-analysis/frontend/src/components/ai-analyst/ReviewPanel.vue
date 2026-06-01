<template>
  <div>
    <!-- 复盘摘要 -->
    <el-row :gutter="16" style="margin-bottom: 20px;">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总复盘数" :value="summary.total || 0" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="平均评分" :value="summary.avg_score || 0" :precision="1" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <el-button type="primary" :loading="running" @click="runReview" style="margin-top: 8px;">
            手动触发复盘
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 按窗口统计 -->
    <el-card v-if="Object.keys(summary.by_horizon || {}).length > 0" shadow="hover" style="margin-bottom: 20px;">
      <template #header><span style="font-weight: bold;">各窗口评分</span></template>
      <el-row :gutter="16">
        <el-col v-for="(data, horizon) in summary.by_horizon" :key="horizon" :span="6">
          <div class="horizon-stat">
            <div class="horizon-label">{{ horizon }}</div>
            <div class="horizon-score">{{ data.avg_score?.toFixed(1) || '—' }}</div>
            <div class="horizon-count">{{ data.count || 0 }} 条</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 复盘列表 -->
    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">复盘记录</span></template>
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
        <el-table-column label="方向" width="80">
          <template #default="{ row }">{{ row.direction_correct?.toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column label="优于持有" width="90">
          <template #default="{ row }">{{ row.beat_hold?.toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column label="优于基准" width="90">
          <template #default="{ row }">{{ row.beat_benchmark?.toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column prop="outcome_summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.error_reason" type="danger" size="small">异常</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="outcomes.length === 0" description="暂无复盘记录" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPersonalAnalystOutcomes, runPersonalAnalystOutcomes } from '../../api'

const outcomes = ref<any[]>([])
const summary = ref<any>({ total: 0, avg_score: 0, by_horizon: {} })
const running = ref(false)

function scoreType(score: number) {
  if (score >= 70) return 'success'
  if (score >= 40) return 'warning'
  return 'danger'
}

async function loadData() {
  try {
    const res = (await getPersonalAnalystOutcomes(100)) as any
    outcomes.value = res.outcomes || []
    summary.value = res.summary || {}
  } catch (e) {
    console.error(e)
  }
}

async function runReview() {
  running.value = true
  try {
    const res = (await runPersonalAnalystOutcomes()) as any
    ElMessage.success(`复盘完成：新增${res.created}条，跳过${res.skipped}条`)
    await loadData()
  } catch (e: any) {
    ElMessage.error('复盘失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    running.value = false
  }
}

onMounted(loadData)
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
