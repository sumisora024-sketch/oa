<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Columns3, Download, Eye, FileUp, Pencil, Plus, RefreshCw, Save, Search, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const rows = ref([])
const employees = ref([])
const salaryRows = ref([])
const selectedSalaries = ref([])
const detailRow = ref(null)
const activeTab = ref(route.name === 'salaryManagement' ? 'salaries' : 'contracts')
const dialog = ref(false)
const editingContractId = ref(null)
const pdfDialog = ref(false)
const detailDrawer = ref(false)
const q = ref('')
const salaryQ = ref('')
const formRef = ref(null)
const pdfFormRef = ref(null)
const form = reactive(defaultContractForm())
const pdfForm = reactive({ employee_id: null, title: '雇用契約書', file: null })
const salaryMonth = ref(currentMonth())
const contractTypeOptions = ['正社員', '契約社員', 'freelance', 'アルバイト', 'その他']
const companyOptions = ['日本インフォテック株式会社', 'その他']
const visibleColumns = reactive({
  title: true,
  employee: true,
  contract_type: true,
  vendor_company: true,
  base_salary: true,
  allowance_total: true,
  base_unit_price_low: true,
  base_unit_price_high: true,
  start_date: false,
  end_date: true,
  duty: false,
  workplace: false
})
const columnOptions = [
  'title', 'employee', 'contract_type', 'vendor_company', 'base_salary', 'allowance_total',
  'base_unit_price_low', 'base_unit_price_high', 'start_date', 'end_date', 'duty', 'workplace'
]
const rules = computed(() => ({
  employee_id: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  title: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  contract_type: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  vendor_company: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  hours_range: [{ pattern: /^\d+(?:\.\d+)?-\d+(?:\.\d+)?$/, message: t('contracts.hoursRangeInvalid'), trigger: 'blur' }]
}))
const pdfRules = computed(() => ({
  employee_id: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  title: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  file: [{ required: true, message: t('validation.required'), trigger: 'change' }]
}))

const employeeNameById = computed(() => Object.fromEntries(employees.value.map((employee) => [employee.id, employee.full_name])))
const isEmployeeRole = computed(() => auth.user?.role === 'employee')
const isSalaryRoute = computed(() => route.name === 'salaryManagement')
const isContractTab = computed(() => activeTab.value === 'contracts')
const displayColumnOptions = computed(() => isEmployeeRole.value ? columnOptions.filter((column) => !['title', 'employee'].includes(column)) : columnOptions)
const salaryTotals = computed(() => salaryRows.value.reduce((totals, row) => {
  totals.estimated += Number(row.estimated_salary || 0)
  totals.actual += Number(row.actual_salary || 0)
  return totals
}, { estimated: 0, actual: 0 }))
const filteredContracts = computed(() => {
  const text = q.value.trim().toLowerCase()
  if (!text) return rows.value
  return rows.value.filter((row) => [
    row.title,
    contractEmployeeName(row),
    row.contract_type,
    row.vendor_company,
    row.attributes?.workplace,
    row.attributes?.duty
  ].some((value) => String(value || '').toLowerCase().includes(text)))
})
const filteredSalaries = computed(() => {
  const text = salaryQ.value.trim().toLowerCase()
  if (!text) return salaryRows.value
  return salaryRows.value.filter((row) => [row.employee_name, row.employee_email, row.employee_id]
    .some((value) => String(value || '').toLowerCase().includes(text)))
})
const { pager: contractPager, pageRows: pagedContracts } = usePagination(filteredContracts)
const { pager: salaryPager, pageRows: pagedSalaries } = usePagination(filteredSalaries)

function defaultContractForm() {
  return {
    employee_id: null,
    title: '',
    contract_type: '',
    vendor_company: '',
    start_date: '',
    end_date: '',
    base_salary: null,
    hours_range: '140-180',
    workplace: '',
    duty: '',
    parsed_text: '',
    allowances: [],
    source_attributes: {}
  }
}

