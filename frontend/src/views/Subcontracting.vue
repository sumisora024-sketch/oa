<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { CheckCircle2, Download, FileSpreadsheet, Plus, RefreshCw, Upload } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()

const quotations = ref([])
const invoices = ref([])
const personnel = ref([])
const partners = ref([])
const onboardingItems = ref([])
const fixedFiles = ref([])
const selectedPartnerId = ref(null)
const quotationFormRef = ref(null)
const invoiceFormRef = ref(null)
const personnelFormRef = ref(null)
const noticeDialog = ref(false)
const activeNotice = ref(null)
const noticeFormRef = ref(null)

const quotationForm = reactive({
  partner_id: null,
  target_start_month: currentMonth(),
  target_end_month: currentMonth(),
  issue_date: today(),
  item_name: 'SES',
  quantity: 1,
  unit_price: 0,
  work_period: '',
  base_hours: '140-180h',
  workplace: '',
  note: '',
  file: null
})

const invoiceForm = reactive({
  partner_id: null,
  source_document_id: null,
  payment_month: currentMonth(),
  issue_date: today(),
  item_name: 'SES',
  amount: 0,
  note: '',
  file: null
})

const personnelForm = reactive({
  partner_id: null,
  full_name: '',
  assignment_month: currentMonth(),
  contract_end_date: '',
  monthly_hours: null,
  note: '',
  resume: null,
  avatar: null,
  timesheet: null
})

const noticeForm = reactive({
  company_name: '',
  address: '',
  representative_name: '',
  contact_name: '',
  email: '',
  phone: '',
  agreed_on: today(),
  scrolled_to_bottom: false
})

const isAdmin = computed(() => auth.user?.role === 'admin')
const isPartner = computed(() => auth.user?.role === 'partner')
const section = computed(() => route.path.split('/').pop() || 'quotations')
const partnerOptions = computed(() => partners.value.map((item) => ({ label: item.company_name, value: item.id })))
const approvedQuotations = computed(() => quotations.value.filter((row) => approvalStatus(row) === 'approved'))
const selectedInvoiceQuotation = computed(() => approvedQuotations.value.find((row) => row.id === invoiceForm.source_document_id))
const onboardingComplete = computed(() => onboardingItems.value.length > 0 && onboardingItems.value.every((item) => item.status === 'completed'))
const { pager: noticePager, pageRows: pagedOnboardingItems } = usePagination(onboardingItems)
const { pager: quotationPager, pageRows: pagedQuotations } = usePagination(quotations)
const { pager: invoicePager, pageRows: pagedInvoices } = usePagination(invoices)
const { pager: personnelPager, pageRows: pagedPersonnel } = usePagination(personnel)
const rules = computed(() => ({
  partner_id: [{ required: isAdmin.value, message: t('validation.required'), trigger: 'change' }],
  target_start_month: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  target_end_month: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  issue_date: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  item_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  unit_price: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  source_document_id: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  payment_month: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  amount: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  file: [{ validator: validateRequiredFile, trigger: 'change' }],
  full_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  assignment_month: [{ required: true, message: t('validation.required'), trigger: 'change' }],
  resume: [{ validator: validateRequiredFile, trigger: 'change' }],
  avatar: [{ validator: validateRequiredFile, trigger: 'change' }]
}))
const noticeRules = computed(() => ({
  company_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  address: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  representative_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  contact_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  email: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  phone: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  agreed_on: [{ required: true, message: t('validation.required'), trigger: 'change' }]
}))

