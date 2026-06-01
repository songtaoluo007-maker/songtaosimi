<template>
  <div>
    <!-- 页面标题区 -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h2 style="margin: 0;">AI 分析师</h2>
        <span style="color: #909399; font-size: 13px;">专属投资分析 · 记忆 · 复盘 · 成长</span>
      </div>
      <el-button type="primary" :loading="generating" @click="handleGenerate">
        <el-icon><MagicStick /></el-icon> 立即生成建议
      </el-button>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="今日建议" name="advice">
        <AdvicePanel ref="advicePanelRef" />
      </el-tab-pane>
      <el-tab-pane label="建议复盘" name="review">
        <ReviewPanel />
      </el-tab-pane>
      <el-tab-pane label="专属画像" name="profile">
        <ProfilePanel />
      </el-tab-pane>
      <el-tab-pane label="相似案例" name="similar">
        <SimilarCasesPanel />
      </el-tab-pane>
      <el-tab-pane label="成长报告" name="report">
        <GrowthReportPanel />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdvicePanel from '../components/ai-analyst/AdvicePanel.vue'
import ReviewPanel from '../components/ai-analyst/ReviewPanel.vue'
import ProfilePanel from '../components/ai-analyst/ProfilePanel.vue'
import SimilarCasesPanel from '../components/ai-analyst/SimilarCasesPanel.vue'
import GrowthReportPanel from '../components/ai-analyst/GrowthReportPanel.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref('advice')
const generating = ref(false)
const advicePanelRef = ref()

const tabList = ['advice', 'review', 'profile', 'similar', 'report']

onMounted(() => {
  // 从 query 同步 tab
  const tab = route.query.tab as string
  if (tab && tabList.includes(tab)) {
    activeTab.value = tab
  }
})

function onTabChange(tab: string | number) {
  router.replace({ query: { ...route.query, tab: tab as string } })
}

async function handleGenerate() {
  generating.value = true
  try {
    if (advicePanelRef.value) {
      await advicePanelRef.value.refresh()
    }
  } finally {
    generating.value = false
  }
}
</script>

<style scoped>
h2 {
  color: #303133;
}
</style>
