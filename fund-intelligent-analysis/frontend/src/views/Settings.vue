<template>
  <div>
    <h2 style="margin: 0 0 20px;">系统设置</h2>

    <el-card shadow="hover" class="diagnostics-card">
      <template #header>
        <div class="card-header">
          <div>
            <span style="font-weight: bold;">系统体检</span>
            <span class="muted">行情、新闻、AI、调度与启动日志</span>
          </div>
          <el-button size="small" :loading="diagnosticsLoading" @click="loadDiagnostics">
            刷新体检
          </el-button>
        </div>
      </template>

      <div class="diagnostics-head">
        <el-tag size="large" :type="tagType(diagnostics.status)">
          {{ statusText(diagnostics.status) }}
        </el-tag>
        <span class="diagnostics-time">生成时间：{{ diagnostics.generated_at || '-' }}</span>
        <span class="diagnostics-time">市场语境：{{ diagnostics.market_context || '-' }}</span>
        <span class="diagnostics-time">
          正常 {{ diagnostics.summary?.ok || 0 }} / 警告 {{ diagnostics.summary?.warning || 0 }} / 严重 {{ diagnostics.summary?.critical || 0 }}
        </span>
      </div>

      <el-alert
        v-if="diagnostics.summary?.warning || diagnostics.summary?.critical"
        class="diagnostics-alert"
        :type="diagnostics.summary?.critical ? 'error' : 'warning'"
        :closable="false"
        show-icon
        title="系统检测到数据或启动链路存在需要关注的项目，请优先处理严重和警告项。"
      />

      <el-row :gutter="12" class="freshness-grid">
        <el-col v-for="item in snapshotItems" :key="item.key" :xs="24" :sm="12" :md="8" :lg="4">
          <div class="freshness-tile">
            <div class="freshness-title">{{ item.label }}</div>
            <div class="freshness-date">{{ item.latest_date || '暂无' }}</div>
            <div class="freshness-meta">
              {{ item.latest_time || '-' }} · {{ item.count_on_latest_date || 0 }} 条
            </div>
          </div>
        </el-col>
      </el-row>

      <el-table :data="diagnostics.checks || []" size="small" stripe style="width: 100%; margin-top: 12px;">
        <el-table-column prop="title" label="检查项" width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="tagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="结果" min-width="180" />
        <el-table-column prop="detail" label="说明" min-width="240" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-row :gutter="20">
      <!-- 基本配置 -->
      <el-col :span="12">
        <el-card shadow="hover" style="margin-bottom: 20px;">
          <template #header><span style="font-weight: bold;">AI配置</span></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="AI模型">{{ config.deepseek_model }}</el-descriptions-item>
            <el-descriptions-item label="API地址">{{ config.deepseek_base_url }}</el-descriptions-item>
            <el-descriptions-item label="API Key">
              <el-tag :type="config.has_api_key ? 'success' : 'danger'">
                {{ config.has_api_key ? '已配置' : '未配置' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <div style="margin-top: 12px; color: #909399; font-size: 12px;">
            修改配置请编辑项目根目录的 .env 文件，然后重启服务生效
          </div>
        </el-card>

        <el-card shadow="hover">
          <template #header><span style="font-weight: bold;">采集配置</span></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="行情采集间隔">{{ config.market_collect_interval }} 分钟</el-descriptions-item>
            <el-descriptions-item label="估值采集间隔">{{ config.fund_estimate_interval }} 分钟</el-descriptions-item>
            <el-descriptions-item label="尾盘AI时间">{{ config.ai_advice_time }}</el-descriptions-item>
            <el-descriptions-item label="建议前刷新">
              <el-tag :type="config.ai_advice_pre_refresh ? 'success' : 'warning'">
                {{ config.ai_advice_pre_refresh ? '已启用' : '未启用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="新闻回看">{{ config.ai_news_lookback_days }} 天</el-descriptions-item>
            <el-descriptions-item label="监听地址">{{ config.backend_host }}</el-descriptions-item>
            <el-descriptions-item label="后端端口">{{ config.backend_port }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 调度状态 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: bold;">定时任务状态</span>
              <el-button size="small" @click="loadSchedulerStatus">刷新</el-button>
            </div>
          </template>

          <div v-if="scheduler.status === 'running'">
            <el-table :data="scheduler.jobs" stripe style="width: 100%;">
              <el-table-column prop="name" label="任务名称" min-width="140" />
              <el-table-column label="下次执行" width="180">
                <template #default="{ row }">
                  <span style="font-size: 12px;">{{ formatNextRun(row.next_run) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button size="small" type="primary" @click="handleTrigger(row.id)">
                    立即执行
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="调度器未运行" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, getSchedulerStatus, getDiagnostics, triggerJob } from '../api'

const config = ref<any>({})
const scheduler = ref<any>({ status: 'not_running', jobs: [] })
const diagnostics = ref<any>({ checks: [], summary: {}, data_freshness: { snapshots: {} } })
const diagnosticsLoading = ref(false)

const snapshotLabels: Record<string, string> = {
  index: 'A股指数',
  sector: '行业板块',
  concept: '概念板块',
  global: '全球市场',
  fund: '基金估值',
}

const snapshotItems = computed(() => {
  const snapshots = diagnostics.value?.data_freshness?.snapshots || {}
  return Object.entries(snapshotLabels).map(([key, label]) => ({
    key,
    label,
    ...(snapshots[key] || {}),
  }))
})

function tagType(status: string) {
  if (status === 'healthy' || status === 'ok') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'danger'
  return 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = {
    healthy: '健康',
    ok: '正常',
    warning: '警告',
    critical: '严重',
  }
  return map[status] || '未知'
}

function formatNextRun(t: string) {
  if (!t || t === 'N/A') return 'N/A'
  try {
    const d = new Date(t)
    return d.toLocaleString('zh-CN')
  } catch {
    return t
  }
}

async function loadSchedulerStatus() {
  try {
    scheduler.value = (await getSchedulerStatus()) as any
  } catch (e) {
    console.error(e)
  }
}

async function loadDiagnostics() {
  diagnosticsLoading.value = true
  try {
    diagnostics.value = (await getDiagnostics()) as any
  } catch (e: any) {
    ElMessage.error('系统体检失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    diagnosticsLoading.value = false
  }
}

async function handleTrigger(jobId: string) {
  try {
    const res = (await triggerJob(jobId)) as any
    if (res.error) {
      ElMessage.error(res.error)
    } else {
      ElMessage.success(res.message || '已触发')
    }
  } catch (e: any) {
    ElMessage.error('触发失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(async () => {
  try {
    config.value = await getSettings() as any
  } catch (e) {
    console.error(e)
  }
  loadSchedulerStatus()
  loadDiagnostics()
})
</script>

<style scoped>
.diagnostics-card {
  margin-bottom: 20px;
}

.card-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.muted {
  color: #909399;
  font-size: 12px;
  font-weight: normal;
  margin-left: 10px;
}

.diagnostics-head {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
}

.diagnostics-time {
  color: #606266;
  font-size: 13px;
}

.diagnostics-alert {
  margin-top: 12px;
}

.freshness-grid {
  margin-top: 14px;
}

.freshness-tile {
  background: #f8fafc;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  min-height: 88px;
  padding: 12px;
}

.freshness-title {
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

.freshness-date {
  color: #111827;
  font-size: 18px;
  font-weight: 700;
  margin-top: 8px;
}

.freshness-meta {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
