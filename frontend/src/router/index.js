import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '../components/AppLayout.vue'
import Login from '../views/Login.vue'
import ForceResetPassword from '../views/ForceResetPassword.vue'
import Home from '../views/Home.vue'
import Profile from '../views/Profile.vue'
import Employees from '../views/Employees.vue'
import EmployeeOffboarding from '../views/EmployeeOffboarding.vue'
import ExternalPersonnel from '../views/ExternalPersonnel.vue'
import Contracts from '../views/Contracts.vue'
import ExternalContracts from '../views/ExternalContracts.vue'
import Approvals from '../views/Approvals.vue'
import Reimbursements from '../views/Reimbursements.vue'
import DocumentManagement from '../views/DocumentManagement.vue'
import Projects from '../views/Projects.vue'
import Settings from '../views/Settings.vue'
import PermissionManagement from '../views/PermissionManagement.vue'
import PlatformSettings from '../views/PlatformSettings.vue'
import Subcontracting from '../views/Subcontracting.vue'
import Attendance from '../views/Attendance.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    { path: '/reset-password-required', name: 'resetPasswordRequired', component: ForceResetPassword, meta: { auth: true } },
    {
      path: '/',
      component: AppLayout,
      meta: { auth: true },
      children: [
        { path: '', redirect: '/home' },
        { path: 'home', name: 'home', component: Home, meta: { uiKey: 'home' } },
        { path: 'profile', name: 'myProfile', component: Profile, meta: { module: 'employees', uiKey: 'home' } },
        { path: 'account/password', name: 'accountPassword', component: ForceResetPassword },
        { path: 'employees', redirect: '/employees/internal' },
        { path: 'employees/internal', name: 'internalEmployees', component: Employees, meta: { module: 'employees', uiKey: 'employees.internal' } },
        { path: 'employees/external', name: 'externalEmployees', component: ExternalPersonnel, meta: { module: 'external_personnel', uiKey: 'employees.external' } },
        { path: 'employees/offboarding', redirect: '/offboarding' },
        { path: 'offboarding', name: 'employeeOffboarding', component: EmployeeOffboarding, meta: { module: 'employees', uiKey: 'employees.offboarding' } },
        { path: 'contracts', redirect: '/contracts/internal' },
        { path: 'contracts/internal', name: 'internalContracts', component: Contracts, meta: { module: 'contracts', uiKey: 'contracts.internal' } },
        { path: 'contracts/external', redirect: '/contracts/external/new' },
        { path: 'contracts/external/new', name: 'externalContractsNew', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'contracts.external.new' } },
        { path: 'contracts/external/partners', name: 'externalPartners', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'contracts.external.partners' } },
        { path: 'contracts/approvals', redirect: '/approvals/contracts' },
        { path: 'approvals', redirect: '/approvals/contracts' },
        { path: 'approvals/contracts', name: 'approvalContracts', component: Approvals, meta: { uiKey: 'approvals.contracts' } },
        { path: 'approvals/reimbursements', name: 'approvalReimbursements', component: Approvals, meta: { uiKey: 'approvals.reimbursements' } },
        { path: 'approvals/attendance', name: 'approvalAttendance', component: Approvals, meta: { module: 'attendance', uiKey: 'approvals.attendance' } },
        { path: 'approvals/offboarding', name: 'approvalOffboarding', component: Approvals, meta: { uiKey: 'approvals.offboarding' } },
        { path: 'reimbursements', redirect: '/reimbursements/claims' },
        { path: 'reimbursements/claims', name: 'reimbursements', component: Reimbursements, meta: { module: 'reimbursements', uiKey: 'reimbursements.claims' } },
        { path: 'reimbursements/salaries', name: 'salaryManagement', component: Contracts, meta: { module: 'contracts', uiKey: 'reimbursements.salaries' } },
        { path: 'reimbursements/monthly-settlement', name: 'monthlySettlement', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'reimbursements.monthly_settlement' } },
        { path: 'documents', redirect: '/documents/purchase-orders' },
        { path: 'documents/purchase-orders', name: 'documentPurchaseOrders', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'documents.purchase_orders' } },
        { path: 'documents/quotations', name: 'documentQuotations', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'documents.quotations' } },
        { path: 'documents/invoices', name: 'documentInvoices', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'documents.invoices' } },
        { path: 'documents/history', name: 'documentHistory', component: ExternalContracts, meta: { module: 'external_contracts', uiKey: 'documents.history' } },
        { path: 'documents/library', name: 'documents', component: DocumentManagement, meta: { uiKey: 'documents.library' } },
        { path: 'subcontracting', redirect: '/subcontracting/notice' },
        { path: 'subcontracting/notice', name: 'subcontractingNotice', component: Subcontracting, meta: { module: 'subcontracting', uiKey: 'subcontracting.notice' } },
        { path: 'subcontracting/quotations', name: 'subcontractingQuotations', component: Subcontracting, meta: { module: 'subcontracting', uiKey: 'subcontracting.quotations' } },
        { path: 'subcontracting/invoices', name: 'subcontractingInvoices', component: Subcontracting, meta: { module: 'subcontracting', uiKey: 'subcontracting.invoices' } },
        { path: 'subcontracting/personnel', name: 'subcontractingPersonnel', component: Subcontracting, meta: { module: 'subcontracting', uiKey: 'subcontracting.personnel' } },
        { path: 'attendance', redirect: '/attendance/summary' },
        { path: 'attendance/summary', name: 'attendanceSummary', component: Attendance, meta: { module: 'attendance', uiKey: 'attendance.summary' } },
        { path: 'attendance/requests', name: 'attendanceRequests', component: Attendance, meta: { module: 'attendance', uiKey: 'attendance.requests' } },
        { path: 'attendance/approvals', redirect: '/approvals/attendance' },
        { path: 'attendance/settings', name: 'attendanceSettings', component: Attendance, meta: { module: 'attendance', uiKey: 'attendance.settings' } },
        { path: 'projects', name: 'projects', component: Projects, meta: { module: 'projects', uiKey: 'projects' } },
        { path: 'settings', redirect: '/settings/mail' },
        { path: 'settings/mail', name: 'settings', component: Settings, meta: { admin: true, uiKey: 'settings.mail' } },
        { path: 'settings/permissions', name: 'permissionManagement', component: PermissionManagement, meta: { admin: true, uiKey: 'settings.permissions' } }
        ,{ path: 'settings/platform', name: 'platformSettings', component: PlatformSettings, meta: { admin: true, uiKey: 'settings.platform' } }
      ]
    }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.auth) {
    if (to.name === 'login' && auth.isLoggedIn) return '/home'
    return true
  }
  if (!auth.isLoggedIn) return '/login'
  await auth.bootstrap()
  if (auth.user?.must_reset_password && to.name !== 'resetPasswordRequired') return '/reset-password-required'
  if (!auth.user?.must_reset_password && to.name === 'resetPasswordRequired') return '/home'
  if (to.name === 'accountPassword' && auth.user?.role === 'admin') return '/home'
  const module = to.meta.module
  if (to.meta.admin && auth.user?.role !== 'admin') return '/home'
  if (to.meta.uiKey && !auth.canUi(to.meta.uiKey)) return '/home'
  if (module) {
    const allowed = Object.keys(auth.permissions[module] || {}).length || (auth.permissions[module] || []).length
    if (!allowed) return '/home'
  }
  return true
})

export default router