function openContractCreate() {
  editingContractId.value = null
  Object.assign(form, defaultContractForm())
  dialog.value = true
}

function openContractEdit(row) {
  editingContractId.value = row.id
  Object.assign(form, {
    employee_id: row.employee_id,
    title: row.title || '',
    contract_type: row.contract_type || '',
    vendor_company: row.vendor_company || '',
    start_date: row.start_date || '',
    end_date: row.end_date === '9999-12-31' ? '' : (row.end_date || ''),
    base_salary: row.attributes?.base_salary ?? null,
    hours_range: row.attributes?.hours_range || '140-180',
    workplace: row.attributes?.workplace || '',
    duty: row.attributes?.duty || '',
    parsed_text: row.parsed_text || '',
    allowances: (row.attributes?.allowances || []).map((item) => ({ name: item.name || '', amount: Number(item.amount || 0) })),
    source_attributes: { ...(row.attributes || {}) }
  })
  dialog.value = true
}

function addAllowance() {
  form.allowances.push({ name: '', amount: 0 })
}

function removeAllowance(index) {
  form.allowances.splice(index, 1)
}

function contractPayload() {
  return {
    employee_id: form.employee_id,
    title: form.title,
    contract_type: form.contract_type,
    vendor_company: form.vendor_company,
    start_date: form.start_date || null,
    end_date: form.end_date || null,
    parsed_text: form.parsed_text || null,
    attributes: {
      ...form.source_attributes,
      base_salary: form.base_salary,
      hours_range: form.hours_range || '140-180',
      workplace: form.workplace || null,
      duty: form.duty || null,
      allowances: form.allowances
        .map((item) => ({ name: String(item.name || '').trim(), amount: Number(item.amount || 0) }))
        .filter((item) => item.name || item.amount)
    }
  }
}

function warnLockedSalary(sync) {
  if (!sync) return false
  const entries = sync.employees || [sync]
  const locked = entries.flatMap((entry) => (entry.locked_months || []).map((month) => `${entry.employee_id}: ${month}`))
  if (!locked.length) return false
  ElMessage.warning(`給与がロックされているため金額を更新していません: ${locked.join(', ')}`)
  return true
}

