<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { Briefcase, ClipboardCheck, Clock3, FileText, HandCoins, Handshake, Home, KeyRound, Languages, LogOut, Moon, Settings, Sun, Users } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()
const theme = ref(localStorage.getItem('oa_theme') || 'light')
const fixedLabels = {
  offboarding: { zh: '退职', ja: '退職', en: 'Offboarding' },
  offboardingApproval: { zh: '退职审批', ja: '退職承認', en: 'Offboarding approvals' }
}

function applyTheme(value) {
  document.documentElement.classList.toggle('theme-dark', value === 'dark')
}

function fixedLabel(key) {
  return fixedLabels[key]?.[locale.value] || fixedLabels[key]?.ja || key
}

onMounted(() => {
  auth.bootstrap()
  applyTheme(theme.value)
})

const menu = computed(() => {
  const ui = (key) => auth.canUi(key)
  const items = ui('home') ? [{ path: '/home', label: t('nav.home'), icon: Home }] : []
  const employeeChildren = []
  if (ui('employees.internal') && auth.canAny('employees', ['read', 'read_self', 'update', 'import', 'create'])) {
    employeeChildren.push({ path: '/employees/internal', label: t('nav.internalEmployees') })
  }
  if (ui('employees.external') && auth.canAny('external_personnel', ['read', 'create', 'update', 'confirm']) && ['admin', 'hr'].includes(auth.user?.role)) {
    employeeChildren.push({ path: '/employees/external', label: t('nav.externalEmployees') })
  }
  if (employeeChildren.length) {
    items.push({ path: '/employees', label: t('nav.employees'), icon: Users, children: employeeChildren })
  }
  if (ui('employees.offboarding') && auth.canAny('employees', ['read', 'read_self', 'update_self'])) {
    items.push({ path: '/offboarding', label: fixedLabel('offboarding'), icon: LogOut })
  }
  const contractChildren = []
  if (ui('contracts.internal') && auth.canAny('contracts', ['read', 'read_self', 'create', 'import'])) {
    contractChildren.push({ path: '/contracts/internal', label: t('nav.internalContracts') })
  }
  if (ui('contracts.external.new') && auth.canAny('external_contracts', ['read', 'create', 'generate'])) {
    contractChildren.push({ path: '/contracts/external/new', label: t('nav.externalContractsNew') })
  }
  if (ui('contracts.external.partners') && auth.canAny('external_contracts', ['read', 'create', 'generate'])) {
    contractChildren.push({ path: '/contracts/external/partners', label: t('nav.externalPartners') })
  }
  if (contractChildren.length) {
    items.push({ path: '/contracts', label: t('nav.contracts'), icon: FileText, children: contractChildren })
  }
  const documentChildren = []
  if (ui('documents.purchase_orders') && auth.canAny('external_contracts', ['read', 'generate'])) {
    documentChildren.push({ path: '/documents/purchase-orders', label: t('nav.purchaseOrders') })
  }
  if (ui('documents.quotations') && auth.canAny('external_contracts', ['read', 'generate'])) {
    documentChildren.push({ path: '/documents/quotations', label: t('nav.quotations') })
  }
  if (ui('documents.invoices') && auth.canAny('external_contracts', ['read', 'generate'])) {
    documentChildren.push({ path: '/documents/invoices', label: t('nav.invoices') })
  }
  if (ui('documents.history') && auth.canAny('external_contracts', ['read', 'download'])) {
    documentChildren.push({ path: '/documents/history', label: t('nav.documentHistory') })
  }
  if (ui('documents.library') && auth.user?.role === 'admin') {
    documentChildren.push({ path: '/documents/library', label: t('nav.documentLibrary') })
  }
  if (documentChildren.length) {
    items.push({ path: '/documents', label: t('nav.documentManagement'), icon: FileText, children: documentChildren })
  }
  const approvalChildren = []
  if (ui('approvals.contracts') && auth.canAny('approvals', ['read', 'approve'])) {
    approvalChildren.push({ path: '/approvals/contracts', label: t('nav.contractApprovals') })
  }
  if (ui('approvals.reimbursements') && auth.canAny('approvals', ['read', 'approve']) && ['admin', 'hr'].includes(auth.user?.role)) {
    approvalChildren.push({ path: '/approvals/reimbursements', label: t('nav.reimbursementApprovals') })
  }
  if (ui('approvals.attendance') && auth.canAny('attendance', ['approve'])) {
    approvalChildren.push({ path: '/approvals/attendance', label: t('nav.attendanceApprovals') })
  }
  if (ui('approvals.offboarding') && auth.canAny('approvals', ['read', 'approve']) && ['admin', 'hr'].includes(auth.user?.role)) {
    approvalChildren.push({ path: '/approvals/offboarding', label: fixedLabel('offboardingApproval') })
  }
  if (approvalChildren.length) {
    items.push({ path: '/approvals', label: t('nav.approvals'), icon: ClipboardCheck, children: approvalChildren })
  }
  const reimbursementChildren = []
  if (ui('reimbursements.claims') && auth.canAny('reimbursements', ['read', 'read_self', 'create', 'create_self'])) {
    reimbursementChildren.push({ path: '/reimbursements/claims', label: t('nav.reimbursementClaims') })
  }
  if (ui('reimbursements.salaries') && auth.canAny('contracts', ['update'])) {
    reimbursementChildren.push({ path: '/reimbursements/salaries', label: t('nav.salaryDetails') })
  }
  if (ui('reimbursements.monthly_settlement') && auth.canAny('external_contracts', ['read', 'settle'])) {
    reimbursementChildren.push({ path: '/reimbursements/monthly-settlement', label: t('nav.monthlySettlement') })
  }
  if (reimbursementChildren.length) {
    items.push({ path: '/reimbursements', label: t('nav.expenseSettlement'), icon: HandCoins, children: reimbursementChildren })
  }
  if (auth.canAny('subcontracting', ['read', 'create'])) {
    const subcontractingChildren = [
      ui('subcontracting.notice') && { path: '/subcontracting/notice', label: t('nav.subcontractingNotice') },
      ui('subcontracting.quotations') && { path: '/subcontracting/quotations', label: t('nav.subcontractingQuotations') },
      ui('subcontracting.invoices') && { path: '/subcontracting/invoices', label: t('nav.subcontractingInvoices') },
      ui('subcontracting.personnel') && { path: '/subcontracting/personnel', label: t('nav.subcontractingPersonnel') }
    ].filter(Boolean)
    if (subcontractingChildren.length) {
      items.push({ path: '/subcontracting', label: t('nav.subcontracting'), icon: Handshake, children: subcontractingChildren })
    }
  }
  if (auth.canAny('attendance', ['read'])) {
    const attendanceChildren = []
    if (ui('attendance.summary')) {
      attendanceChildren.push({ path: '/attendance/summary', label: t('nav.attendanceSummary') })
    }
    if (ui('attendance.requests')) {
      attendanceChildren.push({ path: '/attendance/requests', label: t('nav.attendanceRequests') })
    }
    if (ui('attendance.settings') && auth.canAny('attendance', ['update', 'settings'])) {
      attendanceChildren.push({ path: '/attendance/settings', label: t('nav.attendanceSettings') })
    }
    if (attendanceChildren.length) {
      items.push({ path: '/attendance', label: t('nav.attendance'), icon: Clock3, children: attendanceChildren })
    }
  }
  if (ui('projects') && auth.canAny('projects', ['read', 'read_assigned', 'create', 'recommend'])) {
    items.push({ path: '/projects', label: t('nav.projects'), icon: Briefcase })
  }
  const settingChildren = []
  if (ui('settings.mail') && auth.user?.role === 'admin') {
    settingChildren.push({ path: '/settings/mail', label: t('nav.mailSettings') })
  }
  if (auth.user?.role === 'admin') {
    settingChildren.push({ path: '/settings/permissions', label: t('nav.permissionManagement') })
  }
  if (settingChildren.length) {
    items.push({ path: '/settings', label: t('nav.settings'), icon: Settings, children: settingChildren })
  }
  return items
})

