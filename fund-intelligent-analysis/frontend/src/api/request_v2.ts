/**
 * Axios 请求实例 — V2
 *
 * V2 改动：
 * - 401 重试前防御 `error.config` 为空（fetch 错误、取消请求等场景）
 * - 重试时复用原始 config 而非递归调用 axios baseURL 拼接，避免 url 重复
 * - 同一时刻并发请求触发刷新只发一次（沿用单飞 Promise）
 * - 401 引导登录时带上当前路径 + 查询串，登录成功能跳回原页
 * - 抽出 STORAGE_KEYS 常量，去掉所有硬编码字符串
 */
import axios, { AxiosError, AxiosRequestConfig } from 'axios'
import { STORAGE_KEYS } from '@/utils/constants'

const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

let refreshPromise: Promise<string | null> | null = null

async function tryRefreshToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
  if (!refreshToken) return null
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    try {
      const resp = await axios.post('/api/auth/refresh', null, {
        headers: { 'X-Refresh-Token': refreshToken },
      })
      const token = resp.data.access_token as string
      localStorage.setItem(STORAGE_KEYS.TOKEN, token)
      return token
    } catch {
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
      return null
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

request.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEYS.TOKEN)
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const status = error.response?.status
    const config = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined

    // 401 单次重试：仅在拿到完整 config 时尝试
    if (status === 401 && config && !config._retried) {
      config._retried = true
      const newToken = await tryRefreshToken()
      if (newToken) {
        config.headers = config.headers || {}
        ;(config.headers as Record<string, string>).Authorization = `Bearer ${newToken}`
        return request(config)
      }
    }

    if (status === 401) {
      if (!window.location.pathname.startsWith('/login')) {
        const { useAuthStore } = await import('@/stores/auth')
        const authStore = useAuthStore()
        authStore.logoutAndRedirect(window.location.pathname + window.location.search)
      }
      return Promise.reject(error)
    }

    return Promise.reject(error)
  },
)

export default request
