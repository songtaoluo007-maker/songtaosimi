<template>
  <div>
    <el-alert
      title="建议复盘功能将在后端记忆库完成后开放。届时将自动追踪每条建议的 1/7/30/90 天表现。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">历史建议复盘</span></template>
      <el-table :data="advices" stripe style="width: 100%">
        <el-table-column prop="advice_date" label="日期" width="120" />
        <el-table-column label="市场判断" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="marketViewTagType(row.market_view)">
              {{ marketViewLabel(row.market_view) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作数" width="80">
          <template #default="{ row }">{{ row.actions?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="复盘状态" width="120">
          <template #default>
            <el-tag size="small" type="info">待接入</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="表现" min-width="120">
          <template #default>
            <span style="color: #909399;">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAiAdvices } from '../../api'

const advices = ref<any[]>([])

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

onMounted(async () => {
  try {
    advices.value = (await getAiAdvices(90)) as any
  } catch (e) {
    console.error(e)
  }
})
</script>
