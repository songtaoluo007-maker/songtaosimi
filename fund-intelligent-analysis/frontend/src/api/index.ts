import request from './request'

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
export const refreshNews = () => request.post('/news/refresh', {}, { timeout: 120000 })

// AI建议
export const getAiAdvices = (limit = 30) => request.get('/ai/advice', { params: { limit } })
export const getLatestAdvice = () => request.get('/ai/advice/latest')
export const generateAdvice = () => request.post('/ai/advice/generate', {}, { timeout: 300000 })
export const markAdviceRead = (id: number) => request.put(`/ai/advice/${id}/read`)

// OCR
export const uploadOcr = (formData: FormData, source: string) => {
  formData.append('source', source)
  return request.post('/ocr/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}
export const confirmOcr = (items: any[]) => request.post('/ocr/confirm', items)

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
