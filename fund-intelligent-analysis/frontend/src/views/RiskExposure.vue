<template>
  <div>
    <div class="page-head">
      <div>
        <h2>组合风险暴露</h2>
        <p>基于基金标签和持仓权重，透视行业/主题/风格维度的真实风险</p>
      </div>
      <div class="head-actions">
        <el-button :loading="tagging" @click="handleAutoTagAll">AI 自动打标</el-button>
      </div>
    </div>

    <el-alert v-if="tagResult" :title="tagResult" type="success" show-icon :closable="true" @close="tagResult = ''" style="margin-bottom: 16px;" />

    <!-- P1.2 目标资产配置 + 再平衡 -->
    <el-card shadow="hover" style="margin-bottom: 20px;">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:bold;">目标资产配置（纪律工具）</span>
          <div style="display:flex;gap:8px;align-items:center;">
            <span v-if="deviations.needs_rebalance" style="color:var(--danger-500);font-size:12px;">
              ⚠ 偏离超阈值，建议再平衡
            </span>
            <el-button size="small" @click="openAllocationEdit">编辑目标</el-button>
          </div>
        </div>
      </template>
      <div v-if="!allocationTargets.length" class="empty-chart" style="height:120px;">
        <div style="text-align:center;">
          <p>尚未设置目标资产配置 — 点击右上"编辑目标"开始</p>
          <p style="font-size:12px;color:var(--gray-400);">设定 60% 股 / 30% 债 / 10% 黄金 类的纪律目标，偏离超阈值会提醒再平衡</p>
        </div>
      </div>
      <template v-else>
        <el-table :data="deviations.deviations || []" stripe size="small">
          <el-table-column prop="label" label="资产大类" min-width="120" />
          <el-table-column label="目标" width="100" align="right">
            <template #default="{ row }">{{ row.target_pct }}%</template>
          </el-table-column>
          <el-table-column label="当前" width="100" align="right">
            <template #default="{ row }">{{ row.current_pct }}%</template>
          </el-table-column>
          <el-table-column label="偏离" width="110" align="right">
            <template #default="{ row }">
              <span :class="row.within_tolerance ? '' : 'text-warn'">
                {{ row.deviation_pct >= 0 ? '+' : '' }}{{ row.deviation_pct }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="建议" min-width="160">
            <template #default="{ row }">
              <el-tag v-if="row.within_tolerance" type="success" size="small">达标</el-tag>
              <template v-else>
                <el-tag :type="row.suggested_action === 'add' ? 'danger' : 'success'" size="small">
                  {{ row.suggested_action === 'add' ? '加仓' : '减仓' }} ¥{{ formatMoneyDev(row.suggested_amount) }}
                </el-tag>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <!-- 编辑目标弹层 -->
    <el-dialog v-model="allocationEditVisible" title="编辑目标资产配置" width="640px">
      <p style="color:var(--gray-500);font-size:13px;margin:0 0 16px;">
        合计应接近 100%。建议留 5-10% 现金 buffer。
      </p>
      <el-table :data="editTargets" border>
        <el-table-column label="资产大类" min-width="150">
          <template #default="{ row }">{{ row.label }}</template>
        </el-table-column>
        <el-table-column label="目标占比 %" width="180">
          <template #default="{ row }">
            <el-input-number v-model="row.target_pct" :min="0" :max="100" :step="5" :precision="1" />
          </template>
        </el-table-column>
        <el-table-column label="容差 ±%" width="160">
          <template #default="{ row }">
            <el-input-number v-model="row.tolerance_pct" :min="1" :max="20" :step="1" :precision="1" />
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top:12px;font-size:13px;">
        合计：<strong :class="Math.abs(editTotal - 100) > 1 ? 'text-warn' : ''">{{ editTotal.toFixed(1) }}%</strong>
        <span style="color:var(--gray-400);margin-left:8px;">（应接近 100%）</span>
      </div>
      <template #footer>
        <el-button @click="allocationEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTargets" @click="handleSaveTargets">保存</el-button>
      </template>
    </el-dialog>

    <!-- 集中度卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px;" v-if="concentration.total_holdings">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">最大持仓占比</div>
          <div class="metric-value" :class="concentration.top1_pct > 15 ? 'text-warn' : ''">{{ concentration.top1_pct }}%</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">前3大占比</div>
          <div class="metric-value" :class="concentration.top3_pct > 45 ? 'text-warn' : ''">{{ concentration.top3_pct }}%</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">前5大占比</div>
          <div class="metric-value">{{ concentration.top5_pct }}%</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">高波动占比</div>
          <div class="metric-value" :class="concentration.high_volatility_pct > 50 ? 'text-warn' : ''">{{ concentration.high_volatility_pct }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert v-if="concentration.warning && concentration.warning !== '组合分散度良好'" :title="concentration.warning" type="warning" show-icon style="margin-bottom: 16px;" />

    <!-- 图表区域 -->
    <el-row :gutter="16" style="margin-bottom: 20px;">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold;">行业暴露</span></template>
          <v-chart v-if="industry.exposure?.length" :option="industryOption" style="height: 320px;" autoresize />
          <div v-else class="empty-chart">暂无行业标签数据，请先 AI 打标</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold;">主题暴露</span></template>
          <v-chart v-if="theme.exposure?.length" :option="themeOption" style="height: 320px;" autoresize />
          <div v-else class="empty-chart">暂无主题标签数据，请先 AI 打标</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 20px;">
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold;">风格暴露</span></template>
          <v-chart v-if="styleData.exposure?.length" :option="styleOption" style="height: 300px;" autoresize />
          <div v-else class="empty-chart">暂无风格标签数据，请先 AI 打标</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="hover" v-if="concentration.theme_concentration?.length">
          <template #header><span style="font-weight: bold;">同主题集中度</span></template>
          <v-chart :option="themeConcOption" style="height: 300px;" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- P0.3 真实分散度 -->
    <el-card shadow="hover" style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold;">实际分散度（基于底层持股）</span>
          <div style="display: flex; gap: 8px; align-items: center;">
            <span v-if="overlap.data_coverage?.coverage_pct !== undefined"
                  style="font-size:12px;color:var(--gray-400);">
              覆盖率 {{ overlap.data_coverage.coverage_pct }}%
            </span>
            <el-button size="small" :loading="overlapSyncing" @click="handleSyncOverlap">
              <el-icon><Refresh /></el-icon> 拉取最新季报持股
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!overlap.heatmap?.labels?.length" class="empty-chart">
        <div style="text-align:center;">
          <p>暂无底层持股数据 — 点击右上 "拉取最新季报持股" 同步</p>
          <p style="font-size:12px;color:var(--gray-400);margin-top:4px;">
            数据源：AKShare 基金前十大重仓股，季报披露日（4/8/10/次年1 月底）后刷新
          </p>
        </div>
      </div>

      <template v-else>
        <!-- 评分 + 警示 -->
        <el-row :gutter="16" style="margin-bottom: 18px;">
          <el-col :xs="12" :sm="8">
            <div class="metric-card">
              <div class="metric-label">真实分散度评分</div>
              <div class="metric-value" :class="diversificationClass(overlap.diversification_score)">
                {{ overlap.diversification_score }}
              </div>
              <small style="color:var(--gray-400);">满分 100，越高越分散</small>
            </div>
          </el-col>
          <el-col :xs="12" :sm="8">
            <div class="metric-card">
              <div class="metric-label">平均两两重叠</div>
              <div class="metric-value" :class="(overlap.avg_overlap_pct || 0) > 30 ? 'text-warn' : ''">
                {{ overlap.avg_overlap_pct }}%
              </div>
              <small style="color:var(--gray-400);">{{ overlap.pairs?.length || 0 }} 对基金</small>
            </div>
          </el-col>
          <el-col :xs="24" :sm="8">
            <div class="metric-card">
              <div class="metric-label">最高单对重叠</div>
              <div class="metric-value" :class="(overlap.max_overlap_pct || 0) > 40 ? 'text-warn' : ''">
                {{ overlap.max_overlap_pct }}%
              </div>
              <small style="color:var(--gray-400);">两只基金共同重仓比例</small>
            </div>
          </el-col>
        </el-row>

        <el-alert
          v-if="overlap.warning && overlap.warning !== '组合实际分散度良好'"
          :title="overlap.warning"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 16px;"
        />

        <el-row :gutter="16">
          <el-col :xs="24" :lg="14">
            <div style="font-weight:600;margin-bottom:8px;font-size:13px;color:var(--gray-700);">
              重叠度热力图
            </div>
            <v-chart :option="overlapHeatmapOption" style="height: 360px;" autoresize />
          </el-col>
          <el-col :xs="24" :lg="10">
            <div style="font-weight:600;margin-bottom:8px;font-size:13px;color:var(--gray-700);">
              重复重仓股 Top 10
            </div>
            <el-table :data="overlap.duplicated_stocks || []" stripe size="small" height="360">
              <el-table-column prop="stock_name" label="股票" min-width="100">
                <template #default="{ row }">
                  <strong>{{ row.stock_name }}</strong>
                  <small style="display:block;color:var(--gray-400);">{{ row.stock_code }}</small>
                </template>
              </el-table-column>
              <el-table-column label="基金数" width="70" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.fund_count >= 3 ? 'danger' : 'warning'" size="small">
                    {{ row.fund_count }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="组合暴露" width="100" align="right">
                <template #default="{ row }">
                  <strong :class="row.total_exposure_pct > 5 ? 'text-warn' : ''">
                    {{ row.total_exposure_pct }}%
                  </strong>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="!overlap.duplicated_stocks?.length" style="text-align:center;color:var(--gray-400);padding:24px;font-size:13px;">
              无跨基金重复重仓
            </div>
          </el-col>
        </el-row>

        <div v-if="overlap.data_coverage?.without_data?.length"
             style="margin-top:12px;font-size:12px;color:var(--gray-500);">
          ⓘ 未参与计算的基金：{{ overlap.data_coverage.without_data.join('、') }}
          （这些基金暂无前十大持股数据，点击上方按钮可补齐）
        </div>
      </template>
    </el-card>

    <!-- 标签管理 -->
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold;">基金标签管理</span>
          <el-select v-model="selectedFund" placeholder="选择基金" style="width: 220px;" @change="loadFundTags" filterable>
            <el-option v-for="f in fundList" :key="f.fund_code" :label="`${f.fund_code} ${f.fund_name}`" :value="f.fund_code" />
          </el-select>
        </div>
      </template>
      <template v-if="selectedFund && fundTagData">
        <div style="margin-bottom: 12px;">
          <el-tag v-for="t in allTags" :key="t.id" :type="tagColor(t.tag_type)" closable @close="handleDeleteTag(t.id)" style="margin: 2px 4px;">
            {{ t.tag_type }}: {{ t.name }}
          </el-tag>
          <el-button size="small" :icon="Plus" circle @click="showAddTag = true" style="margin-left: 8px;" />
        </div>
        <el-button size="small" @click="handleAutoTag(selectedFund)" :loading="taggingOne">AI 重新打标</el-button>
      </template>
      <div v-else style="text-align: center; color: var(--gray-400); padding: 24px;">选择一只基金查看标签</div>
    </el-card>

    <!-- 添加标签对话框 -->
    <el-dialog v-model="showAddTag" title="添加标签" width="400px">
      <el-form :model="newTag" label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="newTag.tag_type">
            <el-option value="industry" label="行业" />
            <el-option value="theme" label="主题" />
            <el-option value="style" label="风格" />
            <el-option value="risk" label="风险" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="newTag.tag_name" />
        </el-form-item>
        <el-form-item label="权重">
          <el-input-number v-model="newTag.tag_value" :min="0" :max="1" :step="0.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddTag = false">取消</el-button>
        <el-button type="primary" @click="handleAddTag">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { PieChart, BarChart, RadarChart, HeatmapChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, VisualMapComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import request from '../api/request'

use([PieChart, BarChart, RadarChart, HeatmapChart, TitleComponent, TooltipComponent, LegendComponent, VisualMapComponent, GridComponent, CanvasRenderer])

const industry = ref<any>({ exposure: [], details: [] })
const theme = ref<any>({ exposure: [] })
const styleData = ref<any>({ exposure: [] })
const concentration = ref<any>({})
const fundList = ref<any[]>([])
const selectedFund = ref('')
const fundTagData = ref<any>(null)
const tagging = ref(false)
const taggingOne = ref(false)
const tagResult = ref('')
const showAddTag = ref(false)
const newTag = ref({ tag_type: 'industry', tag_name: '', tag_value: 1.0 })

const allTags = computed(() => {
  if (!fundTagData.value) return []
  const result: any[] = []
  for (const [type, tags] of Object.entries(fundTagData.value)) {
    for (const t of (tags as any[])) {
      result.push({ ...t, tag_type: type })
    }
  }
  return result
})

function tagColor(type: string) {
  const m: Record<string,string> = { industry: '', theme: 'success', style: 'warning', risk: 'danger' }
  return m[type] || ''
}

// Chart options
const industryOption = computed(() => ({
  tooltip: { trigger: 'item' as const, formatter: '{b}: {c}%' },
  series: [{
    type: 'pie', radius: ['40%', '70%'], center: ['50%', '50%'],
    label: { show: true, formatter: '{b}\n{c}%' },
    data: industry.value.exposure.map((i: any) => ({ name: i.name, value: i.value })),
  }],
}))

const themeOption = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  xAxis: { type: 'category' as const, data: theme.value.exposure.map((i: any) => i.name), axisLabel: { rotate: 30 } },
  yAxis: { type: 'value' as const, name: '%' },
  series: [{ type: 'bar', data: theme.value.exposure.map((i: any) => i.value), itemStyle: { borderRadius: [4, 4, 0, 0] } }],
  grid: { left: 50, right: 20, bottom: 80, top: 10 },
}))

const styleOption = computed(() => ({
  tooltip: {},
  radar: {
    indicator: styleData.value.exposure.map((i: any) => ({ name: i.name, max: Math.max(...styleData.value.exposure.map((x: any) => x.value)) * 1.2 || 100 })),
  },
  series: [{ type: 'radar', data: [{ value: styleData.value.exposure.map((i: any) => i.value), name: '组合风格' }], areaStyle: { opacity: 0.3 } }],
}))

const themeConcOption = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  xAxis: { type: 'category' as const, data: concentration.value.theme_concentration?.map((i: any) => i.theme) || [] },
  yAxis: { type: 'value' as const, name: '%' },
  series: [{ type: 'bar', data: concentration.value.theme_concentration?.map((i: any) => i.weight_pct) || [], itemStyle: { color: '#e6a23c', borderRadius: [4, 4, 0, 0] } }],
  grid: { left: 50, right: 20, bottom: 80, top: 10 },
}))

