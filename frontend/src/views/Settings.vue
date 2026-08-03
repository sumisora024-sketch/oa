<script setup>
import { onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { MailCheck, Save, Send } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const { t } = useI18n()

const form = reactive(defaultForm())

const providerOptions = [
  { labelKey: 'settings.disabled', value: 'disabled' },
  { labelKey: 'settings.gmail', value: 'gmail_app_password' },
  { labelKey: 'settings.generic', value: 'generic_imap_smtp' },
  { labelKey: 'settings.smtpOnly', value: 'smtp_only' }
]

function defaultForm() {
  return {
    provider: 'disabled',
    enabled: false,
    imap_enabled: false,
    imap_host: '',
    imap_port: 993,
    imap_username: '',
    imap_password: '',
    has_imap_password: false,
    imap_folder: 'INBOX',
    poll_interval_seconds: 60,
    smtp_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    has_smtp_password: false,
    smtp_from: '',
    smtp_use_tls: true
  }
}

function applyProvider(value) {
  form.provider = value
  if (value === 'disabled') {
    form.enabled = false
    form.imap_enabled = false
    form.smtp_enabled = false
    return
  }
  form.enabled = true
  if (value === 'gmail_app_password') {
    form.imap_enabled = true
    form.smtp_enabled = true
    form.imap_host = 'imap.gmail.com'
    form.imap_port = 993
    form.smtp_host = 'smtp.gmail.com'
    form.smtp_port = 587
    form.smtp_use_tls = true
    form.imap_folder = form.imap_folder || 'INBOX'
    return
  }
  if (value === 'smtp_only') {
    form.imap_enabled = false
    form.smtp_enabled = true
    if (form.smtp_host === 'smtp.gmail.com') form.smtp_host = ''
    form.smtp_port = form.smtp_port || 587
    return
  }
  form.imap_enabled = true
  form.smtp_enabled = true
  if (form.imap_host === 'imap.gmail.com') form.imap_host = ''
  if (form.smtp_host === 'smtp.gmail.com') form.smtp_host = ''
  form.imap_port = form.imap_port || 993
  form.smtp_port = form.smtp_port || 587
}

function payload() {
  const data = {
    provider: form.provider,
    enabled: form.enabled,
    imap_enabled: form.imap_enabled,
    imap_host: form.imap_host || null,
    imap_port: form.imap_port,
    imap_username: form.imap_username || null,
    imap_folder: form.imap_folder || 'INBOX',
    poll_interval_seconds: form.poll_interval_seconds,
    smtp_enabled: form.smtp_enabled,
    smtp_host: form.smtp_host || null,
    smtp_port: form.smtp_port,
    smtp_username: form.smtp_username || null,
    smtp_from: form.smtp_from || null,
    smtp_use_tls: form.smtp_use_tls
  }
  if (form.imap_password) data.imap_password = form.imap_password
  if (form.smtp_password) data.smtp_password = form.smtp_password
  return data
}

async function load() {
  const { data } = await api.get('/mail-settings')
  Object.assign(form, data, { imap_password: '', smtp_password: '' })
}

async function save() {
  const { data } = await api.put('/mail-settings', payload())
  Object.assign(form, data, { imap_password: '', smtp_password: '' })
  ElMessage.success(t('common.success'))
}

async function test(kind) {
  const endpoint = kind === 'imap' ? '/mail-settings/test-imap' : '/mail-settings/test-smtp'
  const { data } = await api.post(endpoint)
  if (data.ok) {
    ElMessage.success(data.message)
  } else {
    ElMessage.error(data.message)
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ t('settings.mail') }}</h2>
      <div class="toolbar">
        <el-button :icon="MailCheck" @click="test('imap')">{{ t('settings.testImap') }}</el-button>
        <el-button :icon="Send" @click="test('smtp')">{{ t('settings.testSmtp') }}</el-button>
        <el-button type="primary" :icon="Save" @click="save">{{ t('common.save') }}</el-button>
      </div>
    </div>

    <section class="settings-panel">
      <el-form label-position="top" class="form-grid">
        <el-form-item :label="t('settings.provider')">
          <el-select v-model="form.provider" @change="applyProvider">
            <el-option v-for="option in providerOptions" :key="option.value" :label="t(option.labelKey)" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('settings.enabled')">
          <el-switch v-model="form.enabled" />
        </el-form-item>

        <el-form-item :label="t('settings.imapEnabled')">
          <el-switch v-model="form.imap_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.smtpEnabled')">
          <el-switch v-model="form.smtp_enabled" />
        </el-form-item>

        <el-form-item :label="t('settings.imapHost')">
          <el-input v-model="form.imap_host" :disabled="!form.imap_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.imapPort')">
          <el-input-number v-model="form.imap_port" :min="1" :max="65535" :disabled="!form.imap_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.imapUsername')">
          <el-input v-model="form.imap_username" :disabled="!form.imap_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.imapPassword')">
          <el-input v-model="form.imap_password" type="password" show-password :placeholder="form.has_imap_password ? t('settings.hasPassword') : ''" :disabled="!form.imap_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.imapFolder')">
          <el-input v-model="form.imap_folder" :disabled="!form.imap_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.pollInterval')">
          <el-input-number v-model="form.poll_interval_seconds" :min="15" :step="15" :disabled="!form.imap_enabled" />
        </el-form-item>

        <el-form-item :label="t('settings.smtpHost')">
          <el-input v-model="form.smtp_host" :disabled="!form.smtp_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.smtpPort')">
          <el-input-number v-model="form.smtp_port" :min="1" :max="65535" :disabled="!form.smtp_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.smtpUsername')">
          <el-input v-model="form.smtp_username" :disabled="!form.smtp_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.smtpPassword')">
          <el-input v-model="form.smtp_password" type="password" show-password :placeholder="form.has_smtp_password ? t('settings.hasPassword') : ''" :disabled="!form.smtp_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.smtpFrom')">
          <el-input v-model="form.smtp_from" :disabled="!form.smtp_enabled" />
        </el-form-item>
        <el-form-item :label="t('settings.smtpTls')">
          <el-switch v-model="form.smtp_use_tls" :disabled="!form.smtp_enabled" />
        </el-form-item>
      </el-form>
    </section>
  </div>
</template>
