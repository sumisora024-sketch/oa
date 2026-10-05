<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, KeyRound, Pencil, Plus, RefreshCw, Search, Trash2, Upload } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { downloadCsv as exportCsv } from '../utils/csv'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const selectedRows = ref([])
const loading = ref(false)
const q = ref('')
const dialog = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const form = reactive(defaultForm())

const canCreate = computed(() => auth.can('employees', 'create'))
const canImport = computed(() => auth.can('employees', 'import'))
const canUpdate = computed(() => auth.can('employees', 'update') || auth.can('employees', 'update_self'))
const canManageRole = computed(() => auth.user?.role === 'admin')
const canManageAnnual = computed(() => ['admin', 'soumu', 'hr'].includes(auth.user?.role))
const canResetPassword = computed(() => auth.user?.role === 'admin')
const nationalityOptions = ['中国', '日本', 'その他']
const graduationOptions = ['大学卒業', '短大卒業', '大学院修了', '中退・その他']
const employeeTypeOptions = ['一般社員', 'hr', '総務', '営業', '管理者']
const namePattern = /^[A-Za-z\u3040-\u30ff\u3400-\u9fff々〆ヶ・ー\s\u3000.'-]+$/u
const employeeTypeFilters = computed(() => employeeTypeOptions.map((option) => ({ text: option, value: option })))
const nationalityFilters = computed(() => nationalityOptions.map((option) => ({ text: option, value: option })))
const graduationFilters = computed(() => graduationOptions.map((option) => ({ text: option, value: option })))
const { pager, pageRows } = usePagination(rows)

const rules = computed(() => ({
  full_name: [
    { required: true, message: t('validation.required'), trigger: 'blur' },
    { pattern: namePattern, message: t('validation.employeeName'), trigger: 'blur' }
  ],
  email: [{ required: true, type: 'email', message: t('validation.email'), trigger: 'blur' }],
  phone: [
    { required: true, message: t('validation.required'), trigger: 'blur' },
    { validator: validatePhone, trigger: 'blur' }
  ],
  birth_date: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  graduation_status: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  nationality: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  employee_type: [{ required: true, message: t('validation.required'), trigger: 'change' }]
}))

function defaultForm() {
  return {
    full_name: '', name_kana: '', email: '', phone: '', birth_date: '', age: null,
    graduation_status: '', residence: '', nearest_station: '', nationality: '',
    employee_type: '一般社員',
    estimated_annual_salary: null,
    estimated_annual_salary_manual: false,
    languages: '', certifications: '', technical_experience: '', it_years: null,
    talent_category: '', skillsText: ''
  }
}

function resetForm() {
  Object.assign(form, defaultForm())
  editingId.value = null
  formRef.value?.clearValidate()
}

function calculateAge(birthDate) {
  if (!birthDate) return null
  const birth = new Date(birthDate)
  const today = new Date()
  let age = today.getFullYear() - birth.getFullYear()
  const beforeBirthday = today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())
  if (beforeBirthday) age -= 1
  return age >= 0 ? age : null
}

function refreshAge() {
  form.age = calculateAge(form.birth_date)
}

function validatePhone(_rule, value, callback) {
  const text = String(value || '').trim()
  const compact = text.replace(/[-\s]/g, '')
  const normalized = compact.startsWith('+81') ? compact.replace('+81', '0') : compact
  const pattern = /^(?:\+81[- ]?)?(?:0?\d{1,4}[- ]?\d{1,4}[- ]?\d{3,4})$/
  if (!pattern.test(text) || !normalized.startsWith('0') || ![10, 11].includes(normalized.length)) {
    callback(new Error(t('validation.jpPhone')))
    return
  }
  callback()
}

function parseSkills(text) {
  return (text || '').split(/[,，、;\n]/).map((item) => item.trim()).filter(Boolean).map((item) => {
    const [name, level = '中'] = item.split(/[:：]/)
    return { name: name.trim(), level: level.trim() || '中' }
  })
}

function fillForm(row) {
  resetForm()
  editingId.value = row.id
  Object.assign(form, {
    ...row,
    skillsText: (row.skills || []).map((item) => `${item.name}:${item.level}`).join(', ')
  })
  refreshAge()
  dialog.value = true
}

function payload() {
  const data = { ...form, skills: parseSkills(form.skillsText) }
  if (data.estimated_annual_salary !== null && data.estimated_annual_salary !== undefined && data.estimated_annual_salary !== '') {
    data.estimated_annual_salary_manual = true
  }
  delete data.skillsText
  delete data.age
  Object.keys(data).forEach((key) => {
    if (data[key] === '') data[key] = null
  })
  return data
}

