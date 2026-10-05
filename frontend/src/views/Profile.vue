<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Save, UserRound } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'

import { api } from '../api/client'

const { t, locale } = useI18n()
const loading = ref(false)
const saving = ref(false)
const profile = ref(null)
const requests = ref([])
const changeOpen = ref(false)
const changeSaving = ref(false)
const formRef = ref(null)
const form = reactive({
  phone: '',
  nearest_station: '',
  languages: '',
  certifications: '',
  technical_experience: '',
  it_years: null,
  talent_category: '',
  skillsText: ''
})
const changeForm = reactive({ full_name: '', name_kana: '', birth_date: '', graduation_status: '', residence: '', email: '', nationality: '', reason: '' })
const profileCopy = computed(() => ({
  ja: { request: '正式情報の変更申請', requestHint: '氏名、住所、メールなどの正式情報は承認後に反映されます。', reason: '変更理由', submit: '申請する', history: '変更申請履歴', pending: '承認待ち', approved: '承認済み', rejected: '差戻し' },
  zh: { request: '正式信息变更申请', requestHint: '姓名、住址、邮箱等正式信息将在审批通过后生效。', reason: '变更理由', submit: '提交申请', history: '变更申请记录', pending: '审批中', approved: '已通过', rejected: '已驳回' },
  en: { request: 'Request formal profile change', requestHint: 'Formal fields such as name, address, and email are applied after approval.', reason: 'Reason', submit: 'Submit', history: 'Change request history', pending: 'Pending', approved: 'Approved', rejected: 'Rejected' }
}[locale.value] || {}))

const rules = {
  phone: [
    { required: true, message: t('validation.required'), trigger: 'blur' },
    { pattern: /^(?:0\d{1,4}-?\d{1,4}-?\d{3,4}|\+81-?\d{1,4}-?\d{1,4}-?\d{3,4})$/, message: t('validation.jpPhone'), trigger: 'blur' }
  ]
}

function applyProfile(data) {
  profile.value = data
  Object.assign(form, {
    phone: data.phone || '',
    nearest_station: data.nearest_station || '',
    languages: data.languages || '',
    certifications: data.certifications || '',
    technical_experience: data.technical_experience || '',
    it_years: data.it_years ?? null,
    talent_category: data.talent_category || '',
    skillsText: (data.skills || []).map((item) => `${item.name}:${item.level}`).join(', ')
  })
  Object.assign(changeForm, {
    full_name: data.full_name || '', name_kana: data.name_kana || '', birth_date: data.birth_date || '',
    graduation_status: data.graduation_status || '', residence: data.residence || '', email: data.email || '',
    nationality: data.nationality || '', reason: ''
  })
}

function parseSkills(value) {
  return String(value || '')
    .split(/[,、\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [name, level = '中'] = item.split(/[:：]/)
      return { name: name.trim(), level: level.trim() || '中' }
    })
}

function nullable(value) {
  return value === '' ? null : value
}

async function load() {
  loading.value = true
  try {
    applyProfile((await api.get('/employees/me')).data)
    requests.value = (await api.get('/employees/me/change-requests')).data
  } finally {
    loading.value = false
  }
}

async function submitChange() {
  const fields = ['full_name', 'name_kana', 'birth_date', 'graduation_status', 'residence', 'email', 'nationality']
  const payload = { reason: changeForm.reason || null }
  fields.forEach((key) => {
    const current = profile.value?.[key] ?? ''
    const next = changeForm[key] ?? ''
    if (String(current) !== String(next)) payload[key] = next || null
  })
  changeSaving.value = true
  try {
    await api.post('/employees/me/change-requests', payload)
    ElMessage.success(t('common.success'))
    changeOpen.value = false
    requests.value = (await api.get('/employees/me/change-requests')).data
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  } finally { changeSaving.value = false }
}

function statusLabel(value) { return profileCopy.value[value] || value }

