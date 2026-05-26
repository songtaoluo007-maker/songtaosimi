/**
 * 前端入口 — V2
 *
 * V2 改动：
 * - 启动时调用 migrateStorage()，把老版本的 `fund-ai-privacy-mode` 等键名迁移到 STORAGE_KEYS
 *   原 v1 写了 migrateStorage 但从未调用，老用户的隐私模式开关每次都会失效
 * - 把 ElementPlus / Pinia / Router 的注册顺序保持与 v1 一致，避免组件初始化时拿不到全局服务
 */
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/variables.css'
import './styles/global.css'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import { registerIcons } from './utils/icons'
import { migrateStorage } from './utils/constants'

// 关键修复：v1 写了 migrateStorage 但没调用，导致老用户的偏好失效
migrateStorage()

const app = createApp(App)
const pinia = createPinia()

registerIcons(app)
app.use(ElementPlus, { locale: zhCn })
app.use(pinia)
app.use(router)
app.mount('#app')