async function load() {
  loading.value = true
  try {
    if (auth.can('employees', 'read')) {
      const { data } = await api.get('/employees', { params: { q: q.value || undefined } })
      rows.value = data
    } else if (auth.user?.employee_id) {
      const { data } = await api.get(`/employees/${auth.user.employee_id}`)
      rows.value = [data]
    } else {
      rows.value = []
    }
  } finally {
    loading.value = false
  }
}

async function save() {
  try {
    await formRef.value?.validate()
    let response
    if (editingId.value) {
      response = await api.put(`/employees/${editingId.value}`, payload())
    } else {
      response = await api.post('/employees', payload())
    }
    const lockedMonths = response.data?.salary_sync?.locked_months || []
    if (lockedMonths.length) {
      ElMessage.warning(`給与がロックされているため金額を更新していません: ${lockedMonths.join(', ')}`)
    } else {
      ElMessage.success(t('common.success'))
    }
    dialog.value = false
    await load()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`${t('common.delete')} ${row.full_name}?`)
  await api.delete(`/employees/${row.id}`)
  await load()
}

async function deleteSelected() {
  if (!selectedRows.value.length || !auth.can('employees', 'delete')) return
  try {
    await ElMessageBox.confirm(`${selectedRows.value.length}件を削除します。`, t('common.delete'), { type: 'warning' })
    await Promise.all(selectedRows.value.map((row) => api.delete(`/employees/${row.id}`)))
    selectedRows.value = []
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(detail || t('common.failed'))
  }
}

async function resetPassword(row) {
  await ElMessageBox.confirm(t('employees.resetPasswordConfirm', { name: row.full_name }), t('employees.resetPassword'), { type: 'warning' })
  const { data } = await api.post(`/employees/${row.id}/password/reset`)
  ElMessage.success(t('employees.passwordResetDone', { email: data.email || row.platform_email || '' }))
}

async function uploadFile(options) {
  try {
    const data = new FormData()
    data.append('file', options.file)
    const res = await api.post('/employees/import-xlsx', data)
    ElMessage.success(`created ${res.data.created}, updated ${res.data.updated}`)
    if (res.data.errors?.length) ElMessage.warning(res.data.errors.join(' / '))
    await load()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.join(' / ') : detail || t('common.failed'))
  }
}

function download(row) {
  window.open(`/api/employees/${row.id}/employment-info/download`, '_blank')
}

function downloadRows(rowsToExport, filename) {
  const result = exportCsv(rowsToExport, [
    { key: 'full_name', label: t('fields.fullName') },
    { key: 'name_kana', label: t('fields.nameKana') },
    { key: 'email', label: t('fields.email') },
    { key: 'platform_email', label: t('fields.platformEmail') },
    { key: 'phone', label: t('fields.phone') },
    { key: 'employee_type', label: t('fields.employeeType') },
    { key: 'estimated_annual_salary', label: t('fields.estimatedAnnualSalary') },
    { key: 'nationality', label: t('fields.nationality') },
    { key: 'graduation_status', label: t('fields.graduationStatus') },
    { key: 'nearest_station', label: t('fields.nearestStation') },
    { key: 'talent_category', label: t('fields.talentCategory') },
    { key: 'it_years', label: t('fields.itYears') }
  ], filename)
  if (!result.ok) ElMessage.warning(result.message)
}

function handleBatchCommand(command) {
  if (command === 'delete') {
    deleteSelected()
    return
  }
  if (command === 'selected') {
    downloadRows(selectedRows.value, 'employees-selected.csv')
    return
  }
  downloadRows(rows.value, 'employees-list.csv')
}

