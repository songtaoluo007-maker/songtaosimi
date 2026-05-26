export const STORAGE_KEYS = {
  TOKEN: 'fund_ai_token',
  USER: 'fund_ai_user',
  REFRESH_TOKEN: 'fund_ai_refresh_token',
  PRIVACY_MODE: 'fund_ai_privacy_mode',
} as const

// 迁移旧键名 → 新键名
export function migrateStorage(): void {
  const legacy = 'fund-ai-privacy-mode'
  if (localStorage.getItem(legacy) !== null) {
    localStorage.setItem(STORAGE_KEYS.PRIVACY_MODE, localStorage.getItem(legacy)!)
    localStorage.removeItem(legacy)
  }
}
