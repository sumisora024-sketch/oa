<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, Pencil, Plus, RefreshCw, Save, Search, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const partners = ref([])
const loading = ref(false)
const dialog = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const q = ref('')

const canEdit = computed(() => ['admin', 'soumu', 'hr'].includes(auth.user?.role))
const partnerOptions = computed(() => partners.value.map((item) => ({ label: item.company_name, value: item.id })))
const { pager, pageRows } = usePagination(rows)

const form = reactive(defaultForm())
const rules = computed(() => ({
  partner_id: [{ required: canEdit.value, message: t('validation.required'), trigger: 'change' }],
  full_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  assignment_month: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  resume: [{ validator: validateRequiredFile, trigger: 'change' }],
  avatar: [{ validator: validateRequiredFile, trigger: 'change' }]
}))

function validateRequiredFile(_rule, value, callback) {
  if (!value) {
    callback(new Error(t('validation.required')))
    return
  }
  callback()
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function defaultForm() {
  return {
    partner_id: null,
    full_name: '',
    assignment_month: currentMonth(),
    contract_end_date: '',
    monthly_hours: null,
    status: 'submitted',
    note: '',
    resume: null,
    avatar: null,
    timesheet: null
  }
}

function resetForm() {
  editingId.value = null
  Object.assign(form, defaultForm())
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  dialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    partner_id: row.partner_id,
    full_name: row.full_name,
    assignment_month: row.assignment_month,
    contract_end_date: row.contract_end_date || '',
    monthly_hours: row.monthly_hours,
    status: row.status,
    note: row.note || '',
    resume: null,
    avatar: null,
    timesheet: null
  })
  dialog.value = true
}

function setFile(field, fileList) {
  form[field] = fileList.map((item) => item.raw).filter(Boolean)[0] || null
  formRef.value?.clearValidate(field)
}

function showApiError(error) {
  const detail = error.response?.data?.detail
  ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
}

async function load() {
  loading.value = true
  try {
    rows.value = (await api.get('/external-personnel', { params: { q: q.value || undefined } })).data
    if (canEdit.value) partners.value = (await api.get('/external/partners')).data
  } finally {
    loading.value = false
  }
}