function filterByValue(value, row, column) {
  return row[column.property] === value
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ t('nav.internalEmployees') }}</h2>
      <div class="toolbar">
        <el-input v-model="q" :prefix-icon="Search" :placeholder="t('common.search')" clearable @keyup.enter="load" />
        <span v-if="selectedRows.length" class="muted">{{ selectedRows.length }} 件選択中</span>
        <el-button type="danger" :icon="Trash2" :disabled="!selectedRows.length || !auth.can('employees', 'delete')" @click="deleteSelected">選択行を削除</el-button>
        <el-button :icon="Download" :disabled="!selectedRows.length" @click="downloadRows(selectedRows, 'employees-selected.csv')">選択行をダウンロード</el-button>
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
        <el-upload v-if="canImport" :show-file-list="false" :http-request="uploadFile" accept=".xlsx,.xlsm">
          <el-button :icon="Upload">{{ t('common.import') }}</el-button>
        </el-upload>
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="resetForm(); dialog = true">{{ t('common.create') }}</el-button>
      </div>
    </div>
    <p class="muted">{{ t('employees.importHelp') }} · {{ t('employees.defaultPassword') }}</p>
    <el-table :data="pageRows" v-loading="loading" height="calc(100vh - 280px)" stripe @selection-change="selectedRows = $event">
      <el-table-column type="selection" width="46" />
      <el-table-column prop="full_name" :label="t('fields.fullName')" min-width="130" sortable />
      <el-table-column prop="name_kana" :label="t('fields.nameKana')" min-width="150" sortable />
      <el-table-column prop="email" :label="t('fields.email')" min-width="210" sortable />
      <el-table-column prop="platform_email" :label="t('fields.platformEmail')" min-width="220" sortable />
      <el-table-column prop="phone" :label="t('fields.phone')" min-width="120" />
      <el-table-column prop="employee_type" :label="t('fields.employeeType')" min-width="110" sortable :filters="employeeTypeFilters" :filter-method="filterByValue" />
      <el-table-column prop="estimated_annual_salary" :label="t('fields.estimatedAnnualSalary')" min-width="140" sortable>
        <template #default="{ row }">{{ row.estimated_annual_salary ? Number(row.estimated_annual_salary).toLocaleString() : '-' }}</template>
      </el-table-column>
      <el-table-column prop="nationality" :label="t('fields.nationality')" width="110" sortable :filters="nationalityFilters" :filter-method="filterByValue" />
      <el-table-column prop="graduation_status" :label="t('fields.graduationStatus')" min-width="130" sortable :filters="graduationFilters" :filter-method="filterByValue" />
      <el-table-column prop="nearest_station" :label="t('fields.nearestStation')" min-width="130" sortable />
      <el-table-column prop="talent_category" :label="t('fields.talentCategory')" min-width="120" sortable />
      <el-table-column prop="it_years" :label="t('fields.itYears')" width="100" sortable />
      <el-table-column fixed="right" :label="t('common.actions')" width="230">
        <template #default="{ row }">
          <el-button text :icon="Download" @click="download(row)" />
          <el-button v-if="canResetPassword" text type="warning" :icon="KeyRound" @click="resetPassword(row)" />
          <el-button v-if="canUpdate" text :icon="Pencil" @click="fillForm(row)" />
          <el-button v-if="auth.can('employees', 'delete')" text type="danger" :icon="Trash2" @click="remove(row)" />
        </template>
      </el-table-column>
    </el-table>
    <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="rows.length" />

    <el-dialog v-model="dialog" :title="editingId ? t('common.edit') : t('common.create')" width="760px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item :label="t('fields.fullName')" prop="full_name"><el-input v-model="form.full_name" /></el-form-item>
        <el-form-item :label="t('fields.nameKana')"><el-input v-model="form.name_kana" /></el-form-item>
        <el-form-item :label="t('fields.email')" prop="email"><el-input v-model="form.email" /></el-form-item>
        <el-form-item :label="t('fields.phone')" prop="phone"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item :label="t('fields.birthDate')" prop="birth_date"><el-date-picker v-model="form.birth_date" value-format="YYYY-MM-DD" @change="refreshAge" /></el-form-item>
        <el-form-item :label="t('fields.age')"><el-input-number v-model="form.age" :min="0" disabled /></el-form-item>
        <el-form-item :label="t('fields.graduationStatus')" prop="graduation_status">
          <el-select v-model="form.graduation_status">
            <el-option v-for="option in graduationOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.residence')"><el-input v-model="form.residence" /></el-form-item>
        <el-form-item :label="t('fields.nearestStation')"><el-input v-model="form.nearest_station" /></el-form-item>
        <el-form-item :label="t('fields.nationality')" prop="nationality">
          <el-select v-model="form.nationality">
            <el-option v-for="option in nationalityOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.employeeType')" prop="employee_type">
          <el-select v-model="form.employee_type" :disabled="!canManageRole">
            <el-option v-for="option in employeeTypeOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.itYears')"><el-input-number v-model="form.it_years" :min="0" :step="0.5" /></el-form-item>
        <el-form-item v-if="canManageAnnual" :label="t('fields.estimatedAnnualSalary')"><el-input-number v-model="form.estimated_annual_salary" :min="0" :controls="false" /></el-form-item>
        <el-form-item :label="t('fields.talentCategory')"><el-input v-model="form.talent_category" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.skills')"><el-input v-model="form.skillsText" type="textarea" :rows="2" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.technicalExperience')"><el-input v-model="form.technical_experience" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