async function loadReport() {
  try {
    const res = await request.get('/risk-exposure/report') as any
    industry.value = res.industry || { exposure: [], details: [] }
    theme.value = res.theme || { exposure: [] }
    styleData.value = res.style || { exposure: [] }
    concentration.value = res.concentration || {}
  } catch { /* empty */ }
}

async function loadFunds() {
  try {
    fundList.value = await request.get('/funds') as any
  } catch { fundList.value = [] }
}

async function loadFundTags() {
  if (!selectedFund.value) return
  try {
    fundTagData.value = await request.get(`/risk-exposure/fund/${selectedFund.value}/tags`) as any
  } catch { fundTagData.value = null }
}

async function handleAutoTag(code: string) {
  taggingOne.value = true
  try {
    const res = await request.post(`/risk-exposure/auto-tag/${code}`) as any
    ElMessage.success(`${code} 打标完成: ${res.tags?.length || 0} 个标签`)
    await loadFundTags()
    await loadReport()
  } catch (e: any) {
    ElMessage.error('打标失败: ' + (e.response?.data?.detail || e.message))
  } finally { taggingOne.value = false }
}

async function handleAutoTagAll() {
  tagging.value = true
  try {
    const res = await request.post('/risk-exposure/auto-tag-all') as any
    tagResult.value = `打标完成: ${res.tagged} 只成功, ${res.failed} 只失败, 共 ${res.total} 只`
    await loadReport()
  } catch (e: any) {
    ElMessage.error('批量打标失败: ' + (e.response?.data?.detail || e.message))
  } finally { tagging.value = false }
}

