<template>
  <div class="news-page">
    <div class="news-header">
      <div>
        <h2>新闻资讯</h2>
        <p>自动分类新闻，标注利好/利空影响板块，并联动 AI 决策输入。</p>
      </div>
      <div class="header-actions">
        <el-button :loading="classifying" @click="handleClassify">重新分类历史</el-button>
        <el-button type="primary" :loading="refreshing" @click="handleRefresh">刷新新闻</el-button>
      </div>
    </div>

    <div class="channel-tabs">
      <button
        v-for="item in channels"
        :key="item"
        :class="{ active: activeChannel === item }"
        @click="switchChannel(item)"
      >
        {{ item }}
      </button>
    </div>

    <div v-if="activeChannel === '7x24'" class="sub-tabs">
      <button
        v-for="item in flashTabs"
        :key="item"
        :class="{ active: activeFlashTab === item }"
        @click="switchFlashTab(item)"
      >
        {{ item }}
      </button>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="keyword"
        placeholder="搜索新闻、板块、基金主题"
        clearable
        style="width: 260px;"
        @clear="loadNews"
        @keyup.enter="loadNews"
      />
      <el-select v-model="sentiment" clearable placeholder="情绪" style="width: 120px;" @change="loadNews">
        <el-option label="利好" value="positive" />
        <el-option label="利空" value="negative" />
        <el-option label="分化" value="mixed" />
        <el-option label="中性" value="neutral" />
      </el-select>
      <el-button type="primary" @click="loadNews">筛选</el-button>
      <span class="muted">当前栏目：{{ activeChannel }}{{ activeChannel === '7x24' ? ` / ${activeFlashTab}` : '' }}</span>
    </div>

    <div class="content-grid">
      <main class="news-main" v-loading="loading">
        <template v-if="newsList.length">
          <article v-for="item in newsList" :key="item.id" class="news-item">
            <div class="news-item-head">
              <div class="news-title" @click="openUrl(item.url)">{{ item.title }}</div>
              <el-tag size="small" :type="sentimentTag(item.sentiment)">{{ sentimentText(item.sentiment) }}</el-tag>
            </div>
            <p v-if="item.content" class="news-content">{{ item.content }}</p>
            <div class="news-meta">
              <span>{{ item.source || '未知来源' }}</span>
              <span>{{ formatTime(item.publish_time) }}</span>
              <el-tag size="small" type="info">{{ item.category || '推荐' }}</el-tag>
              <el-tag v-if="item.sub_category && item.category === '7x24'" size="small" type="info">{{ item.sub_category }}</el-tag>
              <el-tag v-if="item.importance_score >= 75" size="small" type="warning">高影响 {{ item.importance_score.toFixed?.(0) || item.importance_score }}</el-tag>
            </div>
            <div v-if="item.impact_items?.length" class="impact-list">
              <span class="impact-label">影响：</span>
              <span
                v-for="impact in item.impact_items"
                :key="`${item.id}-${impact.direction}-${impact.target_name}`"
                class="impact-chip"
                :class="impactClass(impact.direction)"
                :title="impact.reason"
              >
                {{ impact.direction }} {{ impact.target_name }} · {{ impact.horizon }} · {{ strengthText(impact.strength) }}
              </span>
            </div>
          </article>
        </template>
        <el-empty v-else-if="!loading" description="暂无该栏目新闻，可刷新或切换栏目" />
        <div v-if="totalNews > pageSize" style="margin-top: 16px; display: flex; justify-content: center;">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="totalNews"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            small
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </main>

      <aside class="news-side">
        <section class="side-panel">
          <div class="side-title">影响雷达</div>
          <div class="radar-row">
            <div class="radar-col">
              <strong>利好板块</strong>
              <div v-for="item in insights.positive_targets || []" :key="item.target" class="target-line positive">
                <span>{{ item.target }}</span><em>{{ item.score }}</em>
              </div>
              <el-empty v-if="!insights.positive_targets?.length" description="暂无利好标注" :image-size="48" />
            </div>
            <div class="radar-col">
              <strong>利空板块</strong>
              <div v-for="item in insights.negative_targets || []" :key="item.target" class="target-line negative">
                <span>{{ item.target }}</span><em>{{ item.score }}</em>
              </div>
              <el-empty v-if="!insights.negative_targets?.length" description="暂无利空标注" :image-size="48" />
            </div>
          </div>
        </section>

        <section class="side-panel">
          <div class="side-title">7x24 快讯</div>
          <div v-for="item in flashList" :key="item.id" class="flash-item" @click="openUrl(item.url)">
            <span>{{ formatTime(item.publish_time).slice(5) }}</span>
            <p>{{ item.title }}</p>
          </div>
          <el-empty v-if="!flashList.length" description="暂无快讯" :image-size="48" />
        </section>

        <section class="side-panel">
          <div class="side-title">情绪分布</div>
          <div class="sentiment-grid">
            <div><span>利好</span><strong class="positive">{{ insights.sentiment?.positive || 0 }}</strong></div>
            <div><span>利空</span><strong class="negative">{{ insights.sentiment?.negative || 0 }}</strong></div>
            <div><span>分化</span><strong>{{ insights.sentiment?.mixed || 0 }}</strong></div>
            <div><span>中性</span><strong>{{ insights.sentiment?.neutral || 0 }}</strong></div>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { classifyExistingNews, getNews, getNewsInsights, refreshNews } from '../api'

