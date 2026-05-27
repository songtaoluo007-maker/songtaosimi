<template>
  <router-view v-if="$route.meta.public" v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>

  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="sidebar-logo">
          <img :src="brandIcon" alt="" />
        </div>
        <div class="sidebar-brand-text">
          <span class="sidebar-app-name">基金智能分析</span>
          <span class="sidebar-app-ver">本地安全工作台</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-label">核心</div>
        <router-link
          v-for="item in primaryNav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>

        <div class="nav-section-label" style="margin-top:14px;">分析</div>
        <router-link
          v-for="item in analysisNav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>

        <div class="nav-section-label" style="margin-top:14px;">系统</div>
        <router-link
          v-for="item in systemNav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="sidebar-user">
          <div class="user-avatar">{{ currentUserName.charAt(0) }}</div>
          <div class="user-info">
            <span class="user-name">{{ currentUserName }}</span>
            <span class="user-addr">localhost</span>
          </div>
        </div>
        <el-button class="logout-btn" text @click="logout">
          <el-icon><SwitchButton /></el-icon>
        </el-button>
      </div>
    </aside>

    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="slide-up" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<!--
  V2 改动：
  - 把导航分为「核心 / 分析 / 系统」三组，比 v1 的单组扁平结构更清晰
  - 补齐 v1 缺失的入口：风险暴露、AI 复盘、交易记录
  - logout() 改为 async，登出后 await router.replace 再清状态，避免最后一秒访问受保护页报 401
-->
<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getOcrSyncStatus } from '@/api'
import {
  DataAnalysis, Wallet, MagicStick, TrendCharts, Coin,
  Document, Camera, List, Setting, SwitchButton,
  Histogram, Memo, RefreshRight, Calendar, Tools,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const brandIcon = '/brand-assets/fund-ai-64.png'

const primaryNav = [
  { path: '/', label: '工作台', icon: DataAnalysis },
  { path: '/holdings', label: '持仓管理', icon: Wallet },
  { path: '/investment-plans', label: '定投计划', icon: Calendar },
  { path: '/ai-advisor', label: 'AI 尾盘建议', icon: MagicStick },
]

const analysisNav = [
  { path: '/risk-exposure', label: '风险暴露', icon: Histogram },
  { path: '/ai-advisor/review', label: 'AI 复盘', icon: RefreshRight },
  { path: '/fee-ledger', label: '费率账本', icon: Coin },
  { path: '/toolbox', label: '老基民工具箱', icon: Tools },
  { path: '/capital-flow', label: '资金流向', icon: Coin },
  { path: '/market', label: '行情监控', icon: TrendCharts },
  { path: '/news', label: '新闻资讯', icon: Document },
  { path: '/trades', label: '交易记录', icon: Memo },
]

const systemNav = [
  { path: '/ocr-import', label: '截图导入', icon: Camera },
  { path: '/settings', label: '系统设置', icon: Setting },
]

const authStore = useAuthStore()
const currentUserName = computed(() => authStore.displayName || '本机所有者')

function localDayKey() {
  const now = new Date()
  const y = now.getFullYear()
  const m = `${now.getMonth() + 1}`.padStart(2, '0')
  const d = `${now.getDate()}`.padStart(2, '0')
  return `${y}-${m}-${d}`
}

async function maybeShowOcrReminder() {
  if (route.meta.public) return
  try {
    const status = await getOcrSyncStatus() as any
    if (!status?.due) return
    const reminderKey = `ocr-sync-reminder:${localDayKey()}`
    if (localStorage.getItem(reminderKey)) return
    localStorage.setItem(reminderKey, '1')
    ElNotification({
      title: '持仓截图需要更新',
      message: status.message || '请导入最新持仓截图',
      type: 'warning',
      duration: 9000,
      onClick: () => router.push('/ocr-import'),
    })
  } catch {
    // OCR 状态提醒不应影响主界面加载
  }
}

watch(() => route.fullPath, maybeShowOcrReminder, { immediate: true })

async function logout() {
  authStore.logout()
  await router.replace('/login')
}
</script>

<style scoped>
/* 与 v1 完全相同，复用同一份 CSS 主题变量 */
.sidebar { width: var(--sidebar-width); min-width: var(--sidebar-width); height: 100vh; background: var(--sidebar-bg); display: flex; flex-direction: column; user-select: none; border-right: 1px solid var(--sidebar-border); }
.sidebar-brand { display: flex; align-items: center; gap: 12px; padding: 20px 20px 16px; }
.sidebar-logo { width: 38px; height: 38px; flex-shrink: 0; border-radius: var(--radius-sm); overflow: hidden; background: var(--brand-500); display: flex; align-items: center; justify-content: center; }
.sidebar-logo img { width: 24px; height: 24px; object-fit: contain; filter: brightness(10); }
.sidebar-brand-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.sidebar-app-name { font-size: 15px; font-weight: var(--weight-medium); color: var(--gray-900); letter-spacing: -0.01em; white-space: nowrap; }
.sidebar-app-ver { font-size: 11px; color: var(--gray-600); white-space: nowrap; }
.sidebar-nav { flex: 1; overflow-y: auto; padding: 8px 12px; }
.nav-section-label { font-size: 11px; font-weight: var(--weight-medium); color: var(--gray-600); padding: 0 12px; margin: 8px 0 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 0 12px 0 16px; height: 40px; border-radius: 0 var(--radius-full) var(--radius-full) 0; color: var(--sidebar-text); text-decoration: none; font-size: 13.5px; font-weight: var(--weight-medium); transition: all var(--transition-fast); position: relative; margin-bottom: 1px; margin-right: 12px; }
.nav-item:hover { background: var(--sidebar-hover); color: var(--gray-900); }
.nav-item.active { background: var(--sidebar-active); color: var(--sidebar-text-active); font-weight: var(--weight-semibold); }
.nav-item.active::before { content: ''; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; background: var(--brand-500); border-radius: 0 3px 3px 0; }
.nav-icon { font-size: 18px; flex-shrink: 0; opacity: 0.65; transition: opacity var(--transition-fast); }
.nav-item:hover .nav-icon { opacity: 0.85; }
.nav-item.active .nav-icon { opacity: 1; }
.nav-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--sidebar-border); position: relative; }
.sidebar-user { display: flex; align-items: center; gap: 10px; width: 100%; }
.user-avatar { width: 32px; height: 32px; border-radius: var(--radius-full); background: var(--brand-500); color: #fff; font-size: 14px; font-weight: var(--weight-medium); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.user-info { display: flex; flex-direction: column; gap: 0; min-width: 0; flex: 1; }
.user-name { font-size: 13px; font-weight: var(--weight-medium); color: var(--gray-900); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-addr { font-size: 11px; color: var(--gray-600); }
.logout-btn { position: absolute; right: 12px; bottom: 14px; color: var(--gray-500); padding: 4px; }
.logout-btn:hover { color: var(--danger-500); background: var(--danger-50); border-radius: var(--radius-full); }
.main-content { flex: 1; overflow-y: auto; overflow-x: hidden; background: var(--page-bg); padding: 28px 36px; min-width: 0; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.slide-up-enter-active { transition: all 0.25s ease; }
.slide-up-leave-active { transition: all 0.15s ease; }
.slide-up-enter-from { opacity: 0; transform: translateY(6px); }
.slide-up-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