async function handleDeleteTag(tagId: number) {
  try {
    await request.delete(`/risk-exposure/tags/${tagId}`)
    await loadFundTags()
    await loadReport()
  } catch { /* */ }
}

async function handleAddTag() {
  if (!selectedFund.value || !newTag.value.tag_name) return
  try {
    await request.post(`/risk-exposure/fund/${selectedFund.value}/tags`, newTag.value)
    showAddTag.value = false
    newTag.value = { tag_type: 'industry', tag_name: '', tag_value: 1.0 }
    await loadFundTags()
    await loadReport()
  } catch (e: any) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

// P1.2 — 目标资产配置
import {
  getAllocationTargets, saveAllocationTargets,
  getAllocationDeviations,
} from '../api'

const allocationTargets = ref<any[]>([])
const deviations = ref<any>({})
const allocationEditVisible = ref(false)
const editTargets = ref<any[]>([])
const savingTargets = ref(false)

const editTotal = computed(() =>
  editTargets.value.reduce((s, t) => s + Number(t.target_pct || 0), 0))

const ASSET_CLASS_LABELS: Record<string, string> = {
  equity_a: 'A股权益',
  equity_hk: '港股权益',
  equity_us: '海外权益 (QDII)',
  bond: '债券',
  gold: '黄金/贵金属',
  cash: '货币/现金',
}

async function loadAllocation() {
  try {
    const tRes: any = await getAllocationTargets()
    allocationTargets.value = tRes?.items || []
    const dRes: any = await getAllocationDeviations(false)
    deviations.value = dRes || {}
  } catch {
    allocationTargets.value = []
    deviations.value = {}
  }
}

function openAllocationEdit() {
  const classes = ['equity_a', 'equity_hk', 'equity_us', 'bond', 'gold', 'cash']
  const byClass = new Map(allocationTargets.value.map(t => [t.asset_class, t]))
  editTargets.value = classes.map(cls => {
    const existing = byClass.get(cls) as any
    return {
      asset_class: cls,
      label: ASSET_CLASS_LABELS[cls],
      target_pct: existing?.target_pct ?? 0,
      tolerance_pct: existing?.tolerance_pct ?? 5,
    }
  })
  allocationEditVisible.value = true
}

async function handleSaveTargets() {
  if (Math.abs(editTotal.value - 100) > 1) {
    ElMessage.warning(`合计 ${editTotal.value.toFixed(1)}%，应接近 100%`)
    return
  }
  savingTargets.value = true
  try {
    await saveAllocationTargets(editTargets.value.filter((t: any) => Number(t.target_pct) > 0))
    ElMessage.success('已保存')
    allocationEditVisible.value = false
    await loadAllocation()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingTargets.value = false
  }
}

function formatMoneyDev(v: any) {
  return (Number(v) || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

// P0.3 — 持仓重叠度
import { getOverlapReport, syncOverlapHoldings } from '../api'
const overlap = ref<any>({})
const overlapSyncing = ref(false)

async function loadOverlap() {
  try {
    overlap.value = await getOverlapReport()
  } catch (e: any) {
    overlap.value = {}
  }
}
async function handleSyncOverlap() {
  overlapSyncing.value = true
  try {
    const res: any = await syncOverlapHoldings()
    ElMessage.success(`已同步 ${res?.success?.length || 0} / ${res?.checked || 0} 只基金持股`)
    await loadOverlap()
  } catch (e: any) {
    ElMessage.error('同步失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    overlapSyncing.value = false
  }
}

function diversificationClass(score: number) {
  const v = Number(score || 0)
  if (v >= 80) return 'text-good'
  if (v >= 60) return ''
  return 'text-warn'
}

const overlapHeatmapOption = computed(() => {
  const labels: any[] = overlap.value.heatmap?.labels || []
  const data: any[] = overlap.value.heatmap?.data || []
  const names = labels.map(l => l.code)
  return {
    tooltip: {
      position: 'top',
      formatter: (p: any) => {
        const [i, j, v] = p.data
        const a = labels[i]?.name || labels[i]?.code || ''
        const b = labels[j]?.name || labels[j]?.code || ''
        if (i === j) return `${a}<br/>自身 100%`
        return `${a}<br/>vs<br/>${b}<br/>重叠 <strong>${v}%</strong>`
      },
    },
    grid: { top: 30, left: 90, right: 20, bottom: 70 },
    xAxis: {
      type: 'category', data: names,
      axisLabel: { rotate: 60, fontSize: 11, interval: 0 },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category', data: names,
      axisLabel: { fontSize: 11 },
      splitArea: { show: true },
    },
    visualMap: {
      min: 0, max: 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 5,
      itemHeight: 80,
      itemWidth: 14,
      inRange: { color: ['#f0f9eb', '#fdf6ec', '#fef0f0', '#dc2626'] },
      text: ['高重叠', '低重叠'],
      textStyle: { fontSize: 11 },
    },
    series: [{
      type: 'heatmap',
      data: data,
      label: {
        show: data.length <= 100,
        formatter: (p: any) => {
          const v = p.data[2]
          return v >= 5 ? `${v}` : ''
        },
        fontSize: 10,
      },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.3)' } },
    }],
  }
})

onMounted(async () => {
  await Promise.all([loadReport(), loadFunds(), loadOverlap(), loadAllocation()])
})
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-head h2 { margin: 0; }
.page-head p { margin: 4px 0 0; color: var(--gray-400); font-size: 13px; }
.head-actions { display: flex; gap: 8px; }

.metric-card { text-align: center; }
.metric-label { font-size: 11px; color: var(--gray-400); text-transform: uppercase; }
.metric-value { font-size: 28px; font-weight: 700; color: var(--gray-900); margin-top: 8px; }
.metric-value.text-warn { color: #e6a23c; }

.empty-chart { height: 320px; display: flex; align-items: center; justify-content: center; color: var(--gray-400); font-size: 14px; }
.text-good { color: #16a34a; }
.text-warn { color: #e6a23c; }
</style>
