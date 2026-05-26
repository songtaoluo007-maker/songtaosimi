import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { STORAGE_KEYS } from '@/utils/constants'
import type { UserInfo } from '@/types'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(STORAGE_KEYS.TOKEN))
  const user = ref<UserInfo | null>(null)

  // 从 localStorage 恢复用户信息
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.USER)
    if (raw) user.value = JSON.parse(raw)
  } catch { /* 忽略解析错误 */ }

  const isLoggedIn = computed(() => !!token.value)
  const displayName = computed(() => user.value?.display_name ?? user.value?.username ?? '')

  function setAuth(res: { access_token: string; user: UserInfo }) {
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem(STORAGE_KEYS.TOKEN, res.access_token)
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(res.user))
  }

  function clearState() {
    token.value = null
    user.value = null
    localStorage.removeItem(STORAGE_KEYS.TOKEN)
    localStorage.removeItem(STORAGE_KEYS.USER)
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  }

  function logout() {
    clearState()
  }

  function logoutAndRedirect(redirectPath?: string) {
    clearState()
    router.push('/login?redirect=' + encodeURIComponent(redirectPath || '/'))
  }

  return { token, user, isLoggedIn, displayName, setAuth, logout, logoutAndRedirect }
})
