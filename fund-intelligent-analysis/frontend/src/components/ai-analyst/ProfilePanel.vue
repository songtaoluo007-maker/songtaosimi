<template>
  <div>
    <el-row :gutter="20">
      <!-- 用户手填画像 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: bold;">用户画像（手动填写）</span>
              <el-button size="small" type="primary" @click="saveProfile" :loading="saving">保存</el-button>
            </div>
          </template>
          <el-form label-width="120px" size="default">
            <el-form-item label="风险承受能力">
              <el-slider v-model="profile.risk_tolerance" :min="1" :max="10" show-stops :marks="riskMarks" />
            </el-form-item>
            <el-form-item label="预期收益目标">
              <el-select v-model="profile.return_target" style="width: 100%;">
                <el-option label="保守（3-5%）" value="conservative" />
                <el-option label="稳健（5-10%）" value="moderate" />
                <el-option label="积极（10-20%）" value="aggressive" />
                <el-option label="激进（20%+）" value="very_aggressive" />
              </el-select>
            </el-form-item>
            <el-form-item label="投资期限">
              <el-select v-model="profile.holding_period" style="width: 100%;">
                <el-option label="短期（< 3个月）" value="short" />
                <el-option label="中期（3-12个月）" value="medium" />
                <el-option label="长期（1年+）" value="long" />
              </el-select>
            </el-form-item>
            <el-form-item label="最大回撤容忍">
              <el-slider v-model="profile.max_drawdown_tolerance" :min="5" :max="50" :step="5" show-stops />
              <span style="color: #909399; font-size: 12px;">{{ profile.max_drawdown_tolerance }}%</span>
            </el-form-item>
            <el-form-item label="交易频率偏好">
              <el-select v-model="profile.trade_frequency" style="width: 100%;">
                <el-option label="低频（月度调仓）" value="low" />
                <el-option label="中频（周度调仓）" value="medium" />
                <el-option label="高频（日内关注）" value="high" />
              </el-select>
            </el-form-item>
            <el-form-item label="偏好行业">
              <el-input v-model="profile.preferred_sectors" placeholder="如：科技、消费、医疗" />
            </el-form-item>
            <el-form-item label="回避行业">
              <el-input v-model="profile.avoided_sectors" placeholder="如：地产、白酒" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- AI 推断画像 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: bold;">AI 推断画像</span>
              <el-button size="small" :loading="recalculating" @click="recalculate">重新计算</el-button>
            </div>
          </template>

          <div v-if="aiProfile">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="风险容忍度">
                <el-progress :percentage="aiProfile.risk_tolerance_score * 10" :stroke-width="12" style="width: 200px;" />
              </el-descriptions-item>
              <el-descriptions-item label="回撤敏感度">
                <el-progress :percentage="aiProfile.drawdown_sensitivity * 10" :stroke-width="12" :color="'#e6a23c'" style="width: 200px;" />
              </el-descriptions-item>
              <el-descriptions-item label="恐慌卖出倾向">
                <el-progress :percentage="aiProfile.panic_sell_risk_score * 10" :stroke-width="12" :color="'#f56c6c'" style="width: 200px;" />
              </el-descriptions-item>
              <el-descriptions-item label="追高倾向">
                <el-progress :percentage="aiProfile.chasing_risk_score * 10" :stroke-width="12" :color="'#f56c6c'" style="width: 200px;" />
              </el-descriptions-item>
              <el-descriptions-item label="交易频率偏好">{{ aiProfile.trade_frequency_preference }}</el-descriptions-item>
              <el-descriptions-item label="持仓周期">{{ aiProfile.preferred_holding_period }}</el-descriptions-item>
              <el-descriptions-item label="投资风格">{{ aiProfile.style_preference }}</el-descriptions-item>
              <el-descriptions-item label="亏损反应">{{ aiProfile.loss_reaction_pattern }}</el-descriptions-item>
              <el-descriptions-item label="置信度调整">
                <el-tag :type="aiProfile.confidence_adjustment > 0 ? 'success' : (aiProfile.confidence_adjustment < 0 ? 'danger' : 'info')">
                  {{ aiProfile.confidence_adjustment > 0 ? '+' : '' }}{{ (aiProfile.confidence_adjustment * 100).toFixed(0) }}%
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="总建议数">{{ aiProfile.total_advices }}</el-descriptions-item>
              <el-descriptions-item label="采纳/拒绝">{{ aiProfile.accepted_count }} / {{ aiProfile.rejected_count }}</el-descriptions-item>
            </el-descriptions>

            <div v-if="aiProfile.evidence_summary" style="margin-top: 16px; padding: 12px; background: #f4f4f5; border-radius: 8px;">
              <div style="font-weight: bold; margin-bottom: 4px;">更新依据：</div>
              <div style="font-size: 13px; color: #606266;">{{ aiProfile.evidence_summary }}</div>
            </div>

            <div v-if="aiProfile.evidence_tags?.length" style="margin-top: 12px;">
              <el-tag v-for="tag in aiProfile.evidence_tags" :key="tag" style="margin-right: 4px;">{{ tag }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无 AI 推断画像，点击上方按钮生成" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPersonalAnalystProfile, recalculatePersonalAnalystProfile } from '../../api'

const saving = ref(false)
const recalculating = ref(false)
const aiProfile = ref<any>(null)

const profile = reactive({
  risk_tolerance: 5,
  return_target: 'moderate',
  holding_period: 'medium',
  max_drawdown_tolerance: 20,
  trade_frequency: 'low',
  preferred_sectors: '',
  avoided_sectors: '',
})

const riskMarks: Record<number, string> = {
  1: '保守',
  5: '适中',
  10: '激进',
}

async function saveProfile() {
  saving.value = true
  try {
    // TODO: 接入后端 API 保存用户手填画像
    await new Promise(r => setTimeout(r, 500))
    ElMessage.success('画像已保存')
  } catch (e: any) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function loadProfile() {
  try {
    const res = (await getPersonalAnalystProfile()) as any
    aiProfile.value = res.profile || null
  } catch (e) {
    console.error(e)
  }
}

async function recalculate() {
  recalculating.value = true
  try {
    const res = (await recalculatePersonalAnalystProfile()) as any
    aiProfile.value = res.profile || null
    ElMessage.success('画像已更新')
  } catch (e: any) {
    ElMessage.error('计算失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    recalculating.value = false
  }
}

onMounted(loadProfile)
</script>
