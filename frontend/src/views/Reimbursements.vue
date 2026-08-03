<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, Pencil, Plus, RefreshCw, Search, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const employees = ref([])
const q = ref('')
const statusFilter = ref('')
const payMonth = ref('')
const dialog = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const uploadFiles = ref([])
const form = reactive(defaultForm())

const isManager = computed(() => ['admin', 'hr'].includes(auth.user?.role))
const expenseTypeOptions = ['交通費', '出張費', '懇親会費', 'その他']
const statusOptions = ['pending', 'approved', 'rejected']
const { pager, pageRows } = usePagination(rows)
const rules = computed(() => ({
  expense_type: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  period_start_month: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  amount: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  employee_id: isManager.value ? [{ required: true, message: t('validation.required'), trigger: 'change' }] : [],
  files: editingId.value ? [] : [{ validator: validateFiles, trigger: 'change' }]
}))

function defaultForm() {
  return {
    expense_type: '交通費',
    period_start_month: currentMonth(),
    period_end_month: '',
    employee_id: null,
    amount: 0,
    pay_month: '',
    note: '',
    files: []
  }
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function validateFiles(_rule, _value, callback) {
  if (!uploadFiles.value.length) {
    callback(new Error(t('validation.required')))
    return
  }
  callback()
}

function showApiError(error) {
  const detail = error.response?.data?.detail
  ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
}

async function load() {
  rows.value = (await api.get('/reimbursements', {
    params: {
      q: q.value || undefined,
      status_filter: statusFilter.value || undefined,
      pay_month: payMonth.value || undefined
    }
  })).data
}

async function loadEmployees() {
  if (!isManager.value) return
  try {
    employees.value = (await api.get('/employees')).data
  } catch {
    employees.value = []
  }
}

function resetForm() {
  editingId.value = null
  uploadFiles.value = []
  Object.assign(form, defaultForm())
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  dialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  uploadFiles.value = []
  Object.assign(form, {
    expense_type: row.expense_type,
    period_start_month: row.period_start_month,
    period_end_month: row.period_end_month,
    employee_id: row.employee_id,
    amount: row.amount,
    pay_month: row.pay_month,
    note: row.note || '',
    files: []
  })
  dialog.value = true
}

function handleFileChange(_file, fileList) {
  uploadFiles.value = fileList
  form.files = fileList
}

function handleFileRemove(_file, fileList) {
  uploadFiles.value = fileList
  form.files = fileList
}

async function save() {
  try {
    await formRef.value?.validate()
    if (editingId.value) {
      await api.put(`/reimbursements/${editingId.value}`, {
        expense_type: form.expense_type,
        period_start_month: form.period_start_month,
        period_end_month: form.period_end_month || null,
        employee_id: form.employee_id,
        amount: form.amount,
        pay_month: form.pay_month || null,
        note: form.note || null
      })
    } else {
      const data = new FormData()
      data.append('expense_type', form.expense_type)
      data.append('period_start_month', form.period_start_month)
      if (form.period_end_month) data.append('period_end_month', form.period_end_month)
      if (isManager.value && form.employee_id) data.append('employee_id', form.employee_id)
      data.append('amount', form.amount)
      if (form.pay_month) data.append('pay_month', form.pay_month)
      if (form.note) data.append('note', form.note)
      uploadFiles.value.forEach((file) => data.append('files', file.raw))
      await api.post('/reimbursements', data)
    }
    ElMessage.success(t('common.success'))
    dialog.value = false
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(t('common.confirmDelete'), t('common.delete'), { type: 'warning' })
    await api.delete(`/reimbursements/${row.id}`)
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

function download(url) {
  if (url) window.open(url, '_blank')
}

onMounted(async () => {
  await Promise.all([load(), loadEmployees()])
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ t('nav.reimbursements') }}</h2>
      <div class="toolbar">
        <el-input v-model="q" :prefix-icon="Search" :placeholder="t('common.search')" clearable @keyup.enter="load" />
        <el-select v-model="statusFilter" clearable :placeholder="t('external.status')" style="width: 150px" @change="load">
          <el-option v-for="option in statusOptions" :key="option" :label="option" :value="option" />
        </el-select>
        <el-date-picker v-model="payMonth" type="month" value-format="YYYY-MM" :placeholder="t('reimbursements.payMonth')" clearable @change="load" />
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('common.create') }}</el-button>
      </div>
    </div>

    <el-table :data="pageRows" height="calc(100vh - 280px)" stripe>
      <el-table-column prop="expense_type" :label="t('reimbursements.expenseType')" min-width="130" sortable />
      <el-table-column prop="employee_name" :label="t('fields.employee')" min-width="150" />
      <el-table-column :label="t('reimbursements.period')" min-width="150" sortable>
        <template #default="{ row }">{{ row.period_start_month }} - {{ row.period_end_month }}</template>
      </el-table-column>
      <el-table-column :label="t('fields.amount')" width="130" sortable>
        <template #default="{ row }">{{ money(row.amount) }}</template>
      </el-table-column>
      <el-table-column prop="pay_month" :label="t('reimbursements.payMonth')" width="130" sortable />
      <el-table-column prop="status" :label="t('external.status')" width="120" />
      <el-table-column :label="t('reimbursements.files')" min-width="160">
        <template #default="{ row }">
          <el-button
            v-for="file in row.invoice_files"
            :key="file.download_url"
            text
            type="primary"
            :icon="Download"
            @click="download(file.download_url)"
          >
            {{ file.name }}
          </el-button>
          <span v-if="!row.invoice_files?.length">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="note" :label="t('fields.note')" min-width="180" show-overflow-tooltip />
      <el-table-column fixed="right" :label="t('common.actions')" width="130">
        <template #default="{ row }">
          <el-button v-if="row.status !== 'approved'" text :icon="Pencil" @click="openEdit(row)" />
          <el-button v-if="row.status !== 'approved'" text type="danger" :icon="Trash2" @click="remove(row)" />
        </template>
      </el-table-column>
    </el-table>
    <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="rows.length" />

    <el-dialog v-model="dialog" :title="editingId ? t('common.edit') : t('common.create')" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item :label="t('reimbursements.expenseType')" prop="expense_type">
          <el-select v-model="form.expense_type">
            <el-option v-for="option in expenseTypeOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isManager" :label="t('fields.employee')" prop="employee_id">
          <el-select v-model="form.employee_id" filterable>
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.full_name" :value="employee.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('reimbursements.periodStart')" prop="period_start_month">
          <el-date-picker v-model="form.period_start_month" type="month" value-format="YYYY-MM" />
        </el-form-item>
        <el-form-item :label="t('reimbursements.periodEnd')">
          <el-date-picker v-model="form.period_end_month" type="month" value-format="YYYY-MM" />
        </el-form-item>
        <el-form-item :label="t('fields.amount')" prop="amount"><el-input-number v-model="form.amount" :min="0" :controls="false" /></el-form-item>
        <el-form-item :label="t('reimbursements.payMonth')"><el-date-picker v-model="form.pay_month" type="month" value-format="YYYY-MM" /></el-form-item>
        <el-form-item class="span-2" :label="t('reimbursements.files')" prop="files">
          <el-upload
            v-model:file-list="uploadFiles"
            multiple
            :auto-upload="false"
            accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-button>{{ t('common.upload') }}</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item class="span-2" :label="t('fields.note')"><el-input v-model="form.note" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