async function save() {
  try {
    await formRef.value?.validate()
    saving.value = true
    const { data } = await api.patch('/employees/me', {
      phone: nullable(form.phone),
      nearest_station: nullable(form.nearest_station),
      languages: nullable(form.languages),
      certifications: nullable(form.certifications),
      technical_experience: nullable(form.technical_experience),
      it_years: form.it_years,
      talent_category: nullable(form.talent_category),
      skills: parseSkills(form.skillsText)
    })
    applyProfile(data)
    ElMessage.success(t('common.success'))
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <div class="profile-heading">
        <UserRound :size="24" />
        <h2>{{ t('home.profile') }}</h2>
      </div>
      <el-button type="primary" :icon="Save" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
    </div>

    <section v-if="profile" class="profile-section">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('fields.fullName')">{{ profile.full_name }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.nameKana')">{{ profile.name_kana || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.email')">{{ profile.email }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.birthDate')">{{ profile.birth_date || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.nationality')">{{ profile.nationality || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.graduationStatus')">{{ profile.graduation_status || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.residence')">{{ profile.residence || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('fields.employeeType')">{{ profile.employee_type || '-' }}</el-descriptions-item>
      </el-descriptions>
      <div class="formal-actions">
        <span class="muted">{{ profileCopy.requestHint }}</span>
        <el-button type="primary" plain @click="changeOpen = true">{{ profileCopy.request }}</el-button>
      </div>
    </section>

    <section v-if="profile" class="profile-section">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item :label="t('fields.phone')" prop="phone"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item :label="t('fields.nearestStation')"><el-input v-model="form.nearest_station" /></el-form-item>
        <el-form-item :label="t('fields.itYears')"><el-input-number v-model="form.it_years" :min="0" :step="0.5" /></el-form-item>
        <el-form-item :label="t('fields.talentCategory')"><el-input v-model="form.talent_category" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.languages')"><el-input v-model="form.languages" type="textarea" :rows="2" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.certifications')"><el-input v-model="form.certifications" type="textarea" :rows="2" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.skills')"><el-input v-model="form.skillsText" type="textarea" :rows="2" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.technicalExperience')"><el-input v-model="form.technical_experience" type="textarea" :rows="4" /></el-form-item>
      </el-form>
    </section>

    <section v-if="requests.length" class="profile-section">
      <h3>{{ profileCopy.history }}</h3>
      <el-table :data="requests" border>
        <el-table-column prop="created_at" :label="t('fields.createdAt')" min-width="170" />
        <el-table-column prop="title" min-width="220" />
        <el-table-column prop="status" width="130"><template #default="{ row }"><el-tag>{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column prop="approver_name" :label="t('app.role')" min-width="130" />
        <el-table-column prop="comment" :label="t('fields.note')" min-width="180" />
      </el-table>
    </section>

    <el-dialog v-model="changeOpen" :title="profileCopy.request" width="min(720px, 94vw)">
      <el-form label-position="top" class="form-grid">
        <el-form-item :label="t('fields.fullName')"><el-input v-model="changeForm.full_name" /></el-form-item>
        <el-form-item :label="t('fields.nameKana')"><el-input v-model="changeForm.name_kana" /></el-form-item>
        <el-form-item :label="t('fields.birthDate')"><el-date-picker v-model="changeForm.birth_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item :label="t('fields.email')"><el-input v-model="changeForm.email" /></el-form-item>
        <el-form-item :label="t('fields.nationality')"><el-select v-model="changeForm.nationality"><el-option v-for="item in ['日本', '中国', 'その他']" :key="item" :label="item" :value="item" /></el-select></el-form-item>
        <el-form-item :label="t('fields.graduationStatus')"><el-select v-model="changeForm.graduation_status"><el-option v-for="item in ['大学卒業', '短大卒業', '大学院修了', '中退・その他']" :key="item" :label="item" :value="item" /></el-select></el-form-item>
        <el-form-item class="span-2" :label="t('fields.residence')"><el-input v-model="changeForm.residence" /></el-form-item>
        <el-form-item class="span-2" :label="profileCopy.reason"><el-input v-model="changeForm.reason" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="changeOpen = false">{{ t('common.cancel') }}</el-button><el-button type="primary" :loading="changeSaving" @click="submitChange">{{ profileCopy.submit }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.profile-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}

.profile-heading h2 {
  margin: 0;
}

.profile-section {
  margin-top: 16px;
  padding: 18px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
}
.formal-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 14px; }
.profile-section h3 { margin: 0 0 12px; }
</style>