const channels = ['头条', '推荐', '黄金', '7x24', '股市', '宏观', '国际', '基金', '持仓相关']
const flashTabs = ['全部', '股市', '宏观', '国际', '观点']

const activeChannel = ref('头条')
const activeFlashTab = ref('全部')
const keyword = ref('')
const sentiment = ref('')
const newsList = ref<any[]>([])
const flashList = ref<any[]>([])
const insights = ref<any>({})
const loading = ref(false)
const refreshing = ref(false)
const classifying = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalNews = ref(0)

function switchChannel(channel: string) {
  activeChannel.value = channel
  activeFlashTab.value = '全部'
  currentPage.value = 1
  loadNews()
}

function switchFlashTab(tab: string) {
  activeFlashTab.value = tab
  loadNews()
}

function buildParams() {
  const params: any = { page: currentPage.value, page_size: pageSize.value }
  if (keyword.value) params.keyword = keyword.value
  if (sentiment.value) params.sentiment = sentiment.value
  if (activeChannel.value === '头条') {
    params.sort = 'importance'
    const d = new Date()
    d.setDate(d.getDate() - 7)
    params.start_date = d.toISOString().slice(0, 10)
  } else if (activeChannel.value !== '持仓相关') {
    params.category = activeChannel.value
  } else {
    params.keyword = keyword.value || '持仓'
  }
  if (activeChannel.value === '7x24' && activeFlashTab.value !== '全部') {
    params.sub_category = activeFlashTab.value
  }
  return params
}

