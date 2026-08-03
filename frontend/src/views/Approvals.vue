<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Download, RefreshCw } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const routeTabs = {
  approvalContracts: 'contract',
  approvalReimbursements: 'reimbursement',
  approvalAttendance: 'attendance',
  approvalOffboarding: 'offboarding'
}
const activeTab = ref(routeTabs[route.name] || 'contract')
const rows = ref([])
const attendanceRows = ref([])
const approvalMonth = ref(currentMonth())
const displayRows = computed(() => activeTab.value === 'attendance' ? attendanceRows.value : rows.value)
const pendingCount = computed(() => displayRows.value.filter((item) => item.status === 'pending').length)
const canSeeReimbursement = computed(() => ['admin', 'hr'].includes(auth.user?.role))
const canSeeAttendance = computed(() => ['admin', 'hr'].includes(auth.user?.role))
const canSeeOffboarding = computed(() => ['admin', 'hr'].includes(auth.user?.role))
const pageTitle = computed(() => {
  if (activeTab.value === 'reimbursement') return t('approvals.reimbursementApprovals')
  if (activeTab.value === 'attendance') return t('approvals.attendanceApprovals')
  if (activeTab.value === 'offboarding') return '退職承認'
  return t('approvals.contractApprovals')
})
const { pager, pageRows } = usePagination(displayRows)

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function workflowType() {
  if (activeTab.value === 'offboarding') return 'employee_offboarding'
  return activeTab.value === 'reimbursement' ? 'reimbursement' : null
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function showApiError(error) {
  const detail = error.response?.data?.detail
  ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
}

async function load() {
  if (activeTab.value === 'attendance') {
    const { data } = await api.get('/attendance/requests', { params: { year_month: approvalMonth.value } })
    attendanceRows.value = data
    return
  }
  const type = workflowType()
  const { data } = await api.get('/approvals', { params: type ? { workflow_type: type } : {} })
  rows.value = activeTab.value === 'reimbursement'
    ? data
    : activeTab.value === 'offboarding'
      ? data
      : data.filter((row) => !['reimbursement', 'employee_offboarding'].includes(row.workflow_type))
}

async function decide(row, status) {
  try {
    await api.post(`/approvals/${row.id}/decision`, { status })
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function withdraw(row) {
  try {
    await api.post(`/approvals/${row.id}/withdraw`)
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function decideAttendance(row, status) {
  try {
    await api.post(`/attendance/requests/${row.id}/decision`, { status })
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

function download(url) {
  if (url) window.open(url, '_blank')
}

function documentTypeLabel(value) {
  return value ? t(`external.documentTypes.${value}`) : '-'
}

function requestTypeLabel(value) {
  const labels = {
    paid_leave: '有給休暇',
    absence: '欠勤',
    morning_off: '午前休',
    afternoon_off: '午後休',
    special_leave: '特別休暇',
    holiday_work: '休日出勤',
    adjustment: '手動調整'
  }
  return labels[value] || value
}

function handleTabChange() {
  pager.page = 1
  load()
}

function syncTabFromRoute() {
  activeTab.value = routeTabs[route.name] || 'contract'
  handleTabChange()
}

onMounted(load)
watch(() => route.name, syncTabFromRoute)
watch(approvalMonth, () => {
  if (activeTab.value === 'attendance') load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ pageTitle }}</h2>
      <div class="toolbar">
        <span class="muted">{{ t('external.pendingApprovals') }}: {{ pendingCount }}</span>
        <el-date-picker v-if="activeTab === 'attendance'" v-model="approvalMonth" type="month" value-format="YYYY-MM" :clearable="false" />
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="single-route-tabs" @tab-change="handleTabChange">
      <el-tab-pane v-if="activeTab === 'contract'" :label="t('approvals.contractApprovals')" name="contract">
        <el-table :data="pageRows" height="calc(100vh - 320px)" stripe>
          <el-table-column type="selection" width="46" />
          <el-table-column prop="title" :label="t('fields.title')" min-width="220" />
          <el-table-column :label="t('external.documentType')" width="150"><template #default="{ row }">{{ documentTypeLabel(row.entity?.document_type) }}</template></el-table-column>
          <el-table-column :label="t('external.companyName')" min-width="180"><template #default="{ row }">{{ row.entity?.partner_name || '-' }}</template></el-table-column>
          <el-table-column :label="t('external.documentNo')" min-width="180"><template #default="{ row }">{{ row.entity?.document_no || '-' }}</template></el-table-column>
          <el-table-column :label="t('external.targetMonth')" width="120"><template #default="{ row }">{{ row.entity?.target_month || '-' }}</template></el-table-column>
          <el-table-column :label="t('external.total')" width="140"><template #default="{ row }">{{ money(row.entity?.total) }}</template></el-table-column>
          <el-table-column prop="status" :label="t('external.approvalStatus')" width="130" />
          <el-table-column prop="approver_name" label="承認者" width="130" />
          <el-table-column fixed="right" :label="t('common.actions')" width="260">
            <template #default="{ row }">
              <el-button v-if="row.entity?.download_url" text :icon="Download" @click="download(row.entity.download_url)" />
              <el-button v-if="row.status === 'pending'" text type="success" @click="decide(row, 'approved')">{{ t('external.approve') }}</el-button>
              <el-button v-if="row.status === 'pending'" text type="danger" @click="decide(row, 'rejected')">{{ t('external.reject') }}</el-button>
              <el-button v-if="row.status === 'approved'" text type="warning" @click="withdraw(row)">{{ t('external.withdraw') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="displayRows.length" />
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'reimbursement' && canSeeReimbursement" :label="t('approvals.reimbursementApprovals')" name="reimbursement">
        <el-table :data="pageRows" height="calc(100vh - 320px)" stripe>
          <el-table-column type="selection" width="46" />
          <el-table-column prop="title" :label="t('fields.title')" min-width="220" />
          <el-table-column :label="t('fields.employee')" min-width="150"><template #default="{ row }">{{ row.entity?.employee_name || '-' }}</template></el-table-column>
          <el-table-column :label="t('reimbursements.expenseType')" width="130"><template #default="{ row }">{{ row.entity?.expense_type || '-' }}</template></el-table-column>
          <el-table-column :label="t('reimbursements.period')" width="160">
            <template #default="{ row }">{{ row.entity?.period_start_month || '-' }} - {{ row.entity?.period_end_month || '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('reimbursements.payMonth')" width="130"><template #default="{ row }">{{ row.entity?.pay_month || '-' }}</template></el-table-column>
          <el-table-column :label="t('fields.amount')" width="140"><template #default="{ row }">{{ money(row.entity?.total) }}</template></el-table-column>
          <el-table-column :label="t('reimbursements.files')" min-width="180">
            <template #default="{ row }">
              <el-button v-for="file in row.entity?.files || []" :key="file.download_url" text type="primary" :icon="Download" @click="download(file.download_url)">
                {{ file.name }}
              </el-button>
              <span v-if="!(row.entity?.files || []).length">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" :label="t('external.approvalStatus')" width="130" />
          <el-table-column prop="approver_name" label="承認者" width="130" />
          <el-table-column fixed="right" :label="t('common.actions')" width="260">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" text type="success" @click="decide(row, 'approved')">{{ t('external.approve') }}</el-button>
              <el-button v-if="row.status === 'pending'" text type="danger" @click="decide(row, 'rejected')">{{ t('external.reject') }}</el-button>
              <el-button v-if="row.status === 'approved'" text type="warning" @click="withdraw(row)">{{ t('external.withdraw') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="displayRows.length" />
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'attendance' && canSeeAttendance" :label="t('approvals.attendanceApprovals')" name="attendance">
        <el-table :data="pageRows" height="calc(100vh - 320px)" stripe>
          <el-table-column type="selection" width="46" />
          <el-table-column prop="employee_name" :label="t('fields.employee')" min-width="150" sortable />
          <el-table-column prop="work_date" label="対象日" width="120" sortable />
          <el-table-column label="区分" width="130">
            <template #default="{ row }">{{ requestTypeLabel(row.request_type) }}</template>
          </el-table-column>
          <el-table-column prop="requested_hours" label="申請時間" width="110" sortable />
          <el-table-column prop="calculated_hours" label="反映時間" width="110" sortable />
          <el-table-column prop="reason" label="理由" min-width="220" show-overflow-tooltip />
          <el-table-column prop="status" :label="t('external.approvalStatus')" width="130" />
          <el-table-column prop="approver_name" label="承認者" width="130" />
          <el-table-column fixed="right" :label="t('common.actions')" width="250">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" text type="success" @click="decideAttendance(row, 'approved')">{{ t('external.approve') }}</el-button>
              <el-button v-if="row.status === 'pending'" text type="danger" @click="decideAttendance(row, 'rejected')">{{ t('external.reject') }}</el-button>
              <el-button v-if="row.status === 'approved'" text type="warning" @click="decideAttendance(row, 'pending')">{{ t('external.withdraw') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="displayRows.length" />
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'offboarding' && canSeeOffboarding" label="退職承認" name="offboarding">
        <el-table :data="pageRows" height="calc(100vh - 320px)" stripe>
          <el-table-column type="selection" width="46" />
          <el-table-column prop="title" label="申請" min-width="180" />
          <el-table-column label="氏名" min-width="140"><template #default="{ row }">{{ row.entity?.full_name || '-' }}</template></el-table-column>
          <el-table-column label="退職日" width="120"><template #default="{ row }">{{ row.entity?.resignation_date || '-' }}</template></el-table-column>
          <el-table-column label="最終給与月" width="130"><template #default="{ row }">{{ row.entity?.final_salary_month || '-' }}</template></el-table-column>
          <el-table-column label="最終月工数" width="130"><template #default="{ row }">{{ row.entity?.final_salary_hours ?? '-' }}</template></el-table-column>
          <el-table-column label="最終給与上書き" width="150"><template #default="{ row }">{{ money(row.entity?.final_salary_amount) }}</template></el-table-column>
          <el-table-column label="理由" min-width="180"><template #default="{ row }">{{ row.entity?.resignation_reason || '-' }}</template></el-table-column>
          <el-table-column prop="status" :label="t('external.approvalStatus')" width="130" />
          <el-table-column prop="approver_name" label="承認者" width="130" />
          <el-table-column fixed="right" :label="t('common.actions')" width="260">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" text type="success" @click="decide(row, 'approved')">{{ t('external.approve') }}</el-button>
              <el-button v-if="row.status === 'pending'" text type="danger" @click="decide(row, 'rejected')">{{ t('external.reject') }}</el-button>
              <el-button v-if="row.status === 'approved'" text type="warning" @click="withdraw(row)">{{ t('external.withdraw') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="displayRows.length" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.single-route-tabs :deep(.el-tabs__header) {
  display: none;
}
</style>
