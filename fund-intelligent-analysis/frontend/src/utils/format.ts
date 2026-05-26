import type { MarketView, RiskLevel } from '@/types'

export function profitClass(val: number | null | undefined): string {
  const n = Number(val ?? 0)
  return n >= 0 ? 'up' : 'down'
}

export function signedPercent(val: number | null | undefined, decimals = 2): string {
  const n = Number(val ?? 0)
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(decimals)}%`
}

export function signedMoney(val: number | null | undefined): string {
  const n = Number(val ?? 0)
  const sign = n >= 0 ? '+' : ''
  const abs = Math.abs(n)
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(2)}万`
  return `${sign}${abs.toFixed(2)}`
}

export function money(val: number | null | undefined): string {
  const n = Number(val ?? 0)
  const abs = Math.abs(n)
  if (abs >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toFixed(2)
}

export function privacyMoney(val: number | null | undefined, privacy: boolean): string {
  if (privacy) return '****'
  return `¥${money(val)}`
}

export function formatPrice(val: number | null | undefined, decimals = 2): string {
  return (Number(val ?? 0)).toFixed(decimals)
}

export function formatVolume(val: number | null | undefined): string {
  const n = Number(val ?? 0)
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return `${n}`
}

export function formatTurnover(val: number | null | undefined): string {
  const n = Number(val ?? 0)
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  return `${(n / 1e4).toFixed(0)}万`
}

export function calcBoll(values: number[], n = 20): { mid: number; upper: number; lower: number } {
  if (values.length < n) {
    const avg = values.reduce((a, b) => a + b, 0) / values.length
    return { mid: avg, upper: avg, lower: avg }
  }
  const slice = values.slice(-n)
  const mid = slice.reduce((a, b) => a + b, 0) / n
  const variance = slice.reduce((s, v) => s + (v - mid) ** 2, 0) / n
  const std = Math.sqrt(variance)
  return { mid, upper: mid + 2 * std, lower: mid - 2 * std }
}

export function marketViewLabel(view: MarketView): string {
  return { bullish: '看多', neutral: '中性', bearish: '看空' }[view] ?? view
}

export function marketViewColor(view: MarketView): string {
  return { bullish: '#F56C6C', neutral: '#909399', bearish: '#67C23A' }[view] ?? '#909399'
}

export function riskLabel(level: RiskLevel): string {
  return { low: '低风险', medium: '中等风险', high: '高风险' }[level] ?? level
}

export function riskTagType(level: RiskLevel): 'success' | 'warning' | 'danger' {
  const map: Record<RiskLevel, 'success' | 'warning' | 'danger'> = { low: 'success', medium: 'warning', high: 'danger' }
  return map[level] ?? 'warning'
}

export function displayText(value: unknown, isRestDay = false): string {
  let text = String(value ?? '')
  // 检测嵌套 JSON（模型错误地把整个输出塞进了 overall_suggestion）
  if (text.trim().startsWith('{')) {
    try {
      const nested = JSON.parse(text)
      text = nested.overall_suggestion || nested.market_reasoning || text
    } catch { /* 不是有效 JSON，保持原文 */ }
  }
  if (!isRestDay) return text
  return text
    .replaceAll('今日尾盘', '休市期间')
    .replaceAll('今日主力', '最近交易日主力')
    .replaceAll('今日资金', '最近交易日资金')
    .replaceAll('今日行情', '最近交易日行情')
    .replaceAll('今日涨跌', '最近交易日涨跌')
    .replaceAll('今日', '最近交易日')
    .replaceAll('当天', '最近交易日')
}
