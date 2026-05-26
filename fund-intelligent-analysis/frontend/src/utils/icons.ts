// 仅注册实际使用的 Element Plus 图标，减少打包体积
import type { App } from 'vue'
import {
  ArrowLeft, ArrowRight,
  Calendar, Camera, Check, CircleCheck, Close,
  Coin, DataAnalysis, Delete, Document,
  FullScreen, Hide, Histogram, Loading, MagicStick,
  Memo, MoreFilled,
  Plus, Position, Refresh, RefreshLeft, RefreshRight, Setting,
  SwitchButton, TrendCharts, View, Wallet, WarningFilled,
} from '@element-plus/icons-vue'

const icons = [
  ArrowLeft, ArrowRight, Calendar, Camera, Check, CircleCheck, Close,
  Coin, DataAnalysis, Delete, Document, FullScreen, Hide, Histogram,
  Loading, MagicStick, Memo, MoreFilled,
  Plus, Position, Refresh, RefreshLeft, RefreshRight, Setting,
  SwitchButton, TrendCharts, View, Wallet, WarningFilled,
]

export function registerIcons(app: App) {
  for (const icon of icons) {
    app.component(icon.name!, icon)
  }
}
