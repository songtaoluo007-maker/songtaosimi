// 基金智能分析 — 核心类型定义

// ---------- 基金 ----------
export interface Fund {
  fund_code: string
  fund_name: string
  fund_type: string
  latest_nav: number | null
  latest_nav_date: string | null
  estimated_nav: number | null
  estimated_change_pct: number | null
  created_at: string
}

export interface FundNavPoint {
  date: string
  nav: number
  cumulative_nav?: number
  daily_return?: number
}

export interface FundAnalysis {
  fund: Fund
  nav_history: FundNavPoint[]
  volatility_ratio?: number
  sharpe_ratio?: number
  max_drawdown?: number
  returns: {
    ytd?: number
    m1?: number
    m3?: number
    m6?: number
    y1?: number
    total?: number
  }
}

// ---------- 持仓 ----------
export interface Holding {
  fund_code: string
  fund_name: string
  fund_type: string
  shares: number
  cost_price: number
  cost_amount: number
  current_nav: number | null
  current_value: number | null
  pnl_amount: number
  pnl_ratio: number
  daily_pnl: number
  daily_pnl_ratio: number
  source: string
  is_active: boolean
  group_id?: number
  group_name?: string
}

export interface HoldingSummary {
  total_cost: number
  total_value: number
  total_pnl: number
  total_pnl_ratio: number
  daily_pnl: number
  daily_pnl_ratio: number
  holding_count: number
}

export interface HoldingPerformance {
  fund_code: string
  fund_name: string
  pnl_amount: number
  pnl_ratio: number
  weight: number
  daily_pnl: number
  daily_pnl_ratio: number
}

// ---------- 基金组 ----------
export interface FundGroup {
  id: number
  name: string
  description: string
  color: string
  is_active: boolean
  created_at: string
}

// ---------- 交易记录 ----------
export interface Trade {
  id: number
  fund_code: string
  fund_name?: string
  trade_type: '买入' | '卖出'
  shares: number
  nav_price: number
  amount: number
  fee: number
  trade_date: string
  source: string
  note: string
  created_at: string
}

export interface TradeStats {
  buy_total: number
  sell_total: number
  trade_count: number
  fund_count: number
  avg_holding_days: number | null
}

// ---------- 行情 ----------
export interface MarketSnapshot {
  id?: number
  symbol: string
  name: string
  snapshot_type: string
  price: number
  change_pct: number
  change_amount?: number
  volume?: number
  turnover?: number
  high?: number
  low?: number
  open?: number
  prev_close?: number
  snapshot_date: string
  snapshot_time?: string
}

export interface BoardRanking {
  symbol: string
  name: string
  price: number
  change_pct: number
  net_inflow?: number
  leading_stock?: string
  leading_stock_change_pct?: number
  heat_score?: number
}

export interface GlobalIndex {
  symbol: string
  name: string
  price: number
  change_pct: number
  change_amount?: number
  snapshot_date: string
}

// ---------- 新闻 ----------
export interface NewsItem {
  id: number
  title: string
  content: string
  source: string
  publish_time: string
  category: string
  sub_category: string
  importance_score: number
  sentiment: 'positive' | 'negative' | 'neutral'
  related_topics: string[]
  is_breaking: boolean
  keyword: string
  url?: string
}

export interface NewsInsight {
  date: string
  sentiment_distribution: Record<string, number>
  important_topics: string[]
  breaking_count: number
}

// ---------- AI 建议 ----------
export type MarketView = 'bullish' | 'neutral' | 'bearish'
export type RiskLevel = 'low' | 'medium' | 'high'
export type ActionType = 'add' | 'reduce' | 'hold'

export interface AiAdviceAction {
  fund_code: string
  fund_name: string
  action: ActionType
  reason: string
  urgency: 'high' | 'medium' | 'low'
  suggested_amount?: number
}

export interface AiAdvice {
  id: number
  created_at: string
  market_view: MarketView
  risk_level: RiskLevel
  overall_suggestion: string
  data_quality: Record<string, number>
  actions: AiAdviceAction[]
  is_read: boolean
}

export interface CommandCenter {
  overview: string
  risk: RiskLevel
  market_view: MarketView
  opportunities: BoardRanking[]
  alerts: string[]
  ai_ready: boolean
  generation_status?: 'idle' | 'running' | 'done' | 'error'
}

// ---------- Dashboard ----------
export interface DashboardOverview {
  portfolio: HoldingSummary
  indices: MarketSnapshot[]
  latest_advice: AiAdvice | null
  recent_news: NewsItem[]
}

export interface PnlCurvePoint {
  date: string
  pnl_amount: number
  pnl_ratio: number
  total_value: number
}

export interface AssetAllocation {
  by_type: { name: string; value: number; pct: number }[]
  by_fund: { fund_code: string; fund_name: string; value: number; pct: number }[]
}

// ---------- 认证 ----------
export interface UserInfo {
  id: number
  username: string
  display_name: string
  role: string
  last_login_at: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_at: string
  user: UserInfo
}

// ---------- 设置 ----------
export interface SystemSettings {
  has_api_key: boolean
  deepseek_base_url: string
  backend_port: number
  market_collect_interval: number
  ai_advice_time: string
}

export interface SchedulerStatus {
  running: boolean
  jobs: { id: string; name: string; next_run: string | null; running: boolean }[]
}

export interface SystemDiagnostics {
  checks: {
    name: string
    status: 'ok' | 'warning' | 'error'
    detail: string
    suggestion?: string
  }[]
  overall: 'ok' | 'warning' | 'error'
}

// ---------- API 通用 ----------
export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  message?: string
}