function validateRequiredFile(_rule, value, callback) {
  if (!value) {
    callback(new Error(t('validation.required')))
    return
  }
  callback()
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function approvalStatus(row) {
  return row.attributes?.approval_status || 'pending'
}

function monthRange(row) {
  const start = row.attributes?.target_start_month || row.target_month
  const end = row.attributes?.target_end_month || row.target_month
  return start === end ? start : `${start} - ${end}`
}

function paymentMonth(row) {
  return row.attributes?.payment_month || row.target_month
}

function showApiError(error) {
  const detail = error.response?.data?.detail
  ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
}

function setQuotationFile(_file, fileList) {
  quotationForm.file = fileList.map((item) => item.raw).filter(Boolean)[0] || null
  quotationFormRef.value?.clearValidate('file')
}

function setInvoiceFile(_file, fileList) {
  invoiceForm.file = fileList.map((item) => item.raw).filter(Boolean)[0] || null
  invoiceFormRef.value?.clearValidate('file')
}

function setFile(field, fileList) {
  personnelForm[field] = fileList.map((item) => item.raw).filter(Boolean)[0] || null
  personnelFormRef.value?.clearValidate(field)
}

async function loadPartners() {
  if (!isAdmin.value) return
  partners.value = (await api.get('/external/partners')).data
  if (!selectedPartnerId.value && partners.value.length) selectedPartnerId.value = partners.value[0].id
}

async function loadOnboarding() {
  try {
    const params = selectedPartnerId.value ? { partner_id: selectedPartnerId.value } : {}
    onboardingItems.value = (await api.get('/subcontracting/onboarding', { params })).data
  } catch {
    onboardingItems.value = []
  }
}

async function load() {
  await loadPartners()
  const [quotationResponse, invoiceResponse, personnelResponse, fixedFileResponse] = await Promise.all([
    api.get('/subcontracting/quotations'),
    api.get('/subcontracting/invoices'),
    api.get('/external-personnel'),
    api.get('/subcontracting/fixed-files')
  ])
  quotations.value = quotationResponse.data
  invoices.value = invoiceResponse.data
  personnel.value = personnelResponse.data
  fixedFiles.value = fixedFileResponse.data
  await loadOnboarding()
}

async function submitQuotation() {
  try {
    await quotationFormRef.value?.validate()
    if (quotationForm.target_end_month < quotationForm.target_start_month) {
      ElMessage.error('対象終了月は対象開始月以降を指定してください')
      return
    }
    if (isPartner.value && !onboardingComplete.value) {
      ElMessage.warning('会社通知の確認と必要書類の提出を先に完了してください')
      return
    }
    const data = new FormData()
    if (isAdmin.value) data.append('partner_id', quotationForm.partner_id)
    data.append('target_start_month', quotationForm.target_start_month)
    data.append('target_end_month', quotationForm.target_end_month)
    data.append('issue_date', quotationForm.issue_date)
    data.append('item_name', quotationForm.item_name)
    data.append('quantity', quotationForm.quantity)
    data.append('unit_price', quotationForm.unit_price)
    if (quotationForm.work_period) data.append('work_period', quotationForm.work_period)
    if (quotationForm.base_hours) data.append('base_hours', quotationForm.base_hours)
    if (quotationForm.workplace) data.append('workplace', quotationForm.workplace)
    if (quotationForm.note) data.append('note', quotationForm.note)
    data.append('file', quotationForm.file)
    await api.post('/subcontracting/quotations/upload', data)
    ElMessage.success(t('common.success'))
    Object.assign(quotationForm, { note: '', file: null })
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

function applyInvoiceQuotation() {
  const source = selectedInvoiceQuotation.value
  if (!source) return
  invoiceForm.partner_id = source.partner_id
  invoiceForm.amount = source.total || 0
}

async function submitInvoice() {
  try {
    await invoiceFormRef.value?.validate()
    const data = new FormData()
    if (isAdmin.value) data.append('partner_id', invoiceForm.partner_id)
    data.append('source_document_id', invoiceForm.source_document_id)
    data.append('payment_month', invoiceForm.payment_month)
    data.append('issue_date', invoiceForm.issue_date)
    data.append('item_name', invoiceForm.item_name)
    data.append('amount', invoiceForm.amount)
    if (invoiceForm.note) data.append('note', invoiceForm.note)
    data.append('file', invoiceForm.file)
    await api.post('/subcontracting/invoices/upload', data)
    ElMessage.success(t('common.success'))
    Object.assign(invoiceForm, { source_document_id: null, amount: 0, note: '', file: null })
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function submitPersonnel() {
  try {
    await personnelFormRef.value?.validate()
    const data = new FormData()
    if (personnelForm.partner_id) data.append('partner_id', personnelForm.partner_id)
    data.append('full_name', personnelForm.full_name)
    data.append('assignment_month', personnelForm.assignment_month)
    if (personnelForm.contract_end_date) data.append('contract_end_date', personnelForm.contract_end_date)
    if (personnelForm.monthly_hours !== null && personnelForm.monthly_hours !== undefined) data.append('monthly_hours', personnelForm.monthly_hours)
    if (personnelForm.note) data.append('note', personnelForm.note)
    if (personnelForm.resume) data.append('resume', personnelForm.resume)
    if (personnelForm.avatar) data.append('avatar', personnelForm.avatar)
    if (personnelForm.timesheet) data.append('timesheet', personnelForm.timesheet)
    await api.post('/external-personnel', data)
    ElMessage.success(t('common.success'))
    Object.assign(personnelForm, { full_name: '', monthly_hours: null, note: '', resume: null, avatar: null, timesheet: null })
    await load()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

function openNotice(item) {
  activeNotice.value = item
  Object.assign(noticeForm, {
    company_name: item.form_data?.company_name || '',
    address: item.form_data?.address || '',
    representative_name: item.form_data?.representative_name || '',
    contact_name: item.form_data?.contact_name || '',
    email: item.form_data?.email || '',
    phone: item.form_data?.phone || '',
    agreed_on: item.form_data?.agreed_on || today(),
    scrolled_to_bottom: false
  })
  noticeDialog.value = true
}

function handleNoticeScroll(event) {
  const target = event.target
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 8) noticeForm.scrolled_to_bottom = true
}

async function completeNoticeForm() {
  try {
    await noticeFormRef.value?.validate()
    if (!noticeForm.scrolled_to_bottom) {
      ElMessage.warning('書類の最後まで確認してください')
      return
    }
    await api.post(
      `/subcontracting/onboarding/${activeNotice.value.item_code}/form`,
      { form_data: { ...noticeForm } },
      { params: selectedPartnerId.value ? { partner_id: selectedPartnerId.value } : {} }
    )
    ElMessage.success(t('common.success'))
    noticeDialog.value = false
    await loadOnboarding()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function uploadNoticeFile(item, options) {
  try {
    const data = new FormData()
    if (selectedPartnerId.value) data.append('partner_id', selectedPartnerId.value)
    data.append('file', options.file)
    await api.post(`/subcontracting/onboarding/${item.item_code}/upload`, data)
    ElMessage.success(t('common.success'))
    await loadOnboarding()
    options.onSuccess?.()
  } catch (error) {
    options.onError?.(error)
    if (error?.response) showApiError(error)
  }
}

function noticeActionType(item) {
  return ['nit-1', 'nit-2', 'nit-5'].includes(item.item_code) ? 'form' : 'upload'
}

function download(url) {
  if (url) window.open(url, '_blank')
}

onMounted(load)
watch(() => route.path, load)
watch(selectedPartnerId, loadOnboarding)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ t('nav.subcontracting') }}</h2>
      <div class="toolbar">
        <el-select v-if="isAdmin" v-model="selectedPartnerId" filterable style="width: 260px">
          <el-option v-for="partner in partnerOptions" :key="partner.value" :label="partner.label" :value="partner.value" />
        </el-select>
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
      </div>
    </div>

    <section v-if="section === 'notice'" class="settings-panel">
      <div class="notice-head">
        <div>
          <h3>会社通知・必要書類</h3>
          <p class="muted">NIT-1、NIT-2、NIT-5 は内容確認と入力が必要です。NIT-3、NIT-4 はテンプレートをダウンロードし、記入済みファイルをアップロードしてください。</p>
        </div>
        <el-tag :type="onboardingComplete ? 'success' : 'warning'">{{ onboardingComplete ? '完了' : '未完了' }}</el-tag>
      </div>
      <el-table :data="pagedOnboardingItems" height="calc(100vh - 350px)" stripe>
        <el-table-column prop="name" label="書類" min-width="260" sortable />
        <el-table-column prop="filename" label="テンプレート" min-width="260" />
        <el-table-column prop="status" label="状態" width="120" sortable>
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">{{ row.status === 'completed' ? '完了' : '未完了' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完了日時" width="180" sortable />
        <el-table-column fixed="right" :label="t('common.actions')" width="260">
          <template #default="{ row }">
            <el-button text :icon="Download" @click="download(row.template_download_url)">テンプレート</el-button>
            <el-button v-if="row.upload_download_url" text :icon="Download" @click="download(row.upload_download_url)">提出済み</el-button>
            <el-button v-if="noticeActionType(row) === 'form'" text type="primary" :icon="CheckCircle2" @click="openNotice(row)">確認・入力</el-button>
            <el-upload v-else :show-file-list="false" :http-request="(options) => uploadNoticeFile(row, options)">
              <el-button text type="primary" :icon="Upload">完成版アップロード</el-button>
            </el-upload>
          </template>
        </el-table-column>
      </el-table>
      <TablePager v-model:page="noticePager.page" v-model:page-size="noticePager.pageSize" :total="onboardingItems.length" />
    </section>

    <section v-if="section === 'quotations'">
      <section class="settings-panel">
        <el-alert v-if="isPartner && !onboardingComplete" type="warning" show-icon title="会社通知の確認と必要書類の提出を先に完了してください。" />
        <el-form ref="quotationFormRef" :model="quotationForm" :rules="rules" label-position="top" class="form-grid">
          <el-form-item v-if="isAdmin" :label="t('external.companyName')" prop="partner_id">
            <el-select v-model="quotationForm.partner_id" filterable>
              <el-option v-for="partner in partnerOptions" :key="partner.value" :label="partner.label" :value="partner.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="対象開始月" prop="target_start_month"><el-date-picker v-model="quotationForm.target_start_month" type="month" value-format="YYYY-MM" /></el-form-item>
          <el-form-item label="対象終了月" prop="target_end_month"><el-date-picker v-model="quotationForm.target_end_month" type="month" value-format="YYYY-MM" /></el-form-item>
          <el-form-item :label="t('external.issueDate')" prop="issue_date"><el-date-picker v-model="quotationForm.issue_date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item :label="t('external.itemName')" prop="item_name"><el-input v-model="quotationForm.item_name" /></el-form-item>
          <el-form-item :label="t('external.quantity')"><el-input-number v-model="quotationForm.quantity" :min="0" :controls="false" /></el-form-item>
          <el-form-item :label="t('external.unitPrice')" prop="unit_price"><el-input-number v-model="quotationForm.unit_price" :min="0" :controls="false" /></el-form-item>
          <el-form-item :label="t('external.baseHours')"><el-input v-model="quotationForm.base_hours" /></el-form-item>
          <el-form-item :label="t('fields.workplace')"><el-input v-model="quotationForm.workplace" /></el-form-item>
          <el-form-item :label="t('subcontracting.quotationFile')" prop="file">
            <el-upload :auto-upload="false" :limit="1" :on-change="setQuotationFile" :on-remove="setQuotationFile">
              <el-button :icon="Upload">{{ t('common.upload') }}</el-button>
            </el-upload>
          </el-form-item>
          <el-form-item :label="t('fields.note')" class="span-2"><el-input v-model="quotationForm.note" type="textarea" /></el-form-item>
        </el-form>
        <div class="toolbar">
          <el-button type="primary" :icon="Upload" @click="submitQuotation">{{ t('subcontracting.submitQuotation') }}</el-button>
        </div>
      </section>

      <el-table :data="pagedQuotations" height="calc(100vh - 590px)" stripe>
        <el-table-column prop="document_no" :label="t('external.documentNo')" min-width="180" sortable />
        <el-table-column prop="partner_name" :label="t('external.companyName')" min-width="180" sortable />
        <el-table-column label="対象期間" width="170" sortable><template #default="{ row }">{{ monthRange(row) }}</template></el-table-column>
        <el-table-column :label="t('external.total')" width="140" sortable><template #default="{ row }">{{ money(row.total) }}</template></el-table-column>
        <el-table-column :label="t('subcontracting.approvalStatus')" width="140" sortable><template #default="{ row }">{{ approvalStatus(row) }}</template></el-table-column>
        <el-table-column fixed="right" :label="t('common.actions')" width="140">
          <template #default="{ row }"><el-button v-if="row.download_url" text :icon="Download" @click="download(row.download_url)" /></template>
        </el-table-column>
      </el-table>
      <TablePager v-model:page="quotationPager.page" v-model:page-size="quotationPager.pageSize" :total="quotations.length" />
    </section>

    <section v-if="section === 'invoices'">
      <section class="settings-panel">
        <el-form ref="invoiceFormRef" :model="invoiceForm" :rules="rules" label-position="top" class="form-grid">
          <el-form-item v-if="isAdmin" :label="t('external.companyName')" prop="partner_id">
            <el-select v-model="invoiceForm.partner_id" filterable>
              <el-option v-for="partner in partnerOptions" :key="partner.value" :label="partner.label" :value="partner.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="承認済み見積書" prop="source_document_id" class="span-2">
            <el-select v-model="invoiceForm.source_document_id" filterable @change="applyInvoiceQuotation">
              <el-option
                v-for="doc in approvedQuotations"
                :key="doc.id"
                :label="`${doc.document_no} / ${doc.partner_name} / ${monthRange(doc)} / ${money(doc.total)}`"
                :value="doc.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="希望支払月" prop="payment_month"><el-date-picker v-model="invoiceForm.payment_month" type="month" value-format="YYYY-MM" /></el-form-item>
          <el-form-item :label="t('external.issueDate')" prop="issue_date"><el-date-picker v-model="invoiceForm.issue_date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item :label="t('external.itemName')" prop="item_name"><el-input v-model="invoiceForm.item_name" /></el-form-item>
          <el-form-item label="請求金額" prop="amount"><el-input-number v-model="invoiceForm.amount" :min="0" :controls="false" /></el-form-item>
          <el-form-item label="請求書ファイル" prop="file">
            <el-upload :auto-upload="false" :limit="1" :on-change="setInvoiceFile" :on-remove="setInvoiceFile">
              <el-button :icon="Upload">{{ t('common.upload') }}</el-button>
            </el-upload>
          </el-form-item>
          <el-form-item :label="t('fields.note')" class="span-2"><el-input v-model="invoiceForm.note" type="textarea" /></el-form-item>
        </el-form>
        <div class="toolbar">
          <el-button type="primary" :icon="Upload" :disabled="!approvedQuotations.length" @click="submitInvoice">請求書をアップロード</el-button>
        </div>
      </section>

      <el-table :data="pagedInvoices" height="calc(100vh - 590px)" stripe>
        <el-table-column prop="document_no" :label="t('external.documentNo')" min-width="180" sortable />
        <el-table-column prop="partner_name" :label="t('external.companyName')" min-width="180" sortable />
        <el-table-column label="希望支払月" width="130" sortable><template #default="{ row }">{{ paymentMonth(row) }}</template></el-table-column>
        <el-table-column :label="t('external.total')" width="140" sortable><template #default="{ row }">{{ money(row.total) }}</template></el-table-column>
        <el-table-column :label="t('subcontracting.approvalStatus')" width="140" sortable><template #default="{ row }">{{ approvalStatus(row) }}</template></el-table-column>
        <el-table-column fixed="right" :label="t('common.actions')" width="120">
          <template #default="{ row }"><el-button v-if="row.download_url" text :icon="Download" @click="download(row.download_url)" /></template>
        </el-table-column>
      </el-table>
      <TablePager v-model:page="invoicePager.page" v-model:page-size="invoicePager.pageSize" :total="invoices.length" />
    </section>

    <section v-if="section === 'personnel'">
      <section class="settings-panel">
        <el-form ref="personnelFormRef" :model="personnelForm" :rules="rules" label-position="top" class="form-grid">
          <el-form-item v-if="isAdmin" :label="t('external.companyName')" prop="partner_id">
            <el-select v-model="personnelForm.partner_id" filterable>
              <el-option v-for="partner in partnerOptions" :key="partner.value" :label="partner.label" :value="partner.value" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('fields.fullName')" prop="full_name"><el-input v-model="personnelForm.full_name" /></el-form-item>
          <el-form-item :label="t('subcontracting.assignmentMonth')" prop="assignment_month"><el-date-picker v-model="personnelForm.assignment_month" type="month" value-format="YYYY-MM" /></el-form-item>
          <el-form-item :label="t('external.contractEndDate')"><el-date-picker v-model="personnelForm.contract_end_date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item :label="t('fields.monthlyHours')"><el-input-number v-model="personnelForm.monthly_hours" :min="0" :controls="false" /></el-form-item>
          <el-form-item :label="t('fields.note')" class="span-2"><el-input v-model="personnelForm.note" type="textarea" /></el-form-item>
          <el-form-item label="CV" prop="resume"><el-upload :auto-upload="false" :limit="1" :on-change="(_file, files) => setFile('resume', files)" :on-remove="(_file, files) => setFile('resume', files)"><el-button>{{ t('common.upload') }}</el-button></el-upload></el-form-item>
          <el-form-item label="PNG" prop="avatar"><el-upload accept=".png,image/png" :auto-upload="false" :limit="1" :on-change="(_file, files) => setFile('avatar', files)" :on-remove="(_file, files) => setFile('avatar', files)"><el-button>{{ t('common.upload') }}</el-button></el-upload></el-form-item>
          <el-form-item label="作業報告書"><el-upload :auto-upload="false" :limit="1" :on-change="(_file, files) => setFile('timesheet', files)" :on-remove="(_file, files) => setFile('timesheet', files)"><el-button>{{ t('common.upload') }}</el-button></el-upload></el-form-item>
        </el-form>
        <div class="toolbar">
          <el-button type="primary" :icon="Plus" @click="submitPersonnel">{{ t('subcontracting.submitPersonnel') }}</el-button>
        </div>
      </section>

      <div class="table-scroll-shell">
        <el-table :data="pagedPersonnel" height="calc(100vh - 610px)" stripe>
          <el-table-column prop="full_name" :label="t('fields.fullName')" min-width="140" sortable />
          <el-table-column prop="company_name" :label="t('external.companyName')" min-width="180" sortable />
          <el-table-column prop="assignment_month" :label="t('subcontracting.assignmentMonth')" width="130" sortable />
          <el-table-column prop="contract_end_date" :label="t('external.contractEndDate')" width="140" sortable />
          <el-table-column prop="monthly_hours" :label="t('fields.monthlyHours')" width="120" sortable />
          <el-table-column prop="status" :label="t('external.status')" width="120" sortable />
          <el-table-column fixed="right" :label="t('common.actions')" width="180">
            <template #default="{ row }">
              <el-button v-if="row.resume_download_url" text :icon="FileSpreadsheet" @click="download(row.resume_download_url)">CV</el-button>
              <el-button v-if="row.avatar_download_url" text :icon="Download" @click="download(row.avatar_download_url)">PNG</el-button>
              <el-button v-if="row.timesheet_download_url" text :icon="Download" @click="download(row.timesheet_download_url)">作業</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <TablePager v-model:page="personnelPager.page" v-model:page-size="personnelPager.pageSize" :total="personnel.length" />
    </section>

    <el-dialog v-model="noticeDialog" title="書類確認・入力" width="720px">
      <div class="notice-document" @scroll="handleNoticeScroll">
        <h3>{{ activeNotice?.name }}</h3>
        <p>本書類の内容を確認し、以下の必要事項を入力してください。記入内容は NIT OA System に保存され、契約関連書類の確認履歴として利用されます。</p>
        <p>業務委託、秘密保持、会社情報の取扱い、連絡先、担当者情報について、貴社の正式情報を入力してください。</p>
        <p>最後までスクロールすると完了ボタンを押せるようになります。</p>
        <p class="notice-tail">以上の内容を確認し、必要事項を正確に入力したうえで提出します。</p>
      </div>
      <el-form ref="noticeFormRef" :model="noticeForm" :rules="noticeRules" label-position="top" class="form-grid">
        <el-form-item label="会社名" prop="company_name"><el-input v-model="noticeForm.company_name" /></el-form-item>
        <el-form-item label="住所" prop="address"><el-input v-model="noticeForm.address" /></el-form-item>
        <el-form-item label="代表者名" prop="representative_name"><el-input v-model="noticeForm.representative_name" /></el-form-item>
        <el-form-item label="担当者名" prop="contact_name"><el-input v-model="noticeForm.contact_name" /></el-form-item>
        <el-form-item label="メール" prop="email"><el-input v-model="noticeForm.email" /></el-form-item>
        <el-form-item label="電話番号" prop="phone"><el-input v-model="noticeForm.phone" /></el-form-item>
        <el-form-item label="確認日" prop="agreed_on"><el-date-picker v-model="noticeForm.agreed_on" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="noticeDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :disabled="!noticeForm.scrolled_to_bottom" @click="completeNoticeForm">入力を完了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.notice-head {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.notice-document {
  background: #f8fafc;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  color: #243b53;
  line-height: 1.8;
  max-height: 210px;
  margin-bottom: 18px;
  overflow-y: auto;
  padding: 18px 20px;
}

.notice-tail {
  margin-top: 280px;
  font-weight: 700;
}
</style>