function changeLocale(value) {
  locale.value = value
  localStorage.setItem('oa_locale', value)
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem('oa_theme', theme.value)
  applyTheme(theme.value)
}

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">{{ t('app.title') }}</div>
      <el-menu :default-active="route.path" router class="side-menu">
        <template v-for="item in menu" :key="item.path">
        <el-sub-menu v-if="item.children" :index="item.path">
          <template #title>
            <component :is="item.icon" class="menu-icon" />
            <span>{{ item.label }}</span>
          </template>
          <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
            <span>{{ child.label }}</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item v-else :index="item.path">
          <component :is="item.icon" class="menu-icon" />
          <span>{{ item.label }}</span>
        </el-menu-item>
        </template>
      </el-menu>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <div class="user-name">{{ auth.user?.full_name }}</div>
          <div class="user-role">{{ t('app.role') }}: {{ auth.user?.role }}</div>
        </div>
        <div class="top-actions">
          <Languages :size="18" />
          <el-segmented :model-value="locale" :options="['zh', 'ja', 'en']" @update:model-value="changeLocale" />
          <el-button :icon="theme === 'dark' ? Sun : Moon" circle @click="toggleTheme" />
          <el-button :icon="KeyRound" @click="router.push('/account/password')">{{ t('app.changePassword') }}</el-button>
          <el-button :icon="LogOut" @click="logout">{{ t('app.logout') }}</el-button>
        </div>
      </header>
      <section class="content">
        <router-view />
      </section>
    </main>
  </div>
</template>