async function save() {
  try {
    await formRef.value?.validate()
    if (editingId.value) {
      await api.put(`/external-personnel/${editingId.value}`, {
        full_name: form.full_name,
        assignment_month: form.assignment_month,
        contract_end_date: form.contract_end_date || null,
        monthly_hours: form.monthly_hours,
        status: form.status,
        note: form.note || null
      })
    } else {
      const data = new FormData()
      if (form.partner_id) data.append('partner_id', form.partner_id)
      data.append('full_name', form.full_name)
      data.append('assignment_month', form.assignment_month)
      if (form.contract_end_date) data.append('contract_end_date', form.contract_end_date)
      if (form.monthly_hours !== null && form.monthly_hours !== undefined) data.append('monthly_hours', form.monthly_hours)
      if (form.note) data.append('note', form.note)
      if (form.resume) data.append('resume', form.resume)
      if (form.avatar) data.append('avatar', form.avatar)
      if (form.timesheet) data.append('timesheet', form.timesheet)
      await api.post('/external-personnel', data)
    }
    ElMessage.success(t('common.success'))
    dialog.value = false
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function setStatus(row, status) {
  try {
    let note = null
    if (status === 'rejected') {
      const result = await ElMessageBox.prompt(t('approvals.rejectPrompt'), t('approvals.rejectTitle'), {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        inputType: 'textarea',
        inputValidator: (value) => Boolean(String(value || '').trim()) || t('approvals.rejectRequired')
      })
      note = result.value.trim()
    }
    await api.post(`/external-personnel/${row.id}/status`, { status, note })
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    if (error?.response) showApiError(error)
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(t('common.confirmDelete'), t('common.delete'), { type: 'warning' })
    await api.delete(`/external-personnel/${row.id}`)
    await load()
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

function download(url) {
  if (url) window.open(url, '_blank')
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ t('nav.externalEmployees') }}</h2>
      <div class="toolbar">
        <el-input v-model="q" :prefix-icon="Search" :placeholder="t('common.search')" clearable @keyup.enter="load" />
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('common.create') }}</el-button>
      </div>
    </div>

    <div class="table-scroll-shell">
      <el-table :data="pageRows" v-loading="loading" height="calc(100vh - 270px)" stripe>
      <el-table-column prop="full_name" :label="t('fields.fullName')" min-width="140" sortable />
      <el-table-column prop="company_name" :label="t('external.companyName')" min-width="220" sortable />
      <el-table-column prop="assignment_month" :label="t('subcontracting.assignmentMonth')" width="130" sortable />
      <el-table-column prop="contract_end_date" :label="t('external.contractEndDate')" width="140" sortable />
      <el-table-column prop="monthly_hours" :label="t('fields.monthlyHours')" width="130" sortable />
      <el-table-column prop="status" :label="t('external.status')" width="120" sortable />
      <el-table-column :label="t('external.fixedFiles')" min-width="180">
        <template #default="{ row }">
          <el-button v-if="row.resume_download_url" text :icon="Download" @click="download(row.resume_download_url)">CV</el-button>
          <el-button v-if="row.avatar_download_url" text :icon="Download" @click="download(row.avatar_download_url)">PNG</el-button>
          <el-button v-if="row.timesheet_download_url" text :icon="Download" @click="download(row.timesheet_download_url)">TS</el-button>
        </template>
      </el-table-column>
      <el-table-column fixed="right" :label="t('common.actions')" width="190">
        <template #default="{ row }">
          <el-button v-if="canEdit" text type="primary" :icon="Save" @click="setStatus(row, 'confirmed')" />
          <el-button v-if="canEdit" text :icon="Pencil" @click="openEdit(row)" />
          <el-button v-if="canEdit" text type="danger" :icon="Trash2" @click="remove(row)" />
        </template>
      </el-table-column>
      </el-table>
    </div>
    <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="rows.length" />

    <el-dialog v-model="dialog" :title="editingId ? t('common.edit') : t('common.create')" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item v-if="canEdit" :label="t('external.companyName')" prop="partner_id">
          <el-select v-model="form.partner_id" filterable>
            <el-option v-for="partner in partnerOptions" :key="partner.value" :label="partner.label" :value="partner.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.fullName')" prop="full_name"><el-input v-model="form.full_name" /></el-form-item>
        <el-form-item :label="t('subcontracting.assignmentMonth')" prop="assignment_month"><el-date-picker v-model="form.assignment_month" type="month" value-format="YYYY-MM" /></el-form-item>
        <el-form-item :label="t('external.contractEndDate')"><el-date-picker v-model="form.contract_end_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item :label="t('fields.monthlyHours')"><el-input-number v-model="form.monthly_hours" :min="0" :controls="false" /></el-form-item>
        <el-form-item v-if="editingId" :label="t('external.status')"><el-select v-model="form.status"><el-option label="submitted" value="submitted" /><el-option label="confirmed" value="confirmed" /><el-option label="rejected" value="rejected" /></el-select></el-form-item>
        <el-form-item class="span-2" :label="t('fields.note')"><el-input v-model="form.note" type="textarea" /></el-form-item>
        <el-form-item v-if="!editingId" label="CV" prop="resume"><el-upload :auto-upload="false" :limit="1" :on-change="(_file, files) => setFile('resume', files)" :on-remove="(_file, files) => setFile('resume', files)"><el-button>{{ t('common.upload') }}</el-button></el-upload></el-form-item>
        <el-form-item v-if="!editingId" label="PNG" prop="avatar"><el-upload accept=".png,image/png" :auto-upload="false" :limit="1" :on-change="(_file, files) => setFile('avatar', files)" :on-remove="(_file, files) => setFile('avatar', files)"><el-button>{{ t('common.upload') }}</el-button></el-upload></el-form-item>
        <el-form-item v-if="!editingId" label="Timesheet"><el-upload :auto-upload="false" :limit="1" :on-change="(_file, files) => setFile('timesheet', files)" :on-remove="(_file, files) => setFile('timesheet', files)"><el-button>{{ t('common.upload') }}</el-button></el-upload></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
