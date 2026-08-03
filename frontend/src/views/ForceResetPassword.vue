<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { KeyRound, Save } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ current_password: '', new_password: '', confirm_password: '' })
const isForced = computed(() => route.name === 'resetPasswordRequired')

async function submit() {
  if (!form.current_password || !form.new_password || !form.confirm_password) {
    ElMessage.error(t('validation.required'))
    return
  }
  if (form.new_password !== form.confirm_password) {
    ElMessage.error(t('validation.passwordMismatch'))
    return
  }
  loading.value = true
  try {
    await auth.changePassword({
      current_password: form.current_password,
      new_password: form.new_password
    })
    ElMessage.success(t('common.success'))
    router.push('/home')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('common.failed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div :class="isForced ? 'login-page' : 'password-page'">
    <section class="reset-panel">
      <h2>{{ isForced ? t('login.forceResetTitle') : t('login.changePasswordTitle') }}</h2>
      <p class="muted">{{ isForced ? t('login.forceResetHint') : t('login.changePasswordHint') }}</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item :label="t('login.currentPassword')">
          <el-input v-model="form.current_password" :prefix-icon="KeyRound" type="password" autocomplete="current-password" show-password />
        </el-form-item>
        <el-form-item :label="t('login.newPassword')">
          <el-input v-model="form.new_password" :prefix-icon="KeyRound" type="password" autocomplete="new-password" show-password />
        </el-form-item>
        <el-form-item :label="t('login.confirmPassword')">
          <el-input v-model="form.confirm_password" :prefix-icon="KeyRound" type="password" autocomplete="new-password" show-password />
        </el-form-item>
        <el-button type="primary" :icon="Save" :loading="loading" class="full-button" @click="submit">
          {{ t('common.save') }}
        </el-button>
      </el-form>
    </section>
  </div>
</template>
