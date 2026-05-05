<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <h2 style="margin: 0;">新闻资讯</h2>
      <el-button type="primary" :loading="refreshing" @click="handleRefresh">立即刷新新闻</el-button>
    </div>

    <el-card shadow="hover" style="margin-bottom: 20px;">
      <el-form :inline="true">
        <el-form-item label="关键词">
          <el-input v-model="keyword" placeholder="搜索新闻" clearable @clear="loadNews" @keyup.enter="loadNews" style="width: 200px;" />
        </el-form-item>
        <el-form-item label="情绪">
          <el-select v-model="sentiment" clearable placeholder="全部" style="width: 100px;">
            <el-option label="利好" value="positive" />
            <el-option label="中性" value="neutral" />
            <el-option label="利空" value="negative" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadNews">搜索</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover">
      <div v-loading="loading">
        <div v-for="n in newsList" :key="n.id" style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div style="flex: 1;">
              <div style="font-size: 14px; line-height: 1.6; cursor: pointer;" @click="openUrl(n.url)">
                {{ n.title }}
              </div>
              <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                {{ n.source }}
                <span v-if="n.keyword" style="margin-left: 8px;">
                  <el-tag size="small" type="info">{{ n.keyword }}</el-tag>
                </span>
                <span style="margin-left: 8px;">{{ formatTime(n.publish_time) }}</span>
              </div>
            </div>
            <div>
              <el-tag v-if="n.sentiment === 'positive'" size="small" type="danger">利好</el-tag>
              <el-tag v-else-if="n.sentiment === 'negative'" size="small" type="success">利空</el-tag>
              <el-tag v-else size="small" type="info">中性</el-tag>
            </div>
          </div>
        </div>
        <el-empty v-if="!loading && newsList.length === 0" description="暂无新闻，每日07:00/12:00/18:00自动采集" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getNews, refreshNews } from '../api'

const newsList = ref<any[]>([])
const loading = ref(true)
const keyword = ref('')
const sentiment = ref('')
const refreshing = ref(false)

function formatTime(t: string) {
  if (!t) return ''
  return t.substring(0, 16)
}

function openUrl(url: string) {
  if (url) window.open(url, '_blank')
}

async function loadNews() {
  loading.value = true
  try {
    const params: any = { limit: 50 }
    if (keyword.value) params.keyword = keyword.value
    if (sentiment.value) params.sentiment = sentiment.value
    newsList.value = (await getNews(params)) as any
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await refreshNews()
    ElMessage.success('新闻已刷新')
    await loadNews()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '刷新失败')
  } finally {
    refreshing.value = false
  }
}

onMounted(loadNews)
</script>
