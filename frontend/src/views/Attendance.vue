<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CheckCircle2, RefreshCw, Save } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()

const summary = ref({ rows: [], settings: null })
const requests = ref([])
const calendarRows = ref([])
const balances = ref([])
const loading = ref(false)
const month = ref(currentMonth())
const fiscalYear = ref(new Date().getFullYear())
const formRef = ref(null)
const settingsFormRef = ref(null)
const balanceFormRef = ref(null)
const section = computed(() => route.path.split('/').pop() || 'summary')
const canManage = computed(() => ['admin', 'soumu', 'hr'].includes(auth.user?.role))
const canAdmin = computed(() => auth.user?.role === 'admin')
const employees = computed(() => summary.value.rows.map((row) => ({ id: row.employee_id, name: row.employee_name })))

const requestTypes = [
  { value: 'paid_leave', label: '有給休暇' },
  { value: 'absence', label: '欠勤' },
  { value: 'morning_off', label: '午前休' },
  { value: 'afternoon_off', label: '午後休' },
  { value: 'special_leave', label: '特別休暇' },
  { value: 'holiday_work', label: '休日出勤' },
  { value: 'adjustment', label: '手動調整' }
]

const requestForm = reactive({
  employee_id: null,
  work_date: today(),
  request_type: 'paid_leave',
  requested_hours: null,
  reason: ''
})

const settingsForm = reactive({
  default_start_time: '09:00',
  default_end_time: '18:00',
  break_minutes: 60,
  hour_step: 0.5,
  default_paid_leave_days: 10,
  paid_leave_counts_as_work: false,
  company_holidays_text: '[]'
})

const balanceForm = reactive({
  employee_id: null,
  fiscal_year: fiscalYear.value,
  granted_days: 10,
  adjustment_days: 0,
  note: ''
})

const rules = computed(() => ({
  employee_id: [{ required: canManage.value, message: t('validation.required'), trigger: 'change' }],
  work_date: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  request_type: [{ required: true, message: t('validation.required'), trigger: 'change' }]
}))

const balanceRules = computed(() => ({
  employee_id: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  fiscal_year: [{ required: true, message: t('validation.required'), trigger: 'change' }]
}))

