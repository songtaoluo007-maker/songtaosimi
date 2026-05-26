<template>
  <div class="login-page">
    <section class="login-panel">
      <!-- Brand -->
      <div class="login-brand">
        <div class="login-logo">
          <img :src="brandIcon" alt="" />
        </div>
        <div>
          <h1>基金智能分析</h1>
          <p>本地私人基金量化系统</p>
        </div>
      </div>

      <el-alert
        v-if="setupMode"
        title="首次使用需创建本机所有者账号，数据仅保存在本地。"
        type="info"
        show-icon
        :closable="false"
        class="login-alert"
      />

      <el-form :model="form" label-position="top" @keyup.enter="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" size="large" autocomplete="username" placeholder="owner" />
        </el-form-item>
        <el-form-item v-if="setupMode" label="显示名称">
          <el-input v-model="form.display_name" size="large" placeholder="基金账户所有者" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="至少 8 位，建议包含数字和字母"
          />
        </el-form-item>

        <div class="login-extra" v-if="!setupMode">
          <el-checkbox v-model="rememberMe">记住我（30 天自动登录）</el-checkbox>
          <a class="recover-link" @click="showRecover = true">忘记密码？</a>
        </div>

        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="submit">
          {{ setupMode ? '创建账号并进入系统' : '登录系统' }}
        </el-button>
      </el-form>

      <div v-if="recoveryKeyShown" class="recovery-key-box">
        <strong>请立即保存恢复密钥（仅显示一次）：</strong>
        <code>{{ recoveryKeyShown }}</code>
        <p>忘记密码时凭此密钥可在登录页重置，建议截图或复制保存。</p>
      </div>

      <div class="login-footer">
        <span>Local Account</span>
        <strong>127.0.0.1</strong>
      </div>

      <!-- Recover Dialog -->
      <el-dialog v-model="showRecover" title="重置密码" width="420px" :close-on-click-modal="false">
        <el-form label-position="top">
          <el-form-item label="恢复密钥">
            <el-input v-model="recoverForm.recoveryKey" placeholder="首次设置时生成的 16 位密钥" />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="recoverForm.newPassword" type="password" show-password placeholder="至少 8 位，含数字和字母" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showRecover = false">取消</el-button>
          <el-button type="primary" :loading="recoverLoading" @click="handleRecover">重置密码</el-button>
        </template>
      </el-dialog>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getBootstrapStatus, login, setupOwner, recoverPassword } from '../api'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const setupMode = ref(false)
const rememberMe = ref(true)
const showRecover = ref(false)
const recoverForm = reactive({ recoveryKey: '', newPassword: '' })
const recoverLoading = ref(false)
const recoveryKeyShown = ref('')
const brandIcon = '/brand-assets/fund-ai-128.png'
const form = reactive({
  username: localStorage.getItem('fund_ai_last_user') || 'owner',
  display_name: '基金账户所有者',
  password: '',
})

onMounted(async () => {
  try {
    const status = await getBootstrapStatus() as any
    setupMode.value = !status.has_user
  } catch {
    setupMode.value = false
  }
})

function saveSession(res: any) {
  localStorage.setItem('fund_ai_token', res.access_token)
  localStorage.setItem('fund_ai_user', JSON.stringify(res.user || {}))
  if (res.refresh_token) localStorage.setItem('fund_ai_refresh_token', res.refresh_token)
  localStorage.setItem('fund_ai_last_user', form.username.trim())
  if (rememberMe.value) localStorage.setItem('fund_ai_remember', '1')
}

if (localStorage.getItem('fund_ai_remember') === '1') {
  rememberMe.value = true
}

async function submit() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    if (setupMode.value) {
      const res = await setupOwner({
        username: form.username.trim(),
        display_name: form.display_name.trim(),
        password: form.password,
      }) as any
      saveSession(res)
      recoveryKeyShown.value = res.recovery_key || ''
      ElMessage.success('账号已创建！请妥善保存恢复密钥')
    } else {
      const res = await login({
        username: form.username.trim(),
        password: form.password,
        remember_me: rememberMe.value,
      }) as any
      saveSession(res)
      ElMessage.success('登录成功')
      router.replace((route.query.redirect as string) || '/')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRecover() {
  if (!recoverForm.recoveryKey.trim() || !recoverForm.newPassword) {
    ElMessage.warning('请输入恢复密钥和新密码')
    return
  }
  if (recoverForm.newPassword.length < 8) {
    ElMessage.warning('新密码至少需要 8 位')
    return
  }
  recoverLoading.value = true
  try {
    await recoverPassword({
      recovery_key: recoverForm.recoveryKey.trim(),
      new_password: recoverForm.newPassword,
    })
    ElMessage.success('密码已重置，请使用新密码登录')
    showRecover.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重置失败')
  } finally {
    recoverLoading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
  padding: 24px;
  position: relative;
}

.login-page::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 30% 20%, rgba(99, 102, 241, 0.15), transparent 50%),
              radial-gradient(ellipse at 70% 80%, rgba(59, 130, 246, 0.10), transparent 50%);
  pointer-events: none;
}

.login-panel {
  position: relative;
  width: min(440px, 100%);
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 36px 32px;
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.35);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}

.login-logo {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #6366F1, #4338CA);
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-logo img {
  width: 32px;
  height: 32px;
  object-fit: contain;
}

.login-brand h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0F172A;
  letter-spacing: -0.01em;
}

.login-brand p {
  margin: 2px 0 0;
  font-size: 13px;
  color: #64748B;
}

.login-alert {
  margin-bottom: 20px;
}

.login-btn {
  width: 100%;
  margin-top: 4px;
}

.login-extra {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.recover-link {
  color: #6366F1;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.recover-link:hover {
  color: #4F46E5;
  text-decoration: underline;
}

.recovery-key-box {
  margin-top: 20px;
  padding: 16px;
  background: #FFFBEB;
  border: 1px solid #FCD34D;
  border-radius: 10px;
  font-size: 13px;
}

.recovery-key-box strong {
  color: #92400E;
}

.recovery-key-box code {
  display: block;
  margin: 10px 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
  background: #FFF;
  padding: 8px 12px;
  border-radius: 6px;
  word-break: break-all;
  border: 1px solid #E2E8F0;
}

.recovery-key-box p {
  margin: 0;
  color: #78716C;
  font-size: 12px;
}

.login-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #F1F5F9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #94A3B8;
}

.login-footer strong {
  color: #334155;
  font-family: var(--font-mono);
}
</style>
