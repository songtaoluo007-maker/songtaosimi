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
          <template #header><span style="font-weight: bold;">AI 推断画像</span></template>
          <el-alert
            title="AI 根据你的交易历史、反馈和建议采纳情况自动生成。后端 P3.3 完成后接入。"
            type="info"
            show-icon
            :closable="false"
            style="margin-bottom: 16px;"
          />
          <el-empty description="暂无数据，等待后端画像服务接入" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const saving = ref(false)

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
    // TODO: 接入后端 API
    await new Promise(r => setTimeout(r, 500))
    ElMessage.success('画像已保存')
  } catch (e: any) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>
