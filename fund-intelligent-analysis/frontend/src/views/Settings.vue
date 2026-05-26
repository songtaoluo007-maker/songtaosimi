<template>
  <div class="settings-page">
    <div class="page-header">
      <div>
        <h1>系统设置</h1>
        <p>系统诊断 · 配置管理 · 关于</p>
      </div>
    </div>

    <!-- Tab navigation -->
    <div class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        {{ tab.label }}
      </button>
    </div>

    <!-- ═══ 系统体检 ═══ -->
    <div v-show="activeTab === 'diagnostics'" class="tab-content">
      <div class="section-bar">
        <div>
          <h3>系统体检</h3>
          <p>实时诊断数据链路、调度器及运行环境</p>
        </div>
        <el-button size="small" :loading="diagnosticsLoading" @click="loadDiagnostics">
          <el-icon><Refresh /></el-icon> 刷新体检
        </el-button>
      </div>

      <!-- Overall status -->
      <div class="status-banner" :class="overallClass">
        <div class="status-dot" />
        <span class="status-label">{{ statusText(diagnostics.status) }}</span>
        <span class="status-meta">
          生成于 {{ diagnostics.generated_at || '-' }} ·
          {{ diagnostics.market_context || '-' }} ·
          正常 {{ diagnostics.summary?.ok || 0 }} /
          警告 {{ diagnostics.summary?.warning || 0 }} /
          严重 {{ diagnostics.summary?.critical || 0 }}
        </span>
      </div>

      <el-alert
        v-if="diagnostics.summary?.warning || diagnostics.summary?.critical"
        :type="diagnostics.summary?.critical ? 'error' : 'warning'"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
        title="系统检测到需关注的项目，请优先处理严重和警告项。"
      />

      <!-- Freshness grid -->
      <div class="label-row"><span>数据新鲜度</span></div>
      <div class="freshness-row">
        <div v-for="item in snapshotItems" :key="item.key" class="freshness-cell">
          <span class="f-label">{{ item.label }}</span>
          <strong class="f-date">{{ item.latest_date || '暂无' }}</strong>
          <span class="f-meta">{{ item.latest_time || '-' }} · {{ item.count_on_latest_date || 0 }} 条</span>
        </div>
      </div>

      <!-- Checks table -->
      <div class="label-row" style="margin-top: 24px;"><span>详细检查</span></div>
      <el-table :data="diagnostics.checks || []" stripe>
        <el-table-column prop="title" label="检查项" width="140" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span class="check-dot" :class="row.status" />
            {{ statusText(row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="message" label="结果" min-width="200" />
        <el-table-column prop="detail" label="说明" min-width="240" show-overflow-tooltip />
      </el-table>
    </div>

    <!-- ═══ 系统配置 ═══ -->
    <div v-show="activeTab === 'config'" class="tab-content">
      <div class="config-grid">
        <!-- AI Config -->
        <div class="config-card">
          <div class="config-card-head">
            <el-icon><Connection /></el-icon>
            <span>AI 模型</span>
          </div>
          <div class="config-rows">
            <div class="config-row">
              <span>模型</span>
              <code>{{ config.deepseek_model }}</code>
            </div>
            <div class="config-row">
              <span>API 地址</span>
              <code>{{ config.deepseek_base_url }}</code>
            </div>
            <div class="config-row">
              <span>API Key</span>
              <span class="key-badge" :class="{ active: config.has_api_key }">
                {{ config.has_api_key ? '已配置' : '未配置' }}
              </span>
            </div>
          </div>
          <p class="config-note">修改配置请编辑项目根目录 .env 文件，重启生效</p>
        </div>

        <!-- Collection config -->
        <div class="config-card">
          <div class="config-card-head">
            <el-icon><Timer /></el-icon>
            <span>采集参数</span>
          </div>
          <div class="config-rows">
            <div class="config-row">
              <span>行情采集间隔</span>
              <code>{{ config.market_collect_interval }} 分钟</code>
            </div>
            <div class="config-row">
              <span>估值采集间隔</span>
              <code>{{ config.fund_estimate_interval }} 分钟</code>
            </div>
            <div class="config-row">
              <span>尾盘 AI 时间</span>
              <code>{{ config.ai_advice_time }}</code>
            </div>
            <div class="config-row">
              <span>建议前刷新</span>
              <span class="key-badge" :class="{ active: config.ai_advice_pre_refresh }">
                {{ config.ai_advice_pre_refresh ? '已启用' : '未启用' }}
              </span>
            </div>
            <div class="config-row">
              <span>新闻回看</span>
              <code>{{ config.ai_news_lookback_days }} 天</code>
            </div>
          </div>
        </div>

        <!-- Network -->
        <div class="config-card">
          <div class="config-card-head">
            <el-icon><Monitor /></el-icon>
            <span>服务端口</span>
          </div>
          <div class="config-rows">
            <div class="config-row">
              <span>监听地址</span>
              <code>{{ config.backend_host }}</code>
            </div>
            <div class="config-row">
              <span>后端端口</span>
              <code>{{ config.backend_port }}</code>
            </div>
          </div>
        </div>

        <!-- Password -->
        <div class="config-card">
          <div class="config-card-head">
            <el-icon><Lock /></el-icon>
            <span>账号安全</span>
          </div>
          <div class="config-rows">
            <el-form :model="passwordForm" label-position="top" size="small">
              <el-form-item label="原密码">
                <el-input v-model="passwordForm.old_password" type="password" show-password />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="passwordForm.new_password" type="password" show-password />
              </el-form-item>
              <el-button type="primary" size="small" :loading="passwordLoading" @click="handleChangePassword">
                更新登录密码
              </el-button>
            </el-form>
          </div>
        </div>
      </div>

      <!-- Scheduler -->
      <div class="section-bar" style="margin-top: 28px;">
        <div>
          <h3>定时任务</h3>
          <p>共 {{ scheduler.jobs?.length || 0 }} 个任务</p>
        </div>
        <el-button size="small" @click="loadSchedulerStatus">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>

      <el-table v-if="scheduler.jobs?.length" :data="scheduler.jobs" stripe>
        <el-table-column prop="name" label="任务" min-width="160" />
        <el-table-column label="下次执行" width="200">
          <template #default="{ row }">{{ formatNextRun(row.next_run) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button size="small" @click="handleTrigger(row.id)">立即执行</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="调度器未运行" :image-size="48" />
    </div>

    <!-- ═══ P1.3 用户画像 ═══ -->
    <div v-show="activeTab === 'profile'" class="tab-content">
      <div class="section-bar">
        <div>
          <h3>用户画像</h3>
          <p>填写后，AI 顾问会结合你的年龄/资金性质/风险偏好生成更贴合的建议</p>
        </div>
        <el-button size="small" :icon="Refresh" @click="loadProfile">重新加载</el-button>
      </div>

      <el-card class="profile-card">
        <el-form :model="profile" label-width="140px" style="max-width: 720px;">
          <el-form-item label="出生年份">
            <el-input-number v-model="profile.birth_year" :min="1940" :max="2010" placeholder="如 1985" />
          </el-form-item>
          <el-form-item label="计划退休年">
            <el-input-number v-model="profile.retirement_target_year" :min="2030" :max="2080" />
          </el-form-item>
          <el-form-item label="资金锁定期">
            <el-input-number v-model="profile.investment_horizon_years" :min="0" :max="40" />
            <span style="margin-left:8px;color:var(--gray-500);">年</span>
          </el-form-item>
          <el-form-item label="资金性质">
            <el-radio-group v-model="profile.funds_purpose">
              <el-radio-button value="emergency">紧急资金</el-radio-button>
              <el-radio-button value="house_down">首付资金</el-radio-button>
              <el-radio-button value="children_edu">教育金</el-radio-button>
              <el-radio-button value="retirement">养老金</el-radio-button>
              <el-radio-button value="long_term">长期闲钱</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="目标年化 %">
            <el-input-number v-model="profile.target_annual_return" :min="0" :max="50" :precision="1" :step="0.5" />
          </el-form-item>
          <el-form-item label="可承受最大回撤 %">
            <el-input-number v-model="profile.max_acceptable_drawdown" :min="0" :max="80" :precision="1" :step="1" />
          </el-form-item>
          <el-form-item label="风险偏好">
            <el-radio-group v-model="profile.risk_appetite">
              <el-radio-button value="conservative">保守</el-radio-button>
              <el-radio-button value="balanced">稳健</el-radio-button>
              <el-radio-button value="aggressive">积极</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="月可投入资金">
            <el-input-number v-model="profile.monthly_disposable_income" :min="0" :max="1000000" :step="1000" :precision="0" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="profile.profile_notes" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="profileSaving" @click="saveProfile">保存画像</el-button>
            <el-button :loading="recommendLoading" @click="getRecommendation">生成推荐配置</el-button>
          </el-form-item>
        </el-form>

        <el-alert v-if="recommendResult" type="info" :closable="true" show-icon style="margin-top: 14px;"
                  @close="recommendResult = null">
          <template #title>
            推荐资产配置（年龄 {{ recommendResult.age || '?' }} · {{ recommendResult.risk_appetite }}）
          </template>
          <template #default>
            <p style="margin:4px 0 8px;">{{ recommendResult.reasoning }}</p>
            <el-table :data="recommendResult.recommendation" size="small" stripe>
              <el-table-column label="资产类" prop="notes" width="160" />
              <el-table-column label="占比" prop="target_pct" width="100">
                <template #default="{ row }">{{ row.target_pct }}%</template>
              </el-table-column>
              <el-table-column label="容差" prop="tolerance_pct" width="100">
                <template #default="{ row }">±{{ row.tolerance_pct }}%</template>
              </el-table-column>
            </el-table>
            <p style="margin-top:8px;font-size:12px;color:var(--gray-500);">
              这是参考起点。要应用到系统目标配置，请到"风险暴露 → 目标资产配置"页编辑保存。
            </p>
          </template>
        </el-alert>
      </el-card>
    </div>

    <!-- ═══ 关于 ═══ -->
    <div v-show="activeTab === 'about'" class="tab-content">
      <div class="about-card">
        <div class="about-brand">
          <div class="about-logo">
            <img :src="brandIcon" alt="" />
          </div>
          <div>
            <h2>基金智能分析系统</h2>
            <p>本地部署的私人基金量化分析工作台</p>
          </div>
        </div>

        <div class="about-meta-grid">
          <div class="about-meta">
            <span>版本</span>
            <strong>v1.0.0</strong>
          </div>
          <div class="about-meta">
            <span>构建方式</span>
            <strong>PyInstaller 桌面应用</strong>
          </div>
          <div class="about-meta">
            <span>运行环境</span>
            <strong>Python 3.11 · Windows 11</strong>
          </div>
          <div class="about-meta">
            <span>数据存储</span>
            <strong>SQLite (WAL 模式)</strong>
          </div>
        </div>

        <div class="about-stack">
          <h4>技术栈</h4>
          <div class="stack-tags">
            <span>FastAPI</span>
            <span>Vue 3</span>
            <span>TypeScript</span>
            <span>Element Plus</span>
            <span>ECharts</span>
            <span>SQLAlchemy</span>
            <span>APScheduler</span>
            <span>AKShare</span>
            <span>DeepSeek AI</span>
            <span>PyInstaller</span>
          </div>
        </div>

        <div class="about-stack">
          <h4>数据来源</h4>
          <div class="stack-tags secondary">
            <span>东方财富</span>
            <span>财联社</span>
            <span>新浪财经</span>
            <span>天天基金</span>
            <span>上交所</span>
          </div>
        </div>

        <p class="about-disclaimer">
          本系统仅供个人学习与研究使用，所有数据来自公开 API，不构成投资建议。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Connection, Timer, Monitor, Lock,
  SetUp, DataAnalysis, InfoFilled, User,
} from '@element-plus/icons-vue'
import {
  changePassword, getSettings, getSchedulerStatus,
  getDiagnostics, triggerJob,
  getUserProfile, saveUserProfile, recommendAllocation,
} from '../api'

const brandIcon = '/brand-assets/fund-ai-64.png'
const activeTab = ref('diagnostics')
const tabs = [
  { key: 'diagnostics', label: '系统体检', icon: DataAnalysis },
  { key: 'profile',    label: '用户画像', icon: User },
  { key: 'config',     label: '系统配置', icon: SetUp },
  { key: 'about',      label: '关于',     icon: InfoFilled },
]

const config = ref<any>({})
const scheduler = ref<any>({ status: 'not_running', jobs: [] })
const diagnostics = ref<any>({ checks: [], summary: {}, data_freshness: { snapshots: {} } })
const diagnosticsLoading = ref(false)
const passwordLoading = ref(false)
const passwordForm = ref({ old_password: '', new_password: '' })

// P1.3 用户画像
const profile = ref<any>({})
const profileSaving = ref(false)
const recommendLoading = ref(false)
const recommendResult = ref<any>(null)

async function loadProfile() {
  try { profile.value = await getUserProfile() as any }
  catch { profile.value = {} }
}

async function saveProfile() {
  profileSaving.value = true
  try {
    await saveUserProfile(profile.value)
    ElMessage.success('用户画像已保存，AI 顾问下次生成会用新画像')
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    profileSaving.value = false
  }
}

async function getRecommendation() {
  recommendLoading.value = true
  try {
    recommendResult.value = await recommendAllocation()
  } catch (e: any) {
    ElMessage.error('生成失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    recommendLoading.value = false
  }
}

const snapshotLabels: Record<string, string> = {
  index: 'A股指数', sector: '行业板块', concept: '概念板块',
  global: '全球市场', fund: '基金估值',
}

const snapshotItems = computed(() => {
  const snapshots = diagnostics.value?.data_freshness?.snapshots || {}
  return Object.entries(snapshotLabels).map(([key, label]) => ({
    key, label, ...(snapshots[key] || {}),
  }))
})

const overallClass = computed(() => {
  const s = diagnostics.value?.status
  if (s === 'healthy') return 'ok'
  if (s === 'warning') return 'warn'
  if (s === 'critical') return 'critical'
  return 'info'
})

function tagType(s: string) {
  if (s === 'healthy' || s === 'ok') return 'success'
  if (s === 'warning') return 'warning'
  if (s === 'critical') return 'danger'
  return 'info'
}

function statusText(s: string) {
  const map: Record<string, string> = {
    healthy: '健康', ok: '正常', warning: '警告', critical: '严重',
  }
  return map[s] || '未知'
}

function formatNextRun(t: string) {
  if (!t || t === 'N/A') return 'N/A'
  try { return new Date(t).toLocaleString('zh-CN') }
  catch { return t }
}

async function loadSchedulerStatus() {
  try { scheduler.value = (await getSchedulerStatus()) as any }
  catch (e: any) { ElMessage.error('定时任务状态加载失败: ' + (e?.response?.data?.detail || e?.message || '')) }
}

async function loadDiagnostics() {
  diagnosticsLoading.value = true
  try { diagnostics.value = (await getDiagnostics()) as any }
  catch (e: any) { ElMessage.error('体检失败: ' + (e.response?.data?.detail || e.message)) }
  finally { diagnosticsLoading.value = false }
}

async function handleTrigger(jobId: string) {
  try {
    const res = (await triggerJob(jobId)) as any
    if (res.error) ElMessage.error(res.error)
    else ElMessage.success(res.message || '已触发')
  } catch (e: any) {
    ElMessage.error('触发失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function handleChangePassword() {
  if (!passwordForm.value.old_password || !passwordForm.value.new_password) {
    ElMessage.warning('请输入原密码和新密码')
    return
  }
  passwordLoading.value = true
  try {
    await changePassword(passwordForm.value)
    ElMessage.success('密码已更新，请重新登录')
    localStorage.removeItem('fund_ai_token')
    localStorage.removeItem('fund_ai_user')
    window.location.href = '/login'
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '更新失败')
  } finally { passwordLoading.value = false }
}

onMounted(async () => {
  try { config.value = await getSettings() as any }
  catch (e: any) { ElMessage.error('系统配置加载失败: ' + (e?.response?.data?.detail || e?.message || '')) }
  loadSchedulerStatus()
  loadDiagnostics()
  loadProfile()
})
</script>

<style scoped>
.settings-page {
  max-width: var(--content-max-width);
}

/* ── Tab bar ─────────────────────────── */
.settings-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--gray-300);
  margin-bottom: 28px;
}
.settings-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 10px 20px;
  border: none;
  background: none;
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--gray-600);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all var(--transition-fast);
}
.settings-tabs button:hover { color: var(--gray-900); }
.settings-tabs button.active {
  color: var(--brand-500);
  border-bottom-color: var(--brand-500);
}

