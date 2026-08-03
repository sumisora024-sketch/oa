<script setup>
import { reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { KeyRound, LogIn, Mail } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import nitMark from '../assets/nit-mark.svg'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ email: '', password: '' })

if (locale.value === 'zh') {
  locale.value = 'ja'
  localStorage.setItem('oa_locale', 'ja')
}

async function submit() {
  if (!form.email || !form.password) {
    ElMessage.error(t('validation.required'))
    return
  }
  loading.value = true
  try {
    await auth.login(form)
    router.push(auth.user?.must_reset_password ? '/reset-password-required' : '/home')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('common.failed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-grid-line login-grid-line-a" aria-hidden="true"></div>
    <div class="login-grid-line login-grid-line-b" aria-hidden="true"></div>
    <div class="login-ghost-mark" aria-hidden="true">NIT</div>
    <main class="login-shell">
      <section class="login-brand-panel">
        <div class="login-logo-stack">
          <img :src="nitMark" alt="NIHON INFO TECH" class="login-company-logo" draggable="false" />
          <p class="login-system-tagline">NIT OA System</p>
        </div>
      </section>
      <section class="login-panel">
        <div class="login-panel-header">
          <h2>{{ t('login.title') }}</h2>
        </div>
        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item :label="t('login.email')">
            <el-input v-model="form.email" :prefix-icon="Mail" autocomplete="username" />
          </el-form-item>
          <el-form-item :label="t('login.password')">
            <el-input v-model="form.password" :prefix-icon="KeyRound" type="password" autocomplete="current-password" show-password />
          </el-form-item>
          <el-button type="primary" :icon="LogIn" :loading="loading" class="full-button" @click="submit">
            {{ t('login.submit') }}
          </el-button>
        </el-form>
      </section>
    </main>
  </div>
</template>
