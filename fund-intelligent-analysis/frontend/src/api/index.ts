import request from './request'

// 本地账号
export const getBootstrapStatus = () => request.get('/auth/bootstrap-status')
export const setupOwner = (data: any) => request.post('/auth/setup', data)
export const login = (data: any) => request.post('/auth/login', data)
export const getCurrentUser = () => request.get('/auth/me')
export const changePassword = (data: any) => request.post('/auth/change-password', data)
export const refreshAuthToken = (refreshToken: string) => request.post('/auth/refresh', null, { headers: { 'X-Refresh-Token': refreshToken } })
export const recoverPassword = (data: any) => request.post('/auth/recover', data)

// 基金管理
export const getFunds = (params?: any) => request.get('/funds', { params })
export const getFund = (code: string) => request.get(`/funds/${code}`)
export const addFund = (data: any) => request.post('/funds', data)
export const deleteFund = (code: string) => request.delete(`/funds/${code}`)
export const getFundNavHistory = (code: string, limit = 30) => request.get(`/funds/${code}/nav-history`, { params: { limit } })
export const getFundAnalysis = (code: string, limit = 180) => request.get(`/funds/${code}/analysis`, { params: { limit } })
// 联网搜索基金信息
export const searchFundOnline = (fundCode: string) => request.get(`/funds/search/${fundCode}`)

// 持仓管理
export const getHoldings = (params?: any) => request.get('/holdings', { params })
export const getHoldingsSummary = () => request.get('/holdings/summary')
export const refreshHoldingEstimates = () => request.post('/holdings/refresh-estimates')
export const getHoldingPerformance = () => request.get('/holdings/performance')
export const getHoldingPerformanceCalendar = (params?: any) => request.get('/holdings/performance-calendar', { params })
export const getHoldingXirrMetrics = () => request.get('/holdings/metrics/xirr')
export const getHoldingDrawdownMetrics = () => request.get('/holdings/metrics/drawdown')
export const getHoldingBenchmarkCompare = () => request.get('/holdings/metrics/benchmark-compare')

// P0.2 — 基金经理 + 预警
export const getFundManagers = (code: string) => request.get(`/funds/${code}/managers`)
export const syncFundManagers = (code: string) => request.post(`/funds/${code}/managers/sync`)
export const syncAllManagers = () => request.post('/manager-alerts/sync-all', {}, { timeout: 180000 })
export const getManagerAlerts = (onlyUnread = true, limit = 50) =>
  request.get('/manager-alerts', { params: { only_unread: onlyUnread, limit } })
export const markManagerAlertRead = (id: number) => request.put(`/manager-alerts/${id}/read`)

// P0.3 — 持仓重叠度
export const getOverlapReport = () => request.get('/risk-exposure/overlap')
export const syncOverlapHoldings = () => request.post('/risk-exposure/overlap/sync', {}, { timeout: 300000 })
export const syncOverlapSingle = (code: string) => request.post(`/risk-exposure/overlap/sync/${code}`, {}, { timeout: 60000 })

// P2.2 — 决策复盘
export const getBehaviorBias = (month?: string) =>
  request.get('/decision-review/bias', { params: month ? { month } : {} })
export const persistBehaviorBias = (month?: string) =>
  request.post('/decision-review/bias/persist', null, { params: month ? { month } : {} })
export const getBiasHistory = (limit = 12) =>
  request.get('/decision-review/bias/history', { params: { limit } })
export const getDecisions = (month?: string, limit = 100) =>
  request.get('/decision-review/decisions', { params: { ...(month ? { month } : {}), limit } })
export const runFullReview = () => request.post('/decision-review/run')

// P2.1 — 费率账本
export const getFeeSchedules = () => request.get('/fund-fees/schedules')
export const getFeeSchedule = (code: string) => request.get(`/fund-fees/schedules/${code}`)
export const saveFeeSchedule = (code: string, data: any) => request.put(`/fund-fees/schedules/${code}`, data)
export const runFeeAccrual = () => request.post('/fund-fees/accrual/run')
export const getYearlyLedger = (year?: number) => request.get('/fund-fees/ledger/yearly', { params: year ? { year } : {} })
export const estimateRedemption = (code: string, opts: { redeem_shares?: number; redeem_amount?: number } = {}) =>
  request.get(`/fund-fees/redemption-estimate/${code}`, { params: opts })

// P1.3 — 用户画像
export const getUserProfile = () => request.get('/user/profile')
export const saveUserProfile = (data: any) => request.put('/user/profile', data)
export const recommendAllocation = () => request.post('/user/profile/recommend-allocation')

// P1.2 — 资产配置目标
export const getAllocationTargets = () => request.get('/asset-allocation/targets')
export const saveAllocationTargets = (items: any[]) => request.put('/asset-allocation/targets', items)
export const resetAllocationTargets = () => request.delete('/asset-allocation/targets')
export const getCurrentAllocation = () => request.get('/asset-allocation/current')
export const getAllocationDeviations = (persist = false) =>
  request.get('/asset-allocation/deviations', { params: { persist } })
export const getRebalanceAlerts = (onlyUnack = true) =>
  request.get('/asset-allocation/alerts', { params: { only_unack: onlyUnack } })
export const ackRebalanceAlert = (id: number) => request.put(`/asset-allocation/alerts/${id}/ack`)