async function loadNews() {
  loading.value = true
  try {
    const res = await getNews(buildParams()) as any
    newsList.value = res.items || res || []
    totalNews.value = res.total || 0
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '新闻加载失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadNews()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadNews()
}

async function loadSideData() {
  const [flash, summary] = await Promise.all([
    getNews({ category: '7x24', page: 1, page_size: 18 }),
    getNewsInsights(),
  ])
  flashList.value = (flash as any)?.items || (flash as any) || []
  insights.value = summary as any
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await refreshNews()
    ElMessage.success('新闻已刷新')
    await Promise.all([loadNews(), loadSideData()])
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function handleClassify() {
  classifying.value = true
  try {
    const res = (await classifyExistingNews()) as any
    ElMessage.success(res.message || '历史新闻已重新分类')
    await Promise.all([loadNews(), loadSideData()])
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '分类失败')
  } finally {
    classifying.value = false
  }
}

function formatTime(t: string) {
  if (!t) return ''
  return t.substring(0, 16)
}

function openUrl(url: string) {
  if (url) window.open(url, '_blank')
}

function sentimentText(value: string) {
  const map: Record<string, string> = {
    positive: '利好',
    negative: '利空',
    mixed: '分化',
    neutral: '中性',
  }
  return map[value] || '中性'
}

function sentimentTag(value: string) {
  if (value === 'positive') return 'danger'
  if (value === 'negative') return 'success'
  if (value === 'mixed') return 'warning'
  return 'info'
}

function impactClass(direction: string) {
  if (direction === '利好') return 'impact-positive'
  if (direction === '利空') return 'impact-negative'
  return 'impact-neutral'
}

function strengthText(value: any) {
  const n = Number(value) || 0
  if (n >= 0.78) return '高'
  if (n >= 0.55) return '中'
  return '低'
}

onMounted(async () => {
  try { await refreshNews() } catch { /* 首次刷新失败不影响已有数据 */ }
  await Promise.all([loadNews(), loadSideData()])
})
</script>

<style scoped>
.news-page { max-width: var(--content-max-width); }
.news-header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 16px; }
.news-header h2 { margin: 0; font-size: 24px; font-weight: 700; color: var(--gray-900); letter-spacing: -0.01em; }
.news-header p { font-size: var(--text-sm); color: var(--gray-500); margin: 6px 0 0; }
.header-actions { display: flex; gap: 8px; }
.channel-tabs, .sub-tabs, .filter-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.channel-tabs button, .sub-tabs button {
  background: #fff; border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm); cursor: pointer; font-size: var(--text-sm);
  padding: 8px 14px; color: var(--gray-600); transition: all var(--transition-fast);
}
.sub-tabs button { font-size: var(--text-xs); padding: 6px 12px; }
.channel-tabs button:hover, .sub-tabs button:hover { border-color: var(--brand-300); }
.channel-tabs button.active, .sub-tabs button.active {
  background: var(--brand-600); border-color: var(--brand-600); color: #fff; font-weight: 600;
}
.muted { color: var(--gray-400); font-size: var(--text-xs); }
.content-grid { display: grid; gap: var(--space-4); grid-template-columns: minmax(0, 1fr) 360px; align-items: flex-start; }
.news-main, .side-panel {
  background: #fff; border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-sm);
}
.news-main { min-height: 520px; padding: 6px 18px; }
.news-item { border-bottom: 1px solid var(--gray-100); padding: 16px 0; }
.news-item:last-child { border-bottom: 0; }
.news-item-head { display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; }
.news-title { font-size: 16px; font-weight: 700; color: var(--gray-800); cursor: pointer; line-height: 1.55; }
.news-title:hover { color: var(--brand-600); }
.news-content { font-size: var(--text-sm); color: var(--gray-600); line-height: 1.7; margin: 8px 0 0; }
.news-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: var(--text-xs); color: var(--gray-400); margin-top: 10px; }
.impact-list { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 10px; }
.impact-label { font-size: var(--text-xs); color: var(--gray-500); }
.impact-chip { font-size: var(--text-xs); padding: 4px 8px; border-radius: var(--radius-full); }
.impact-positive { background: var(--danger-50); color: var(--danger-600); }
.impact-negative { background: var(--success-50); color: var(--success-600); }
.impact-neutral { background: var(--gray-100); color: var(--gray-600); }
.news-side { display: flex; flex-direction: column; gap: 12px; }
.side-panel { padding: 14px; }
.side-title { font-size: var(--text-lg); font-weight: 700; color: var(--gray-800); margin-bottom: 12px; }
.radar-row { display: grid; gap: 12px; grid-template-columns: 1fr 1fr; }
.radar-col strong { display: block; font-size: var(--text-sm); margin-bottom: 8px; color: var(--gray-700); }
.target-line { display: flex; justify-content: space-between; align-items: center; font-size: var(--text-xs); line-height: 2; }
.target-line em { color: var(--gray-500); font-style: normal; }
.positive { color: var(--danger-500); }
.negative { color: var(--success-500); }
.flash-item { display: grid; gap: 8px; grid-template-columns: 44px 1fr; border-bottom: 1px solid var(--gray-100); padding: 9px 0; cursor: pointer; }
.flash-item:last-child { border-bottom: 0; }
.flash-item span { font-size: var(--text-xs); color: var(--gray-400); }
.flash-item p { font-size: var(--text-sm); color: var(--gray-700); line-height: 1.5; margin: 0; }
.sentiment-grid { display: grid; gap: 8px; grid-template-columns: repeat(4, 1fr); }
.sentiment-grid div {
  background: var(--gray-50); border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm); padding: 8px; text-align: center;
}
.sentiment-grid span { display: block; font-size: var(--text-xs); color: var(--gray-500); }
.sentiment-grid strong { display: block; font-size: 18px; font-weight: 700; margin-top: 4px; color: var(--gray-800); }
@media (max-width: 1180px) { .content-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) {
  .news-header, .filter-bar { flex-direction: column; align-items: flex-start; }
  .channel-tabs, .sub-tabs { overflow-x: auto; padding-bottom: 4px; }
}
</style>