async function load() {
  const { data } = await api.get('/contracts')
  rows.value = data
  if (auth.canAny('employees', ['read'])) {
    try {
      employees.value = (await api.get('/employees')).data
    } catch {
      employees.value = []
    }
  }
  applyContractQueryFilter()
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

async function loadSalaries() {
  const { data } = await api.get('/contracts/salaries', { params: { year_month: salaryMonth.value } })
  salaryRows.value = data.map((row) => ({
    ...row,
    hours_range: row.hours_range || row.calculation_detail?.hours_range || '140-180',
    pension: row.pension ?? row.calculation_detail?.pension ?? 0,
    resident_tax: row.resident_tax ?? row.calculation_detail?.resident_tax ?? 0,
    insurance_fee: row.health_insurance ?? row.insurance_fee ?? row.calculation_detail?.health_insurance ?? row.calculation_detail?.insurance_fee ?? 0,
    health_insurance: row.health_insurance ?? row.insurance_fee ?? row.calculation_detail?.health_insurance ?? row.calculation_detail?.insurance_fee ?? 0,
    care_insurance: row.care_insurance ?? row.calculation_detail?.care_insurance ?? 0,
    employment_insurance: row.employment_insurance ?? row.calculation_detail?.employment_insurance ?? 0,
    income_tax: row.income_tax ?? row.calculation_detail?.income_tax ?? 0,
    other_deduction: row.other_deduction ?? row.calculation_detail?.other_deduction ?? 0,
    commuting_allowance: row.commuting_allowance ?? row.calculation_detail?.commuting_allowance ?? 0,
    other_payment: row.other_payment ?? row.calculation_detail?.other_payment ?? 0,
    gross_payment_total: row.gross_payment_total ?? row.calculation_detail?.gross_payment_total ?? 0,
    deduction_total: row.deduction_total ?? row.calculation_detail?.deduction_total ?? 0,
    base_unit_price_low: row.base_unit_price_low ?? row.calculation_detail?.base_unit_price_low,
    base_unit_price_high: row.base_unit_price_high ?? row.calculation_detail?.base_unit_price_high,
    reimbursement_amount: row.reimbursement_amount ?? row.calculation_detail?.reimbursement_amount ?? 0,
    _original_actual_salary: row.actual_salary ?? null,
    locked: Boolean(row.locked)
  }))
}

async function refreshCurrent() {
  if (activeTab.value === 'salaries') {
    await loadSalaries()
  } else {
    await load()
  }
}

async function updateSalary(row) {
  const payload = {
    hours_range: row.hours_range || '140-180',
    pension: row.pension ?? 0,
    resident_tax: row.resident_tax ?? 0,
    insurance_fee: row.health_insurance ?? row.insurance_fee ?? 0,
    health_insurance: row.health_insurance ?? row.insurance_fee ?? 0,
    care_insurance: row.care_insurance ?? 0,
    employment_insurance: row.employment_insurance ?? 0,
    income_tax: row.income_tax ?? 0,
    other_deduction: row.other_deduction ?? 0,
    commuting_allowance: row.commuting_allowance ?? 0,
    other_payment: row.other_payment ?? 0,
    locked: Boolean(row.locked),
    note: row.note || null
  }
  if ((row.actual_salary ?? null) !== (row._original_actual_salary ?? null)) {
    payload.actual_salary = row.actual_salary ?? null
  }
  const { data } = await api.put(`/contracts/salaries/${row.id}`, payload)
  Object.assign(row, data, {
    hours_range: data.hours_range || data.calculation_detail?.hours_range || '140-180',
    pension: data.pension ?? data.calculation_detail?.pension ?? 0,
    resident_tax: data.resident_tax ?? data.calculation_detail?.resident_tax ?? 0,
    insurance_fee: data.health_insurance ?? data.insurance_fee ?? data.calculation_detail?.health_insurance ?? data.calculation_detail?.insurance_fee ?? 0,
    health_insurance: data.health_insurance ?? data.insurance_fee ?? data.calculation_detail?.health_insurance ?? data.calculation_detail?.insurance_fee ?? 0,
    care_insurance: data.care_insurance ?? data.calculation_detail?.care_insurance ?? 0,
    employment_insurance: data.employment_insurance ?? data.calculation_detail?.employment_insurance ?? 0,
    income_tax: data.income_tax ?? data.calculation_detail?.income_tax ?? 0,
    other_deduction: data.other_deduction ?? data.calculation_detail?.other_deduction ?? 0,
    commuting_allowance: data.commuting_allowance ?? data.calculation_detail?.commuting_allowance ?? 0,
    other_payment: data.other_payment ?? data.calculation_detail?.other_payment ?? 0,
    gross_payment_total: data.gross_payment_total ?? data.calculation_detail?.gross_payment_total ?? 0,
    deduction_total: data.deduction_total ?? data.calculation_detail?.deduction_total ?? 0,
    base_unit_price_low: data.base_unit_price_low ?? data.calculation_detail?.base_unit_price_low,
    base_unit_price_high: data.base_unit_price_high ?? data.calculation_detail?.base_unit_price_high,
    reimbursement_amount: data.reimbursement_amount ?? data.calculation_detail?.reimbursement_amount ?? 0,
    _original_actual_salary: data.actual_salary ?? null,
    locked: Boolean(data.locked)
  })
  ElMessage.success(t('common.success'))
}

function handleTabChange(name) {
  if (name === 'salaries' && auth.can('contracts', 'update')) loadSalaries()
}

function syncRouteTab() {
  activeTab.value = route.name === 'salaryManagement' ? 'salaries' : 'contracts'
  if (activeTab.value === 'salaries' && auth.can('contracts', 'update')) loadSalaries()
  if (activeTab.value === 'contracts') applyContractQueryFilter()
}

async function save() {
  try {
    await formRef.value?.validate()
    const payload = contractPayload()
    let response
    if (editingContractId.value) {
      response = await api.put(`/contracts/${editingContractId.value}`, payload)
    } else {
      response = await api.post('/contracts', payload)
    }
    if (!warnLockedSalary(response.data?.salary_sync)) ElMessage.success(t('common.success'))
    dialog.value = false
    await load()
    if (auth.can('contracts', 'update')) await loadSalaries()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  }
}

async function deleteContract(row) {
  try {
    await ElMessageBox.confirm(t('common.confirmDelete'), t('common.delete'), { type: 'warning' })
    const { data } = await api.delete(`/contracts/${row.id}`)
    if (!warnLockedSalary(data?.salary_sync)) ElMessage.success(t('common.success'))
    await load()
    if (auth.can('contracts', 'update')) await loadSalaries()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(detail || t('common.failed'))
  }
}

async function importPdf() {
  try {
    await pdfFormRef.value?.validate()
    const data = new FormData()
    data.append('employee_id', pdfForm.employee_id)
    data.append('title', pdfForm.title)
    data.append('file', pdfForm.file)
    await api.post('/contracts/import-pdf', data)
    ElMessage.success(t('common.success'))
    pdfDialog.value = false
    await load()
    if (auth.can('contracts', 'update')) await loadSalaries()
  } catch (error) {
    const detail = error.response?.data?.detail
    if (detail) ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail)
  }
}