.tab-content { animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

/* ── Section bar ──────────────────────── */
.section-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.section-bar h3 { font-size: var(--text-lg); font-weight: var(--weight-medium); color: var(--gray-900); margin: 0 0 2px; }
.section-bar p { font-size: var(--text-xs); color: var(--gray-600); margin: 0; }

.label-row {
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--gray-600);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 10px;
}

/* ── Status banner ────────────────────── */
.status-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}
.status-banner.ok       { background: #e6f4ea; }
.status-banner.warn     { background: #fef7e0; }
.status-banner.critical { background: #fce8e6; }
.status-banner.info     { background: var(--gray-100); }
.status-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-banner.ok .status-dot       { background: var(--success-500); }
.status-banner.warn .status-dot     { background: var(--warning-500); }
.status-banner.critical .status-dot { background: var(--danger-500); }
.status-banner.info .status-dot     { background: var(--gray-400); }
.status-label { font-weight: var(--weight-semibold); font-size: var(--text-sm); color: var(--gray-900); }
.status-meta { font-size: var(--text-xs); color: var(--gray-600); }

/* ── Freshness row ────────────────────── */
.freshness-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}
.freshness-cell {
  background: var(--gray-100);
  border: none;
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.freshness-cell:hover { background: var(--brand-50); }
.f-label { font-size: 11px; color: var(--gray-600); font-weight: var(--weight-medium); display: block; }
.f-date { font-size: var(--text-xl); font-weight: var(--weight-medium); color: var(--gray-900); display: block; margin: 6px 0 4px; }
.f-meta { font-size: 11px; color: var(--gray-500); }

/* check dot */
.check-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.check-dot.ok       { background: var(--success-500); }
.check-dot.warning  { background: var(--warning-500); }
.check-dot.critical { background: var(--danger-500); }

/* ── Config grid ──────────────────────── */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.config-card {
  background: #fff;
  border: none;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 20px 24px;
}
.config-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--gray-900);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--gray-300);
}
.config-card-head .el-icon { color: var(--brand-500); }
.config-rows { display: flex; flex-direction: column; gap: 10px; }
.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--text-sm);
}
.config-row > span:first-child { color: var(--gray-600); }
.config-row code {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--gray-900);
  background: var(--gray-100);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
}
.config-note {
  margin: 14px 0 0;
  font-size: 11px;
  color: var(--gray-500);
  line-height: 1.5;
}
.key-badge {
  font-size: 11px;
  font-weight: var(--weight-medium);
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--gray-200);
  color: var(--gray-600);
}
.key-badge.active { background: var(--success-50); color: var(--success-600); }

