import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/holdings', name: 'Holdings', component: () => import('../views/Holdings.vue') },
  { path: '/ocr-import', name: 'OcrImport', component: () => import('../views/OcrImport.vue') },
  { path: '/market', name: 'Market', component: () => import('../views/Market.vue') },
  { path: '/market/detail/:symbol', name: 'MarketDetail', component: () => import('../views/MarketDetail.vue'), meta: { title: '行情详情' } },
  { path: '/fund/:code', name: 'FundDetail', component: () => import('../views/FundDetail.vue'), meta: { title: '基金详情' } },
  { path: '/news', name: 'News', component: () => import('../views/News.vue') },

  // AI 分析师（统一入口）
  { path: '/ai-analyst', name: 'AiAnalyst', component: () => import('../views/AiAnalyst.vue'), meta: { title: 'AI 分析师' } },

  // 旧路由兼容重定向
  { path: '/ai-advisor', redirect: { path: '/ai-analyst', query: { tab: 'advice' } } },
  { path: '/ai-advisor/review', redirect: { path: '/ai-analyst', query: { tab: 'review' } } },

  { path: '/trades', name: 'Trades', component: () => import('../views/Trades.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