function displayEndDate(row) {
  return row.end_date === '9999-12-31' ? t('contracts.longTerm') : row.end_date
}

function contractEmployeeName(row) {
  if (employeeNameById.value[row.employee_id]) return employeeNameById.value[row.employee_id]
  if (auth.user?.employee_id === row.employee_id) return auth.user.full_name
  return row.employee_id
}

function salaryEmployeeName(row) {
  return row.employee_name || employeeNameById.value[row.employee_id] || row.employee_id
}

function applyContractQueryFilter() {
  if (route.name !== 'internalContracts') return
  const employeeId = Number(route.query.employee_id || 0)
  if (!employeeId) return
  q.value = employeeNameById.value[employeeId] || String(employeeId)
}

async function openEmployeeContracts(row) {
  await router.push({ name: 'internalContracts', query: { employee_id: row.employee_id } })
  activeTab.value = 'contracts'
  applyContractQueryFilter()
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function openDetail(row) {
  detailRow.value = row
  detailDrawer.value = true
}

function downloadContract(row) {
  if (row.pdf_download_url) window.open(row.pdf_download_url, '_blank')
}

function downloadSalary(row, kind) {
  const suffix = kind === 'annual' ? 'annual-estimate.pdf' : 'payslip.pdf'
  window.open(`/api/contracts/salaries/${row.id}/${suffix}?v=${encodeURIComponent(row.updated_at || Date.now())}`, '_blank')
}

function textOrDash(value) {
  return value || '-'
}

function prettyJson(value) {
  return value ? JSON.stringify(value, null, 2) : '-'
}

function columnLabel(key) {
  const labels = {
    title: t('fields.title'),
    employee: t('fields.employee'),
    contract_type: t('fields.contractType'),
    vendor_company: t('fields.vendorCompany'),
    base_salary: t('fields.baseSalary'),
    allowance_total: t('fields.allowanceTotal'),
    base_unit_price_low: t('fields.baseUnitPriceLow'),
    base_unit_price_high: t('fields.baseUnitPriceHigh'),
    start_date: t('fields.startDate'),
    end_date: t('fields.endDate'),
    duty: t('fields.duty'),
    workplace: t('fields.workplace')
  }
  return labels[key]
}

onMounted(async () => {
  await load()
  if (isSalaryRoute.value && auth.can('contracts', 'update')) await loadSalaries()
})
watch(() => route.name, syncRouteTab)
watch(() => route.query.employee_id, applyContractQueryFilter)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ isSalaryRoute ? t('contracts.salaryManagement') : t('nav.internalContracts') }}</h2>
      <div class="toolbar">
        <el-input v-if="isContractTab" v-model="q" :prefix-icon="Search" :placeholder="t('common.search')" clearable style="width: 240px" />
        <span v-if="activeTab === 'salaries' && selectedSalaries.length" class="muted">{{ selectedSalaries.length }} 件選択中</span>
        <el-button :icon="RefreshCw" @click="refreshCurrent">{{ t('common.refresh') }}</el-button>
        <el-button v-if="isContractTab && auth.user?.role === 'admin'" type="primary" :icon="Plus" @click="openContractCreate">{{ t('contracts.manualCreate') }}</el-button>
        <el-button v-if="isContractTab && auth.can('contracts', 'import')" :icon="FileUp" @click="pdfDialog = true">{{ t('contracts.importPdf') }}</el-button>
        <el-popover v-if="isContractTab" placement="bottom-end" width="240" trigger="click">
          <template #reference>
            <el-button :icon="Columns3">{{ t('common.columns') }}</el-button>
          </template>
          <div class="column-menu">
            <el-checkbox v-for="column in displayColumnOptions" :key="column" v-model="visibleColumns[column]">
              {{ columnLabel(column) }}
            </el-checkbox>
          </div>
        </el-popover>
      </div>
    </div>
    <el-tabs v-model="activeTab" :class="{ 'single-route-tabs': isSalaryRoute }" @tab-change="handleTabChange">
      <el-tab-pane v-if="!isSalaryRoute" :label="t('contracts.contractInfo')" name="contracts">
        <p class="muted">{{ t('contracts.batchNote') }}</p>
        <el-table :data="pagedContracts" height="calc(100vh - 310px)" stripe>
          <el-table-column v-if="visibleColumns.title && !isEmployeeRole" prop="title" :label="t('fields.title')" min-width="180" sortable />
          <el-table-column v-if="visibleColumns.employee && !isEmployeeRole" :label="t('fields.employee')" min-width="140" sortable>
            <template #default="{ row }">{{ contractEmployeeName(row) }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.contract_type" prop="contract_type" :label="t('fields.contractType')" min-width="130" sortable />
          <el-table-column v-if="visibleColumns.vendor_company" prop="vendor_company" :label="t('fields.vendorCompany')" min-width="180" sortable />
          <el-table-column v-if="visibleColumns.base_salary" :label="t('fields.baseSalary')" width="130" sortable>
            <template #default="{ row }">{{ money(row.attributes?.base_salary) }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.allowance_total" :label="t('fields.allowanceTotal')" width="130" sortable>
            <template #default="{ row }">{{ money(row.attributes?.allowance_total) }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.base_unit_price_low" :label="t('fields.baseUnitPriceLow')" width="140">
            <template #default="{ row }">{{ money(row.attributes?.base_unit_price_low) }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.base_unit_price_high" :label="t('fields.baseUnitPriceHigh')" width="140">
            <template #default="{ row }">{{ money(row.attributes?.base_unit_price_high) }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.start_date" prop="start_date" :label="t('fields.startDate')" width="120" sortable />
          <el-table-column v-if="visibleColumns.end_date" :label="t('fields.endDate')" width="130" sortable>
            <template #default="{ row }">{{ displayEndDate(row) }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.duty" :label="t('fields.duty')" min-width="180">
            <template #default="{ row }">{{ row.attributes?.duty || '-' }}</template>
          </el-table-column>
          <el-table-column v-if="visibleColumns.workplace" :label="t('fields.workplace')" min-width="180">
            <template #default="{ row }">{{ row.attributes?.workplace || '-' }}</template>
          </el-table-column>
          <el-table-column fixed="right" :label="t('common.actions')" width="190">
            <template #default="{ row }">
              <el-button text :icon="Eye" @click="openDetail(row)" />
              <el-button v-if="auth.user?.role === 'admin'" text type="primary" :icon="Pencil" @click="openContractEdit(row)" />
              <el-button v-if="row.pdf_download_url" text :icon="Download" @click="downloadContract(row)" />
              <el-button v-if="auth.can('contracts', 'delete')" text type="danger" :icon="Trash2" @click="deleteContract(row)" />
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="contractPager.page" v-model:page-size="contractPager.pageSize" :total="filteredContracts.length" />
      </el-tab-pane>

      <el-tab-pane v-if="isSalaryRoute && auth.can('contracts', 'update')" :label="t('contracts.salaryManagement')" name="salaries">
        <div class="toolbar section-toolbar">
          <el-input v-model="salaryQ" :prefix-icon="Search" :placeholder="t('common.search')" clearable style="width: 240px" />
          <el-date-picker v-model="salaryMonth" type="month" value-format="YYYY-MM" :clearable="false" @change="loadSalaries" />
        </div>
        <el-table :data="pagedSalaries" height="calc(100vh - 365px)" stripe @selection-change="selectedSalaries = $event">
          <el-table-column type="selection" width="46" />
          <el-table-column :label="t('fields.employee')" min-width="160">
            <template #default="{ row }">
              <div class="salary-employee-cell">
                <div>
                  <el-button link :type="row.employee_is_deleted ? 'danger' : 'primary'" :class="{ 'deleted-employee-link': row.employee_is_deleted }" @click="openEmployeeContracts(row)">
                    {{ salaryEmployeeName(row) }}
                  </el-button>
                  <el-tag v-if="row.employee_is_deleted" size="small" type="danger" effect="plain">退職</el-tag>
                </div>
                <small>{{ row.employee_email || `ID: ${row.employee_id}` }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="year_month" :label="t('fields.yearMonth')" width="120" sortable />
          <el-table-column :label="t('fields.hoursRange')" width="130">
            <template #default="{ row }"><el-input v-model="row.hours_range" class="table-text-input" /></template>
          </el-table-column>
          <el-table-column :label="t('fields.monthlyHours')" width="150" sortable>
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.monthly_hours ?? '-' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('fields.baseUnitPriceLow')" width="140">
            <template #default="{ row }">{{ money(row.base_unit_price_low) }}</template>
          </el-table-column>
          <el-table-column :label="t('fields.baseUnitPriceHigh')" width="140">
            <template #default="{ row }">{{ money(row.base_unit_price_high) }}</template>
          </el-table-column>
          <el-table-column :label="t('fields.estimatedSalary')" width="150" sortable>
            <template #default="{ row }">{{ money(row.estimated_salary) }}</template>
          </el-table-column>
          <el-table-column :label="t('fields.reimbursementAmount')" width="140" sortable>
            <template #default="{ row }">{{ money(row.reimbursement_amount) }}</template>
          </el-table-column>
          <el-table-column label="通勤手当" width="130">
            <template #default="{ row }"><el-input-number v-model="row.commuting_allowance" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="その他支給" width="130">
            <template #default="{ row }"><el-input-number v-model="row.other_payment" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="総支給額" width="140" sortable>
            <template #default="{ row }">{{ money(row.gross_payment_total) }}</template>
          </el-table-column>
          <el-table-column label="厚生年金" width="130">
            <template #default="{ row }"><el-input-number v-model="row.pension" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="健康保険" width="130">
            <template #default="{ row }"><el-input-number v-model="row.health_insurance" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="介護保険" width="130">
            <template #default="{ row }"><el-input-number v-model="row.care_insurance" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="雇用保険" width="130">
            <template #default="{ row }"><el-input-number v-model="row.employment_insurance" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="所得税" width="130">
            <template #default="{ row }"><el-input-number v-model="row.income_tax" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column :label="t('fields.residentTax')" width="130">
            <template #default="{ row }"><el-input-number v-model="row.resident_tax" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="その他控除" width="130">
            <template #default="{ row }"><el-input-number v-model="row.other_deduction" class="table-number-input" :min="0" :controls="false" /></template>
          </el-table-column>
          <el-table-column label="控除合計" width="140" sortable>
            <template #default="{ row }">{{ money(row.deduction_total) }}</template>
          </el-table-column>
          <el-table-column :label="t('fields.actualSalary')" width="190" sortable>
            <template #default="{ row }">
              <div :class="{ 'manual-actual': row.actual_salary_manual }">
                <el-input-number v-model="row.actual_salary" class="table-number-input" :min="0" :controls="false" />
                <small v-if="row.actual_salary_manual">手動調整あり</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('fields.locked')" width="110">
            <template #default="{ row }"><el-switch v-model="row.locked" /></template>
          </el-table-column>
          <el-table-column :label="t('fields.note')" min-width="220">
            <template #default="{ row }"><el-input v-model="row.note" /></template>
          </el-table-column>
          <el-table-column fixed="right" :label="t('common.actions')" width="150">
            <template #default="{ row }">
              <el-button text type="primary" :icon="Save" @click="updateSalary(row)" />
              <el-button text :icon="Download" @click="downloadSalary(row, 'salary')" />
              <el-button text :icon="Download" @click="downloadSalary(row, 'annual')" />
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="salaryPager.page" v-model:page-size="salaryPager.pageSize" :total="filteredSalaries.length" />
        <div class="salary-summary-bar">
          <div class="summary-total">
            <span>{{ t('fields.estimatedSalary') }}</span>
            <strong>{{ money(salaryTotals.estimated) }}</strong>
          </div>
          <div class="summary-total">
            <span>{{ t('fields.actualSalary') }}</span>
            <strong>{{ money(salaryTotals.actual) }}</strong>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialog" :title="editingContractId ? t('contracts.manualEdit') : t('contracts.manualCreate')" width="760px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item :label="t('fields.employee')" prop="employee_id">
          <el-select v-model="form.employee_id" filterable>
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.full_name" :value="employee.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.title')" prop="title"><el-input v-model="form.title" /></el-form-item>
        <el-form-item :label="t('fields.contractType')" prop="contract_type">
          <el-select v-model="form.contract_type">
            <el-option v-for="option in contractTypeOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.vendorCompany')" prop="vendor_company">
          <el-select v-model="form.vendor_company">
            <el-option v-for="option in companyOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.startDate')"><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item :label="t('fields.endDate')"><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item :label="t('fields.baseSalary')"><el-input-number v-model="form.base_salary" :min="0" :controls="false" /></el-form-item>
        <el-form-item :label="t('fields.hoursRange')" prop="hours_range"><el-input v-model="form.hours_range" placeholder="140-180" /></el-form-item>
        <el-form-item :label="t('fields.workplace')"><el-input v-model="form.workplace" /></el-form-item>
        <el-form-item :label="t('fields.duty')"><el-input v-model="form.duty" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.allowances')">
          <div class="allowance-editor">
            <div v-for="(item, index) in form.allowances" :key="index" class="allowance-row">
              <el-input v-model="item.name" :placeholder="t('fields.allowances')" />
              <el-input-number v-model="item.amount" :min="0" :controls="false" />
              <el-button :icon="Trash2" circle @click="removeAllowance(index)" />
            </div>
            <el-button :icon="Plus" @click="addAllowance">{{ t('contracts.addAllowance') }}</el-button>
          </div>
        </el-form-item>
        <el-form-item class="span-2" :label="t('fields.parsedText')"><el-input v-model="form.parsed_text" type="textarea" :rows="5" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="save">{{ t('common.save') }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="pdfDialog" :title="t('contracts.importPdf')" width="560px">
      <el-form ref="pdfFormRef" :model="pdfForm" :rules="pdfRules" label-position="top">
        <el-form-item :label="t('fields.employee')" prop="employee_id">
          <el-select v-model="pdfForm.employee_id" filterable>
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.full_name" :value="employee.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.title')" prop="title"><el-input v-model="pdfForm.title" /></el-form-item>
        <el-form-item :label="t('common.upload')" prop="file">
          <el-upload :auto-upload="false" :limit="1" accept=".pdf" @change="(file) => { pdfForm.file = file.raw; pdfFormRef?.clearValidate('file') }">
            <el-button :icon="FileUp">{{ t('common.upload') }}</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="pdfDialog = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="importPdf">{{ t('common.import') }}</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailDrawer" :title="t('contracts.detailTitle')" size="46%">
      <div v-if="detailRow" class="detail-sections">
        <section class="detail-section">
          <h3>{{ t('common.detail') }}</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('fields.title')">{{ textOrDash(detailRow.title) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.employee')">{{ contractEmployeeName(detailRow) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.contractType')">{{ textOrDash(detailRow.contract_type) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.vendorCompany')">{{ textOrDash(detailRow.vendor_company) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.startDate')">{{ textOrDash(detailRow.start_date) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.endDate')">{{ displayEndDate(detailRow) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.pdfFile')">{{ textOrDash(detailRow.pdf_filename) }}</el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="detail-section">
          <h3>{{ t('contracts.salaryDetail') }}</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('fields.baseSalary')">{{ money(detailRow.attributes?.base_salary) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.allowanceTotal')">{{ money(detailRow.attributes?.allowance_total) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.salaryTotalMonthly')">{{ money(detailRow.attributes?.salary_total_monthly) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.baseUnitPriceLow')">{{ money(detailRow.attributes?.base_unit_price_low) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.baseUnitPriceHigh')">{{ money(detailRow.attributes?.base_unit_price_high) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.workplace')">{{ textOrDash(detailRow.attributes?.workplace) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.duty')" :span="2">{{ textOrDash(detailRow.attributes?.duty) }}</el-descriptions-item>
          </el-descriptions>

          <el-table v-if="detailRow.attributes?.allowances?.length" :data="detailRow.attributes.allowances" size="small" class="detail-table">
            <el-table-column prop="name" :label="t('fields.allowances')" />
            <el-table-column :label="t('fields.amount')" width="160">
              <template #default="{ row }">{{ money(row.amount) }}</template>
            </el-table-column>
          </el-table>
        </section>

        <section class="detail-section">
          <h3>{{ t('fields.parsedText') }}</h3>
          <pre class="detail-raw">{{ textOrDash(detailRow.parsed_text) }}</pre>
        </section>

        <section class="detail-section">
          <h3>{{ t('fields.attributes') }}</h3>
          <pre class="detail-json">{{ prettyJson(detailRow.attributes) }}</pre>
        </section>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.manual-actual {
  color: #d92d20;
}

.manual-actual :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f04438 inset;
}

.manual-actual small {
  display: block;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.4;
  margin-top: 2px;
}

.deleted-employee-link {
  color: #d92d20;
  font-weight: 700;
}

.single-route-tabs :deep(.el-tabs__header) {
  display: none;
}

.allowance-editor {
  width: 100%;
  display: grid;
  gap: 8px;
}

.allowance-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 180px 36px;
  gap: 8px;
  align-items: center;
}

.salary-employee-cell {
  display: grid;
  gap: 2px;
  line-height: 1.25;
}

.salary-employee-cell small {
  color: var(--el-text-color-secondary);
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .allowance-row {
    grid-template-columns: 1fr;
  }
}
</style>
