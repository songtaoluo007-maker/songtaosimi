<template>
  <div>
    <h2 style="margin: 0 0 20px;">系统设置</h2>

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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, getSchedulerStatus, triggerJob } from '../api'

const config = ref<any>({})
const scheduler = ref<any>({ status: 'not_running', jobs: [] })

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
})
</script>
