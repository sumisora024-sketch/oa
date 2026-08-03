<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RefreshCw, Save } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const defaultRoles = ['admin', 'hr', 'pm', 'employee', 'partner']
const roles = ref(defaultRoles)
const permissions = ref({})
const activeRole = ref('hr')
const selectedKeys = ref([])

const roleLabels = {
  admin: 'Admin',
  hr: 'HR',
  pm: 'PM / 営業',
  employee: '一般社員',
  partner: 'Partner'
}

const groups = computed(() => [
  {
    title: t('nav.employees'),
    items: [
      { key: 'employees.internal', label: t('nav.internalEmployees') },
      { key: 'employees.external', label: t('nav.externalEmployees') },
      { key: 'employees.offboarding', label: '退職' }
    ]
  },
  {
    title: t('nav.contracts'),
    items: [
      { key: 'contracts.internal', label: t('nav.internalContracts') },
      { key: 'contracts.external.new', label: t('nav.externalContractsNew') },
      { key: 'contracts.external.partners', label: t('nav.externalPartners') }
    ]
  },
  {
    title: t('nav.documentManagement'),
    items: [
      { key: 'documents.purchase_orders', label: t('nav.purchaseOrders') },
      { key: 'documents.quotations', label: t('nav.quotations') },
      { key: 'documents.invoices', label: t('nav.invoices') },
      { key: 'documents.history', label: t('nav.documentHistory') },
      { key: 'documents.library', label: t('nav.documentLibrary') }
    ]
  },
  {
    title: t('nav.approvals'),
    items: [
      { key: 'approvals.contracts', label: t('nav.contractApprovals') },
      { key: 'approvals.reimbursements', label: t('nav.reimbursementApprovals') },
      { key: 'approvals.attendance', label: t('nav.attendanceApprovals') },
      { key: 'approvals.offboarding', label: '退職承認' }
    ]
  },
  {
    title: t('nav.expenseSettlement'),
    items: [
      { key: 'reimbursements.claims', label: t('nav.reimbursementClaims') },
      { key: 'reimbursements.monthly_settlement', label: t('nav.monthlySettlement') }
    ]
  },
  {
    title: t('nav.subcontracting'),
    items: [
      { key: 'subcontracting.notice', label: t('nav.subcontractingNotice') },
      { key: 'subcontracting.quotations', label: t('nav.subcontractingQuotations') },
      { key: 'subcontracting.invoices', label: t('nav.subcontractingInvoices') },
      { key: 'subcontracting.personnel', label: t('nav.subcontractingPersonnel') }
    ]
  },
  {
    title: t('nav.attendance'),
    items: [
      { key: 'attendance.summary', label: t('nav.attendanceSummary') },
      { key: 'attendance.requests', label: t('nav.attendanceRequests') },
      { key: 'attendance.settings', label: t('nav.attendanceSettings') }
    ]
  },
  {
    title: t('nav.settings'),
    items: [
      { key: 'home', label: t('nav.home') },
      { key: 'projects', label: t('nav.projects') },
      { key: 'settings.mail', label: t('nav.mailSettings') },
      { key: 'settings.permissions', label: t('nav.permissionManagement'), disabled: true }
    ]
  }
])

const editableRoles = computed(() => roles.value.filter((role) => role !== 'admin'))

function syncSelected() {
  selectedKeys.value = [...(permissions.value[activeRole.value] || [])]
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/ui-permissions')
    roles.value = data.roles?.length ? data.roles : defaultRoles
    permissions.value = data.permissions || {}
    if (!editableRoles.value.includes(activeRole.value)) {
      activeRole.value = editableRoles.value[0] || 'hr'
    }
    syncSelected()
  } catch (error) {
    roles.value = defaultRoles
    if (!editableRoles.value.includes(activeRole.value)) {
      activeRole.value = editableRoles.value[0] || 'hr'
    }
    syncSelected()
    const detail = error.response?.data?.detail
    ElMessage.error(detail || t('common.failed'))
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/ui-permissions/${activeRole.value}`, { route_keys: selectedKeys.value })
    permissions.value = data.permissions || {}
    syncSelected()
    await auth.loadHomepage()
    ElMessage.success(t('common.success'))
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(detail || t('common.failed'))
  } finally {
    saving.value = false
  }
}

watch(activeRole, syncSelected)
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>{{ t('nav.permissionManagement') }}</h2>
        <p class="muted">{{ t('permissions.hint') }}</p>
      </div>
      <div class="toolbar">
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
        <el-button type="primary" :icon="Save" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </div>
    </div>

    <section class="settings-panel permission-panel" v-loading="loading">
      <el-form label-position="top">
        <el-form-item :label="t('permissions.role')">
          <el-select v-model="activeRole" style="width: 240px">
            <el-option v-for="role in editableRoles" :key="role" :label="roleLabels[role] || role" :value="role" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-checkbox-group v-model="selectedKeys" class="permission-groups">
        <section v-for="group in groups" :key="group.title" class="permission-group">
          <h3>{{ group.title }}</h3>
          <div class="permission-grid">
            <el-checkbox
              v-for="item in group.items"
              :key="item.key"
              :label="item.key"
              :disabled="item.disabled"
              border
            >
              {{ item.label }}
            </el-checkbox>
          </div>
        </section>
      </el-checkbox-group>
    </section>
  </div>
</template>

<style scoped>
.permission-panel {
  max-width: 1040px;
}

.permission-groups {
  display: grid;
  gap: 16px;
}

.permission-group {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
}

.permission-group h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.permission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
}
</style>
