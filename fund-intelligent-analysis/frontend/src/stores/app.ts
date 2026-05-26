import { defineStore } from 'pinia'
import { ref } from 'vue'
import { STORAGE_KEYS, migrateStorage } from '@/utils/constants'

export const useAppStore = defineStore('app', () => {
  migrateStorage()

  const privacyMode = ref(localStorage.getItem(STORAGE_KEYS.PRIVACY_MODE) === '1')

  function togglePrivacy() {
    privacyMode.value = !privacyMode.value
    localStorage.setItem(STORAGE_KEYS.PRIVACY_MODE, privacyMode.value ? '1' : '0')
  }

  return { privacyMode, togglePrivacy }
})