const { pager: summaryPager, pageRows: pagedSummary } = usePagination(computed(() => summary.value.rows || []))
const { pager: requestPager, pageRows: pagedRequests } = usePagination(requests)
const { pager: calendarPager, pageRows: pagedCalendar } = usePagination(calendarRows)
const { pager: balancePager, pageRows: pagedBalances } = usePagination(balances)

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function moneyOrHours(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function requestTypeLabel(value) {
  return requestTypes.find((item) => item.value === value)?.label || value
}

function statusType(value) {
  return value === 'approved' ? 'success' : value === 'rejected' ? 'danger' : 'warning'
}

function applySettings(value) {
  if (!value) return
  Object.assign(settingsForm, {
    default_start_time: value.default_start_time || '09:00',
    default_end_time: value.default_end_time || '18:00',
    break_minutes: value.break_minutes ?? 60,
    hour_step: value.hour_step ?? 0.5,
    default_paid_leave_days: value.default_paid_leave_days ?? 10,
    paid_leave_counts_as_work: Boolean(value.paid_leave_counts_as_work),
    company_holidays_text: JSON.stringify(value.company_holidays || [], null, 2)
  })
}

function showApiError(error) {
  const detail = error.response?.data?.detail
  ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
}

async function loadSummary() {
  summary.value = (await api.get('/attendance/summary', { params: { year_month: month.value } })).data
  applySettings(summary.value.settings)
}

async function loadRequests(statusFilter = null) {
  const params = { year_month: month.value }
  if (statusFilter) params.status_filter = statusFilter
  requests.value = (await api.get('/attendance/requests', { params })).data
}

async function loadCalendar() {
  calendarRows.value = (await api.get('/attendance/calendar', { params: { year_month: month.value } })).data
}

async function loadBalances() {
  balances.value = (await api.get('/attendance/leave-balances', { params: { fiscal_year: fiscalYear.value } })).data
}

async function load() {
  loading.value = true
  try {
    await loadSummary()
    if (section.value === 'requests') await loadRequests()
    if (section.value === 'settings') {
      await Promise.all([loadCalendar(), loadBalances()])
    }
  } finally {
    loading.value = false
  }
}

async function submitRequest() {
  try {
    await formRef.value?.validate()
    const payload = {
      employee_id: canManage.value ? requestForm.employee_id : null,
      work_date: requestForm.work_date,
      request_type: requestForm.request_type,
      requested_hours: requestForm.requested_hours,
      reason: requestForm.reason || null
    }
    await api.post('/attendance/requests', payload)
    ElMessage.success(t('common.success'))
    Object.assign(requestForm, { work_date: today(), request_type: 'paid_leave', requested_hours: null, reason: '' })
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function importCalendar() {
  await api.post('/attendance/calendar/import', null, { params: { year: Number(month.value.slice(0, 4)) } })
  ElMessage.success(t('common.success'))
  await load()
}

async function saveCalendarDay(row) {
  try {
    await api.put(`/attendance/calendar/${row.work_date}`, {
      is_workday: Boolean(row.is_workday),
      holiday_name: row.holiday_name || null,
      note: row.note || null
    })
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function saveSettings() {
  try {
    await settingsFormRef.value?.validate()
    let companyHolidays = []
    try {
      companyHolidays = JSON.parse(settingsForm.company_holidays_text || '[]')
    } catch {
      ElMessage.error('会社休日 JSON を確認してください')
      return
    }
    const { data } = await api.put('/attendance/settings', {
      default_start_time: settingsForm.default_start_time,
      default_end_time: settingsForm.default_end_time,
      break_minutes: settingsForm.break_minutes,
      hour_step: settingsForm.hour_step,
      default_paid_leave_days: settingsForm.default_paid_leave_days,
      paid_leave_counts_as_work: settingsForm.paid_leave_counts_as_work,
      leave_policies: null,
      company_holidays: companyHolidays
    })
    applySettings(data)
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function saveBalance() {
  try {
    await balanceFormRef.value?.validate()
    await api.put('/attendance/leave-balances', { ...balanceForm, fiscal_year: Number(balanceForm.fiscal_year) })
    ElMessage.success(t('common.success'))
    await loadBalances()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

function editBalance(row) {
  Object.assign(balanceForm, {
    employee_id: row.employee_id,
    fiscal_year: row.fiscal_year,
    granted_days: row.granted_days,
    adjustment_days: row.adjustment_days,
    note: row.note || ''
  })
}

onMounted(load)
watch(() => route.path, load)
watch(month, load)
watch(fiscalYear, () => {
  balanceForm.fiscal_year = fiscalYear.value
  if (section.value === 'settings') loadBalances()
})
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <h2>{{ t('nav.attendance') }}</h2>
      <div class="toolbar">
        <el-date-picker v-model="month" type="month" value-format="YYYY-MM" :clearable="false" />
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
      </div>
    </div>

    <section v-if="section === 'summary'" class="settings-panel">
      <div class="toolbar section-toolbar">
        <el-tag>09:00 - 18:00 / 休憩 {{ summary.settings?.break_minutes ?? 60 }} 分</el-tag>
        <el-tag :type="summary.settings?.paid_leave_counts_as_work ? 'success' : 'warning'">
          有給: {{ summary.settings?.paid_leave_counts_as_work ? '給与工数に含める' : '給与工数に含めない' }}
        </el-tag>
      </div>
      <el-table :data="pagedSummary" height="calc(100vh - 310px)" stripe>
        <el-table-column prop="employee_name" label="社員" min-width="160" sortable />
        <el-table-column prop="scheduled_workdays" label="所定日数" width="110" sortable />
        <el-table-column prop="scheduled_hours" label="所定時間" width="120" sortable />
        <el-table-column prop="actual_work_hours" label="給与反映工数" width="140" sortable>
          <template #default="{ row }"><strong>{{ moneyOrHours(row.actual_work_hours) }}</strong></template>
        </el-table-column>
        <el-table-column prop="paid_leave_used_days" label="有給使用" width="120" sortable />
        <el-table-column prop="paid_leave_remaining_days" label="有給残" width="120" sortable />
        <el-table-column prop="pending_requests" label="未承認" width="110" sortable />
        <el-table-column label="給与ロック" width="120">
          <template #default="{ row }"><el-tag :type="row.salary_locked ? 'danger' : 'success'">{{ row.salary_locked ? 'ロック済' : '自動反映' }}</el-tag></template>
        </el-table-column>
      </el-table>
      <TablePager v-model:page="summaryPager.page" v-model:page-size="summaryPager.pageSize" :total="summary.rows?.length || 0" />
    </section>

    <section v-if="section === 'requests'">
      <section class="settings-panel">
        <el-form ref="formRef" :model="requestForm" :rules="rules" label-position="top" class="form-grid">
          <el-form-item v-if="canManage" label="社員" prop="employee_id">
            <el-select v-model="requestForm.employee_id" filterable>
              <el-option v-for="employee in employees" :key="employee.id" :label="employee.name" :value="employee.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="対象日" prop="work_date"><el-date-picker v-model="requestForm.work_date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="申請区分" prop="request_type">
            <el-select v-model="requestForm.request_type">
              <el-option v-for="item in requestTypes" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="調整時間"><el-input-number v-model="requestForm.requested_hours" :min="0" :step="0.5" :precision="1" :controls="false" /></el-form-item>
          <el-form-item label="理由" class="span-2"><el-input v-model="requestForm.reason" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <div class="toolbar">
          <el-button type="primary" :icon="CheckCircle2" @click="submitRequest">申請</el-button>
        </div>
      </section>

      <el-table :data="pagedRequests" height="calc(100vh - 540px)" stripe>
        <el-table-column prop="employee_name" label="社員" min-width="150" sortable />
        <el-table-column prop="work_date" label="対象日" width="120" sortable />
        <el-table-column label="区分" width="130"><template #default="{ row }">{{ requestTypeLabel(row.request_type) }}</template></el-table-column>
        <el-table-column prop="requested_hours" label="申請時間" width="110" sortable />
        <el-table-column prop="calculated_hours" label="反映時間" width="110" sortable />
        <el-table-column prop="status" label="状態" width="120">
          <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="reason" label="理由" min-width="180" show-overflow-tooltip />
      </el-table>
      <TablePager v-model:page="requestPager.page" v-model:page-size="requestPager.pageSize" :total="requests.length" />
    </section>

    <section v-if="section === 'settings'">
      <section class="settings-panel">
        <div class="toolbar section-toolbar">
          <el-button :icon="RefreshCw" @click="importCalendar">日本祝日カレンダー取込</el-button>
        </div>
        <el-form ref="settingsFormRef" :model="settingsForm" label-position="top" class="form-grid">
          <el-form-item label="標準開始"><el-time-picker v-model="settingsForm.default_start_time" value-format="HH:mm" format="HH:mm" :clearable="false" :disabled="!canAdmin" /></el-form-item>
          <el-form-item label="標準終了"><el-time-picker v-model="settingsForm.default_end_time" value-format="HH:mm" format="HH:mm" :clearable="false" :disabled="!canAdmin" /></el-form-item>
          <el-form-item label="休憩分"><el-input-number v-model="settingsForm.break_minutes" :min="0" :disabled="!canAdmin" /></el-form-item>
          <el-form-item label="丸め単位"><el-input-number v-model="settingsForm.hour_step" :min="0.25" :max="1" :step="0.25" :disabled="!canAdmin" /></el-form-item>
          <el-form-item label="初期有給日数"><el-input-number v-model="settingsForm.default_paid_leave_days" :min="0" :step="0.5" :disabled="!canAdmin" /></el-form-item>
          <el-form-item label="有給を給与工数に含める"><el-switch v-model="settingsForm.paid_leave_counts_as_work" :disabled="!canAdmin" /></el-form-item>
          <el-form-item label="会社休日 JSON" class="span-2">
            <el-input v-model="settingsForm.company_holidays_text" type="textarea" :rows="3" :disabled="!canAdmin" placeholder='[{"date":"2026-12-29","name":"年末休暇"}]' />
          </el-form-item>
        </el-form>
        <div v-if="canAdmin" class="toolbar">
          <el-button type="primary" :icon="Save" @click="saveSettings">{{ t('common.save') }}</el-button>
        </div>
      </section>

      <section class="below-panel">
        <h3>年休残数調整</h3>
        <el-form ref="balanceFormRef" :model="balanceForm" :rules="balanceRules" label-position="top" class="form-grid">
          <el-form-item label="社員" prop="employee_id">
            <el-select v-model="balanceForm.employee_id" filterable>
              <el-option v-for="employee in employees" :key="employee.id" :label="employee.name" :value="employee.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="年度" prop="fiscal_year"><el-input-number v-model="balanceForm.fiscal_year" :min="2000" /></el-form-item>
          <el-form-item label="付与日数"><el-input-number v-model="balanceForm.granted_days" :min="0" :step="0.5" /></el-form-item>
          <el-form-item label="調整日数"><el-input-number v-model="balanceForm.adjustment_days" :step="0.5" /></el-form-item>
          <el-form-item label="備考" class="span-2"><el-input v-model="balanceForm.note" /></el-form-item>
        </el-form>
        <div class="toolbar">
          <el-date-picker v-model="fiscalYear" type="year" value-format="YYYY" :clearable="false" />
          <el-button v-if="canManage" type="primary" :icon="Save" @click="saveBalance">{{ t('common.save') }}</el-button>
        </div>
        <el-table :data="pagedBalances" height="260" stripe>
          <el-table-column prop="employee_name" label="社員" min-width="160" sortable />
          <el-table-column prop="granted_days" label="付与" width="100" sortable />
          <el-table-column prop="adjustment_days" label="調整" width="100" sortable />
          <el-table-column prop="used_days" label="使用" width="100" sortable />
          <el-table-column prop="remaining_days" label="残" width="100" sortable />
          <el-table-column prop="note" label="備考" min-width="180" show-overflow-tooltip />
          <el-table-column v-if="canManage" fixed="right" :label="t('common.actions')" width="100">
            <template #default="{ row }"><el-button text @click="editBalance(row)">{{ t('common.edit') }}</el-button></template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="balancePager.page" v-model:page-size="balancePager.pageSize" :total="balances.length" />
      </section>

      <section class="below-panel">
        <h3>勤務カレンダー</h3>
        <el-table :data="pagedCalendar" height="360" stripe>
          <el-table-column prop="work_date" label="日付" width="120" sortable />
          <el-table-column label="勤務日" width="110">
            <template #default="{ row }"><el-switch v-model="row.is_workday" :disabled="!canAdmin" /></template>
          </el-table-column>
          <el-table-column label="休日名" min-width="180"><template #default="{ row }"><el-input v-model="row.holiday_name" :disabled="!canAdmin" /></template></el-table-column>
          <el-table-column label="備考" min-width="180"><template #default="{ row }"><el-input v-model="row.note" :disabled="!canAdmin" /></template></el-table-column>
          <el-table-column prop="source" label="source" width="110" sortable />
          <el-table-column v-if="canAdmin" fixed="right" :label="t('common.actions')" width="90">
            <template #default="{ row }"><el-button text type="primary" :icon="Save" @click="saveCalendarDay(row)" /></template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="calendarPager.page" v-model:page-size="calendarPager.pageSize" :total="calendarRows.length" />
      </section>
    </section>
  </div>
</template>
