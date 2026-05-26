/**
 * Vue Router — V2
 *
 * V2 改动：
 * - 自动登录成功后，把新 access_token + user 写入 Pinia authStore，避免页面初始化时 store 仍为空
 * - 所有 localStorage 读写改用 STORAGE_KEYS（保持唯一来源）
 * - 修复登录态识别：原 v1 只看 token 是否存在；v2 同时校验 token 是否未过期（粗判 JWT payload 时间）
 * - 把 axios 直接 import 改为按需 import，避免主包体积膨胀
 */
import { createRouter, createWebHistory } from 'vue-router'
import { STORAGE_KEYS } from '@/utils/constants'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true, title: '登录' } },
  { path: '/holdings', name: 'Holdings', component: () => import('../views/Holdings.vue'), meta: { title: '持仓管理' } },
  { path: '/ocr-import', name: 'OcrImport', component: () => import('../views/OcrImport.vue'), meta: { title: 'OCR导入' } },
  { path: '/market', name: 'Market', component: () => import('../views/Market.vue'), meta: { title: '行情' } },
  { path: '/market/detail/:symbol', name: 'MarketDetail', component: () => import('../views/MarketDetail.vue'), meta: { title: '行情详情' } },
  { path: '/fund/:code', name: 'FundDetail', component: () => import('../views/FundDetail.vue'), meta: { title: '基金详情' } },
  { path: '/news', name: 'News', component: () => import('../views/News.vue'), meta: { title: '新闻' } },
  { path: '/ai-advisor', name: 'AiAdvisor', component: () => import('../views/AiAdvisor.vue'), meta: { title: 'AI 顾问' } },
  { path: '/ai-advisor/review', name: 'AdviceReview', component: () => import('../views/AdviceReview.vue'), meta: { title: 'AI 复盘' } },
  { path: '/risk-exposure', name: 'RiskExposure', component: () => import('../views/RiskExposure.vue'), meta: { title: '风险暴露' } },
  { path: '/trades', name: 'Trades', component: () => import('../views/Trades.vue'), meta: { title: '交易记录' } },
  { path: '/capital-flow', name: 'CapitalFlow', component: () => import('../views/CapitalFlow.vue'), meta: { title: '资金流向' } },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { title: '设置' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFound.vue'), meta: { title: '页面不存在' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function isJwtLikelyValid(token: string | null): boolean {
  if (!token) return false
  // JWT payload 在第一个 '.' 之后；这里只快速判断未过期，不做签名校验
  try {
    const parts = token.split('.')
    if (parts.length < 2) return true // 非标准格式，交给后端验证
    const payloadSegment = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const paddedPayload = payloadSegment.padEnd(Math.ceil(payloadSegment.length / 4) * 4, '=')
    const payload = JSON.parse(atob(paddedPayload))
    if (typeof payload?.exp === 'number') {
      return payload.exp * 1000 > Date.now()
    }
    return true
  } catch {
    return true
  }
}

async function tryAutoLogin(): Promise<boolean> {
  const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
  if (!refreshToken) return false
  try {
    const axios = (await import('axios')).default
    const resp = await axios.post('/api/auth/refresh', null, {
      headers: { 'X-Refresh-Token': refreshToken },
    })
    const token = resp.data.access_token as string
    localStorage.setItem(STORAGE_KEYS.TOKEN, token)

    // 关键修复：写入 Pinia store，避免 App.vue 首次渲染时拿不到 displayName
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    authStore.setAuth({ access_token: token, user: resp.data.user })
    return true
  } catch {
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
    return false
  }
}

router.beforeEach(async (to) => {
  document.title = (to.meta.title as string) || '基金智能分析'
  const token = localStorage.getItem(STORAGE_KEYS.TOKEN)
  const hasValid = isJwtLikelyValid(token)
  if (!to.meta.public && !hasValid) {
    const ok = await tryAutoLogin()
    if (ok) return true
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && hasValid) {
    return '/'
  }
  return true
})

export default router