// P1.1 — 定投计划
export const getInvestmentPlans = (activeOnly = true) =>
  request.get('/investment-plans', { params: { active_only: activeOnly } })
export const createInvestmentPlan = (data: any) => request.post('/investment-plans', data)
export const updateInvestmentPlan = (id: number, data: any) => request.put(`/investment-plans/${id}`, data)
export const deactivateInvestmentPlan = (id: number) => request.delete(`/investment-plans/${id}`)
export const getUpcomingInvestments = (daysAhead = 7) =>
  request.get('/investment-plans/upcoming', { params: { days_ahead: daysAhead } })
export const getInvestmentSmileCurve = (id: number) => request.get(`/investment-plans/${id}/smile-curve`)
export const reconcileInvestmentPlan = (id: number) => request.post(`/investment-plans/${id}/reconcile`)
export const addHolding = (data: any) => request.post('/holdings', data)
export const updateHolding = (code: string, data: any) => request.put(`/holdings/${code}`, data)
export const deleteHolding = (code: string) => request.delete(`/holdings/${code}`)

// 基金组
export const getGroups = () => request.get('/groups')
export const createGroup = (data: any) => request.post('/groups', data)
export const updateGroup = (id: number, data: any) => request.put(`/groups/${id}`, data)
export const updateGroupMembers = (id: number, fundCodes: string[]) => request.put(`/groups/${id}/members`, { fund_codes: fundCodes })
export const deleteGroup = (id: number, deleteHoldings = false) => request.delete(`/groups/${id}`, { params: { delete_holdings: deleteHoldings } })

// 交易记录
export const getTrades = (params?: any) => request.get('/trades', { params })
export const addTrade = (data: any) => request.post('/trades', data)
export const updateTrade = (id: number, data: any) => request.put(`/trades/${id}`, data)
export const deleteTrade = (id: number) => request.delete(`/trades/${id}`)
export const getTradeStats = () => request.get('/trades/stats')

// 行情数据
export const getIndices = () => request.get('/market/indices')
export const getSectors = (type = 'sector') => request.get('/market/sectors', { params: { snapshot_type: type } })
export const getBoardRankings = (type = 'sector', limit = 20, live = false) =>
  request.get('/market/board-rankings', { params: { snapshot_type: type, limit, live }, timeout: 60000 })
export const getGlobalIndices = () => request.get('/market/global')
export const refreshMarketData = () => request.post('/market/refresh', {}, { timeout: 120000 })
export const getFundEstimate = (code: string) => request.get(`/market/fund-estimate/${code}`)
export const getMarketHistory = (symbol: string, days = 30) => request.get(`/market/history/${symbol}`, { params: { days } })
export const getMarketDetail = (symbol: string, params?: any) => request.get(`/market/detail/${symbol}`, { params })

// 新闻
export const getNews = (params?: any) => request.get('/news', { params })
export const getNewsInsights = () => request.get('/news/insights/summary')
export const getNewsImpact = (newsId: number) => request.get(`/news/impact/${newsId}`)
export const getDailyImpactReport = () => request.get('/news/impact/daily')
export const classifyExistingNews = () => request.post('/news/classify-existing', {}, { timeout: 120000 })
export const refreshNews = () => request.post('/news/refresh', {}, { timeout: 120000 })

// AI建议
export const getAiAdvices = (limit = 30) => request.get('/ai/advice', { params: { limit } })
export const getLatestAdvice = () => request.get('/ai/advice/latest')
export const generateAdvice = (refresh = false) =>
  request.post('/ai/advice/generate-async', {}, { params: { refresh }, timeout: 30000 })
export const getAdviceGenerationStatus = () => request.get('/ai/advice/generate/status')
export const markAdviceRead = (id: number) => request.put(`/ai/advice/${id}/read`)
export const sendLatestToFeishu = () => request.post('/ai/notify/send-latest')

// OCR
export const uploadOcr = (formData: FormData, source: string) => {
  formData.append('source', source)
  return request.post('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}
export const confirmOcr = (items: any[]) => request.post('/ocr/confirm', items)
export const getOcrSyncStatus = () => request.get('/ocr/status')
export const previewOcrDiff = (items: any[], tradeDate?: string) =>
  request.post('/ocr/diff-preview', { items, trade_date: tradeDate })
export const confirmOcrSnapshot = (items: any[], options?: { trade_date?: string; generate_trades?: boolean }) =>
  request.post('/ocr/confirm-snapshot', { items, ...(options || {}) })

// 上传交易记录截图并识别
export const uploadOcrTrades = (formData: FormData) => {
  return request.post('/ocr/upload-trades', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

// 确认导入交易记录
export const confirmOcrTrades = (items: any[]) =>
  request.post('/ocr/confirm-trades', items)

// 仪表盘
export const getDashboardOverview = () => request.get('/dashboard/overview')
export const getCommandCenter = () => request.get('/dashboard/command-center')
export const getPnlCurve = (days = 30) => request.get('/dashboard/pnl-curve', { params: { days } })
export const getAssetAllocation = () => request.get('/dashboard/asset-allocation')

// 设置
export const getSettings = () => request.get('/settings')
export const getSchedulerStatus = () => request.get('/settings/scheduler-status')
export const getDiagnostics = () => request.get('/settings/diagnostics')
export const triggerJob = (jobId: string) => request.post(`/settings/scheduler/trigger/${jobId}`)