/* ── About ────────────────────────────── */
.about-card {
  max-width: 680px;
  background: #fff;
  border: none;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  padding: 40px;
}

.about-brand {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 36px;
}
.about-logo {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  background: var(--brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.about-logo img { width: 36px; height: 36px; filter: brightness(10); }
.about-brand h2 { font-size: var(--text-2xl); font-weight: var(--weight-medium); color: var(--gray-900); margin: 0 0 4px; }
.about-brand p  { font-size: var(--text-sm); color: var(--gray-600); margin: 0; }

.about-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 32px;
}
.about-meta {
  background: var(--gray-100);
  border-radius: var(--radius-md);
  padding: 14px 18px;
}
.about-meta span { font-size: 11px; color: var(--gray-600); display: block; }
.about-meta strong { display: block; margin-top: 4px; font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--gray-900); }

.about-stack { margin-bottom: 20px; }
.about-stack h4 { font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--gray-900); margin: 0 0 10px; }
.stack-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.stack-tags span {
  font-size: 12px;
  padding: 4px 14px;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-weight: var(--weight-medium);
}
.stack-tags.secondary span {
  background: var(--gray-100);
  color: var(--gray-600);
}

.about-disclaimer {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--gray-300);
  font-size: var(--text-xs);
  color: var(--gray-500);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .config-grid { grid-template-columns: 1fr; }
  .freshness-row { grid-template-columns: repeat(3, 1fr); }
  .about-meta-grid { grid-template-columns: 1fr; }
}
</style>
