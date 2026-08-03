<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Download, FileSpreadsheet, FileText, Pencil, Plus, RefreshCw, Save, Search, Send, Trash2, Upload } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { downloadCsv as exportCsv } from '../utils/csv'

const auth = useAuthStore()
const route = useRoute()
const routeTabs = {
  externalContractsNew: 'contracts',
  externalPartners: 'partners',
  documentPurchaseOrders: 'purchase',
  documentQuotations: 'quotation',
  documentInvoices: 'invoice',
  documentHistory: 'documents',
  monthlySettlement: 'settlement'
}
const tabTitles = {
  contracts: '新規契約締結',
  partners: '締結済み会社',
  purchase: '発注書作成',
  quotation: '見積書作成',
  invoice: '請求書作成',
  documents: '書類履歴',
  settlement: '月次精算'
}
const activeTab = ref(routeTabs[route.name] || 'contracts')
const partners = ref([])
const contracts = ref([])
const documents = ref([])
const selectedRows = ref([])
const approvedPartnerQuotations = ref([])
const settlement = ref(null)
const q = ref('')
const salaryMonth = ref(currentMonth())
const quotationId = ref(null)
const uploadUseExisting = ref(false)

const partnerDialog = ref(false)
const contractDialog = ref(false)
const uploadDialog = ref(false)
const editingPartnerId = ref(null)
const editingContractId = ref(null)
const partnerAttributes = ref({})
const partnerFormRef = ref(null)
const contractFormRef = ref(null)
const uploadFormRef = ref(null)
const quotationFormRef = ref(null)

const partnerForm = reactive({
  company_name: '',
  company_kana: '',
  partner_type: 'both',
  contracted_at: '',
  contract_end_date: '',
  terminated: false,
  contact_name: '',
  email: '',
  phone: '',
  address: '',
  related_people: '',
  note: ''
})

const contractForm = reactive({
  company_name: '',
  direction: 'downstream',
  title: '業務委託基本契約書',
  contract_type: 'ses_basic',
  status: 'draft',
  contracted_at: '',
  contracted_success: false,
  contact_name: '',
  email: '',
  phone: '',
  note: ''
})

const uploadForm = reactive({
  partner_id: null,
  company_name: '',
  direction: 'upstream',
  title: '上位契約書',
  contracted_at: '',
  files: []
})

const docForm = reactive({
  partner_id: null,
  external_contract_id: null,
  source_document_id: null,
  target_month: currentMonth(),
  issue_date: today(),
  due_date: '',
  item_name: 'SES作業費',
  quantity: 1,
  unit_price: 0,
  note: '',
  work_period: '',
  base_hours: '140時間-180時間',
  workplace: ''
})

const partnerOptions = computed(() => partners.value.map((partner) => ({
  label: `${partner.company_name} / ${partnerTypeLabel(partner.partner_type)}`,
  value: partner.id,
  type: partner.partner_type
})))
const downstreamPartners = computed(() => partnerOptions.value.filter((item) => ['downstream', 'both'].includes(item.type)))
const upstreamPartners = computed(() => partnerOptions.value.filter((item) => ['upstream', 'both'].includes(item.type)))
const partnerTypeById = computed(() => Object.fromEntries(partners.value.map((partner) => [partner.id, partner.partner_type])))
const selectedDocumentPartner = computed(() => partners.value.find((partner) => partner.id === docForm.partner_id) || null)
const selectedApprovedQuotation = computed(() => approvedPartnerQuotations.value.find((doc) => doc.id === docForm.source_document_id) || null)
const canGeneratePurchaseOrder = computed(() => Boolean(selectedApprovedQuotation.value))
const canGenerateUpstreamDocuments = computed(() => ['upstream', 'both'].includes(selectedDocumentPartner.value?.partner_type))
const quotationDocuments = computed(() => documents.value.filter((doc) => (
  doc.document_type === 'quotation' && ['upstream', 'both'].includes(partnerTypeById.value[doc.partner_id])
)))
const selectedQuotation = computed(() => documents.value.find((doc) => doc.id === quotationId.value) || null)
const selectedQuotationPartner = computed(() => partners.value.find((partner) => partner.id === selectedQuotation.value?.partner_id) || null)
const canGenerateInvoice = computed(() => ['upstream', 'both'].includes(selectedQuotationPartner.value?.partner_type))
const isAdmin = computed(() => auth.user?.role === 'admin')
const canEditSettlement = computed(() => isAdmin.value)
const hasBatchActions = computed(() => ['contracts', 'partners', 'documents'].includes(activeTab.value))
const pageTitle = computed(() => tabTitles[activeTab.value] || '外部契約管理')
const invoiceSettlementRows = computed(() => settlement.value?.detail?.invoices || [])
const purchaseSettlementRows = computed(() => settlement.value?.detail?.purchase_orders || [])
const partnerLoopWarnings = computed(() => approvedPartnerQuotations.value
  .map((quotation) => {
    const hasPurchaseOrder = documents.value.some((doc) => doc.document_type === 'purchase_order' && doc.source_document_id === quotation.id)
    const hasPartnerInvoice = documents.value.some((doc) => (
      doc.document_type === 'partner_invoice'
      && doc.source_document_id === quotation.id
      && doc.attributes?.approval_status === 'approved'
    ))
    const missing = []
    if (!hasPurchaseOrder) missing.push('発注書未作成')
    if (!hasPartnerInvoice) missing.push('パートナー請求書未承認')
    return missing.length ? `${quotation.document_no} / ${quotation.partner_name}: ${missing.join('、')}` : null
  })
  .filter(Boolean))

const filteredPartners = computed(() => filterRows(partners.value, [
  'company_name', 'company_kana', 'partner_type', 'partner_login_id', 'contact_name', 'email', 'phone'
], 'partners'))
const filteredContracts = computed(() => filterRows(contracts.value, [
  'partner_name', 'direction', 'title', 'status', 'contracted_at'
], 'contracts'))
const filteredDocuments = computed(() => filterRows(documents.value, [
  'document_type', 'partner_name', 'document_no', 'target_month', 'total'
], 'documents'))
const { pager: partnerPager, pageRows: pagedPartners } = usePagination(filteredPartners)
const { pager: contractPager, pageRows: pagedContracts } = usePagination(filteredContracts)
const { pager: documentPager, pageRows: pagedDocuments } = usePagination(filteredDocuments)
const { pager: invoiceSettlementPager, pageRows: pagedInvoiceSettlementRows } = usePagination(invoiceSettlementRows)
const { pager: purchaseSettlementPager, pageRows: pagedPurchaseSettlementRows } = usePagination(purchaseSettlementRows)

const requiredRule = { required: true, message: '必須項目です', trigger: 'change' }
const partnerRules = {
  company_name: [{ required: true, message: '必須項目です', trigger: 'blur' }],
  partner_type: [requiredRule],
  email: [{ validator: validatePartnerEmail, trigger: 'blur' }]
}
const contractRules = {
  company_name: [{ required: true, message: '必須項目です', trigger: 'blur' }],
  direction: [requiredRule],
  email: [{ validator: validateContractEmail, trigger: 'blur' }],
  title: [{ required: true, message: '必須項目です', trigger: 'blur' }]
}
const uploadRules = {
  partner_id: [requiredRule],
  company_name: [{ required: true, message: '必須項目です', trigger: 'blur' }],
  title: [{ required: true, message: '必須項目です', trigger: 'blur' }],
  files: [{ validator: validateFiles, trigger: 'change' }]
}
const documentRules = {
  partner_id: [requiredRule],
  target_month: [requiredRule],
  issue_date: [requiredRule],
  item_name: [{ required: true, message: '必須項目です', trigger: 'blur' }],
  quantity: [requiredRule],
  unit_price: [requiredRule]
}

function validateOptionalEmail(_rule, value, callback) {
  const text = String(value || '').trim()
  if (!text || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) {
    callback()
    return
  }
  callback(new Error('有効なメールアドレスを入力してください'))
}

function validatePartnerEmail(_rule, value, callback) {
  const text = String(value || '').trim()
  if (['downstream', 'both'].includes(partnerForm.partner_type) && !text) {
    callback(new Error('協力会社、または上流・協力会社には担当者メールが必須です'))
    return
  }
  validateOptionalEmail(_rule, value, callback)
}

function validateContractEmail(_rule, value, callback) {
  const text = String(value || '').trim()
  if (['downstream', 'both'].includes(contractForm.direction) && !text) {
    callback(new Error('協力会社、または上流・協力会社には担当者メールが必須です'))
    return
  }
  validateOptionalEmail(_rule, value, callback)
}

function validateFiles(_rule, value, callback) {
  if (!Array.isArray(value) || value.length === 0) {
    callback(new Error('必須項目です'))
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

function partnerTypeLabel(value) {
  return {
    upstream: '上流会社',
    downstream: '協力会社',
    both: '上流・協力会社'
  }[value] || value || '-'
}

function filterRows(rows, keys, tabName) {
  const text = q.value.trim().toLowerCase()
  if (!text || activeTab.value !== tabName) return rows
  return rows.filter((row) => keys.some((key) => String(row[key] || '').toLowerCase().includes(text)))
}

function blankToNull(value) {
  if (typeof value !== 'string') return value ?? null
  const text = value.trim()
  return text ? text : null
}

function activePartnerDuplicate(companyName, excludeId = null) {
  const text = String(companyName || '').trim()
  if (!text) return null
  return partners.value.find((partner) => (
    partner.company_name === text
    && partner.contract_active
    && (!excludeId || partner.id !== excludeId)
  )) || null
}

function showActivePartnerDuplicate(partner) {
  const endDate = partner.contract_end_date || '未設定'
  ElMessage.warning(`${partner.company_name} は有効な契約がすでに存在します。契約終了日: ${endDate}。解約済み、または契約終了日を過ぎてから再締結してください。`)
}

function download(url) {
  if (url) window.open(url, '_blank')
}

function documentTypeLabel(value) {
  const labels = {
    purchase_order: '発注書',
    quotation: '見積書',
    invoice: '請求書',
    uploaded_contract: 'アップロード契約',
    partner_quotation: 'パートナー見積書',
    partner_invoice: 'パートナー請求書'
  }
  return labels[value] || value
}

function showApiError(error) {
  const detail = error.response?.data?.detail
  ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || '処理に失敗しました')
}

function resetPartnerForm() {
  editingPartnerId.value = null
  partnerAttributes.value = {}
  Object.assign(partnerForm, {
    company_name: '',
    company_kana: '',
    partner_type: 'both',
    contracted_at: '',
    contract_end_date: '',
    terminated: false,
    contact_name: '',
    email: '',
    phone: '',
    address: '',
    related_people: '',
    note: ''
  })
  partnerFormRef.value?.clearValidate()
}

function openPartnerCreate() {
  resetPartnerForm()
  partnerDialog.value = true
}

function openPartnerEdit(row) {
  editingPartnerId.value = row.id
  partnerAttributes.value = { ...(row.attributes || {}) }
  Object.assign(partnerForm, {
    company_name: row.company_name || '',
    company_kana: row.company_kana || '',
    partner_type: row.partner_type || 'both',
    contracted_at: row.contracted_at || '',
    contract_end_date: row.contract_end_date || '',
    terminated: Boolean(row.terminated),
    contact_name: row.contact_name || '',
    email: row.email || '',
    phone: row.phone || '',
    address: row.address || '',
    related_people: row.attributes?.related_people || '',
    note: row.note || ''
  })
  partnerDialog.value = true
}

function partnerPayload() {
  return {
    company_name: partnerForm.company_name.trim(),
    company_kana: blankToNull(partnerForm.company_kana),
    partner_type: partnerForm.partner_type,
    contracted_at: blankToNull(partnerForm.contracted_at),
    contract_end_date: blankToNull(partnerForm.contract_end_date),
    terminated: Boolean(partnerForm.terminated),
    contact_name: blankToNull(partnerForm.contact_name),
    email: blankToNull(partnerForm.email),
    phone: blankToNull(partnerForm.phone),
    address: blankToNull(partnerForm.address),
    note: blankToNull(partnerForm.note),
    attributes: {
      ...partnerAttributes.value,
      related_people: blankToNull(partnerForm.related_people)
    }
  }
}

function resetContractForm() {
  editingContractId.value = null
  Object.assign(contractForm, {
    company_name: '',
    direction: 'downstream',
    title: '業務委託基本契約書',
    contract_type: 'ses_basic',
    status: 'draft',
    contracted_at: '',
    contracted_success: false,
    contact_name: '',
    email: '',
    phone: '',
    note: ''
  })
  contractFormRef.value?.clearValidate()
}

function openContractCreate() {
  resetContractForm()
  contractDialog.value = true
}

function openContractEdit(row) {
  editingContractId.value = row.id
  const partner = partners.value.find((item) => item.id === row.partner_id)
  Object.assign(contractForm, {
    company_name: row.partner_name || '',
    direction: row.direction || 'downstream',
    title: row.title || '',
    contract_type: row.contract_type || 'ses_basic',
    status: row.status || 'draft',
    contracted_at: row.contracted_at || '',
    contracted_success: Boolean(row.contracted_success),
    contact_name: partner?.contact_name || '',
    email: partner?.email || '',
    phone: partner?.phone || '',
    note: row.note || ''
  })
  contractDialog.value = true
}

function contractPayload() {
  const contractedSuccess = Boolean(contractForm.contracted_success)
  return {
    ...contractForm,
    company_name: contractForm.company_name.trim(),
    title: contractForm.title.trim(),
    status: contractedSuccess ? 'signed' : 'draft',
    contracted_success: contractedSuccess,
    contracted_at: blankToNull(contractForm.contracted_at),
    contact_name: blankToNull(contractForm.contact_name),
    email: blankToNull(contractForm.email),
    phone: blankToNull(contractForm.phone),
    note: blankToNull(contractForm.note)
  }
}

function applyApprovedQuotation() {
  const source = selectedApprovedQuotation.value
  if (!source) return
  docForm.partner_id = source.partner_id
  docForm.target_month = source.target_month
  docForm.note = source.note || ''
  docForm.work_period = source.attributes?.work_period || source.target_month
  docForm.base_hours = source.attributes?.base_hours || docForm.base_hours
  docForm.workplace = source.attributes?.workplace || ''
}

function documentPayload(kind = 'manual') {
  const source = kind === 'purchase_order' ? selectedApprovedQuotation.value : null
  return {
    partner_id: source?.partner_id || docForm.partner_id,
    external_contract_id: docForm.external_contract_id || null,
    source_document_id: source?.id || null,
    target_month: source?.target_month || docForm.target_month,
    issue_date: docForm.issue_date,
    due_date: docForm.due_date || null,
    items: source ? [] : [{
      name: docForm.item_name,
      quantity: docForm.quantity,
      unit_price: docForm.unit_price
    }],
    note: docForm.note || null,
    attributes: {
      ...(source?.attributes || {}),
      work_period: docForm.work_period || docForm.target_month,
      base_hours: docForm.base_hours,
      workplace: docForm.workplace
    }
  }
}

async function loadAll() {
  await Promise.all([loadPartners(), loadContracts(), loadDocuments(), loadApprovedPartnerQuotations()])
}

async function loadPartners() {
  partners.value = (await api.get('/external/partners')).data
}

async function loadContracts() {
  contracts.value = (await api.get('/external/contracts')).data
}

async function loadDocuments() {
  documents.value = (await api.get('/external/documents')).data
}

async function loadApprovedPartnerQuotations() {
  approvedPartnerQuotations.value = (await api.get('/external/partner-quotations/approved')).data
}

async function savePartner() {
  try {
    await partnerFormRef.value?.validate()
    const duplicate = activePartnerDuplicate(partnerForm.company_name, editingPartnerId.value)
    if (duplicate) {
      showActivePartnerDuplicate(duplicate)
      return
    }
    if (editingPartnerId.value) {
      await api.put(`/external/partners/${editingPartnerId.value}`, partnerPayload())
    } else {
      await api.post('/external/partners', partnerPayload())
    }
    ElMessage.success('保存しました')
    partnerDialog.value = false
    resetPartnerForm()
    await loadPartners()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function saveContract() {
  try {
    await contractFormRef.value?.validate()
    let response
    if (editingContractId.value) {
      const data = contractPayload()
      delete data.company_name
      response = await api.put(`/external/contracts/${editingContractId.value}`, data)
    } else {
      const duplicate = activePartnerDuplicate(contractForm.company_name)
      if (duplicate) {
        showActivePartnerDuplicate(duplicate)
        return
      }
      response = await api.post('/external/contracts', contractPayload())
    }
    ElMessage.success('保存しました')
    if (response?.data?.partner_temporary_password) {
      await ElMessageBox.alert(
        `アカウント: ${response.data.partner_login_id}\n一時パスワード: ${response.data.partner_temporary_password}`,
        'パートナーアカウント'
      )
    }
    contractDialog.value = false
    resetContractForm()
    await Promise.all([loadContracts(), loadPartners()])
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function deleteContract(row) {
  try {
    await ElMessageBox.confirm('この契約を削除しますか？', '削除', { type: 'warning' })
    await api.delete(`/external/contracts/${row.id}`)
    ElMessage.success('削除しました')
    await loadContracts()
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

async function deletePartner(row) {
  try {
    await ElMessageBox.confirm('この会社を削除しますか？', '削除', { type: 'warning' })
    await api.delete(`/external/partners/${row.id}`)
    ElMessage.success('削除しました')
    await Promise.all([loadPartners(), loadContracts(), loadDocuments()])
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

async function sendPartnerAccount(row) {
  if (!row.email) {
    ElMessage.error('担当者メールを入力してください')
    return
  }
  try {
    await ElMessageBox.confirm('一時パスワードを再発行し、担当者メールへ送信しますか？', 'アカウント情報送信', { type: 'warning' })
    await api.post(`/external/partners/${row.id}/send-account-mail`)
    ElMessage.success('送信しました')
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

async function uploadContract() {
  try {
    await uploadFormRef.value?.validate()
    const duplicate = uploadUseExisting.value
      ? partners.value.find((partner) => partner.id === uploadForm.partner_id && partner.contract_active)
      : activePartnerDuplicate(uploadForm.company_name)
    if (duplicate) {
      showActivePartnerDuplicate(duplicate)
      return
    }
    const data = new FormData()
    if (uploadUseExisting.value) {
      data.append('partner_id', uploadForm.partner_id)
    } else {
      data.append('company_name', uploadForm.company_name.trim())
    }
    data.append('direction', uploadForm.direction)
    data.append('title', uploadForm.title.trim())
    if (uploadForm.contracted_at) data.append('contracted_at', uploadForm.contracted_at)
    uploadForm.files.forEach((file) => data.append('files', file))
    const response = await api.post('/external/contracts/upload', data)
    ElMessage.success('アップロードしました')
    if (response?.data?.partner_temporary_password) {
      await ElMessageBox.alert(
        `アカウント: ${response.data.partner_login_id}\n一時パスワード: ${response.data.partner_temporary_password}`,
        'パートナーアカウント'
      )
    }
    uploadDialog.value = false
    Object.assign(uploadForm, { partner_id: null, company_name: '', direction: 'upstream', contracted_at: '', files: [] })
    uploadUseExisting.value = false
    await Promise.all([loadContracts(), loadDocuments(), loadPartners()])
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function generatePurchaseOrder() {
  try {
    if (!canGeneratePurchaseOrder.value) {
      ElMessage.error('承認済みのパートナー見積書を選択してください')
      return
    }
    const { data } = await api.post('/external/purchase-orders', documentPayload('purchase_order'))
    ElMessage.success('発注書を作成しました')
    await Promise.all([loadDocuments(), loadApprovedPartnerQuotations()])
    download(data.download_url)
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function generateQuotation() {
  try {
    await quotationFormRef.value?.validate()
    if (!canGenerateUpstreamDocuments.value) {
      ElMessage.error('見積書は上流会社、または上流・協力会社のみ作成できます')
      return
    }
    const { data } = await api.post('/external/quotations', documentPayload())
    ElMessage.success('見積書を作成しました')
    await loadDocuments()
    download(data.download_url)
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function generateInvoice() {
  try {
    if (!quotationId.value) {
      ElMessage.error('見積書を選択してください')
      return
    }
    if (!canGenerateInvoice.value) {
      ElMessage.error('請求書は上流会社、または上流・協力会社のみ作成できます')
      return
    }
    const { data } = await api.post(`/external/invoices/from-quotation/${quotationId.value}`)
    ElMessage.success('請求書を作成しました')
    await loadDocuments()
    download(data.download_url)
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

async function deleteDocument(row) {
  try {
    await ElMessageBox.confirm('この書類を削除しますか？', '削除', { type: 'warning' })
    await api.delete(`/external/documents/${row.id}`)
    ElMessage.success('削除しました')
    await Promise.all([loadDocuments(), activeTab.value === 'settlement' ? loadSettlement() : Promise.resolve()])
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

async function deleteSelectedRows() {
  if (!selectedRows.value.length || !hasBatchActions.value) return
  if (activeTab.value === 'partners' && !isAdmin.value) {
    ElMessage.warning('会社の削除はadminのみ操作できます')
    return
  }
  try {
    await ElMessageBox.confirm(`${selectedRows.value.length}件を削除します。`, '削除', { type: 'warning' })
    const endpoint = {
      contracts: (row) => `/external/contracts/${row.id}`,
      partners: (row) => `/external/partners/${row.id}`,
      documents: (row) => `/external/documents/${row.id}`
    }[activeTab.value]
    await Promise.all(selectedRows.value.map((row) => api.delete(endpoint(row))))
    selectedRows.value = []
    ElMessage.success('削除しました')
    await Promise.all([loadContracts(), loadPartners(), loadDocuments()])
  } catch (error) {
    if (error === 'cancel') return
    if (error?.response) showApiError(error)
  }
}

async function loadSettlement() {
  settlement.value = (await api.get(`/external/settlements/${salaryMonth.value}`)).data
}

async function updateSettlementDocument(row) {
  try {
    await api.put(`/external/documents/${row.id}/settlement`, {
      settlement_confirmed: Boolean(row.settlement_confirmed),
      settlement_actual_amount: Number(row.settlement_actual_amount || 0)
    })
    ElMessage.success('保存しました')
    await loadSettlement()
  } catch (error) {
    if (error?.response) showApiError(error)
  }
}

function handleTabChange(name) {
  selectedRows.value = []
  partnerPager.page = 1
  contractPager.page = 1
  documentPager.page = 1
  if (name === 'settlement') loadSettlement()
}

function activeRowsForDownload() {
  if (activeTab.value === 'contracts') return filteredContracts.value
  if (activeTab.value === 'partners') return filteredPartners.value
  if (activeTab.value === 'documents') return filteredDocuments.value
  return []
}

function activeCsvColumns() {
  if (activeTab.value === 'contracts') {
    return [
      { key: 'partner_name', label: '会社名' },
      { label: '区分', value: (row) => partnerTypeLabel(row.direction) },
      { key: 'title', label: 'タイトル' },
      { key: 'status', label: '状態' },
      { key: 'contracted_at', label: '締結日' }
    ]
  }
  if (activeTab.value === 'partners') {
    return [
      { key: 'company_name', label: '会社名' },
      { key: 'company_kana', label: '会社カナ' },
      { label: '区分', value: (row) => partnerTypeLabel(row.partner_type) },
      { key: 'partner_login_id', label: 'パートナーアカウント' },
      { key: 'contracted_at', label: '締結日' },
      { key: 'contract_end_date', label: '契約終了日' },
      { key: 'contract_active', label: '有効' },
      { key: 'contact_name', label: '担当者' },
      { key: 'email', label: 'メール' },
      { key: 'phone', label: '電話' },
      { label: '関連人员', value: (row) => row.attributes?.related_people }
    ]
  }
  return [
    { label: '書類種別', value: (row) => documentTypeLabel(row.document_type) },
    { key: 'partner_name', label: '会社名' },
    { key: 'document_no', label: '書類番号' },
    { key: 'target_month', label: '対象年月' },
    { key: 'issue_date', label: '発行日' },
    { key: 'total', label: '合計' },
    { key: 'download_url', label: 'ダウンロードURL' }
  ]
}

function downloadActiveRows(rowsToExport, filename) {
  const result = exportCsv(rowsToExport, activeCsvColumns(), filename)
  if (!result.ok) ElMessage.warning(result.message)
}

function handleBatchCommand(command) {
  if (command === 'delete') {
    deleteSelectedRows()
    return
  }
  const prefix = {
    contracts: 'external-contracts',
    partners: 'external-partners',
    documents: 'external-documents'
  }[activeTab.value] || 'external'
  if (command === 'selected') {
    downloadActiveRows(selectedRows.value, `${prefix}-selected.csv`)
    return
  }
  downloadActiveRows(activeRowsForDownload(), `${prefix}-list.csv`)
}

function syncTabFromRoute() {
  const next = routeTabs[route.name] || 'contracts'
  activeTab.value = next
  handleTabChange(next)
}

onMounted(async () => {
  await loadAll()
  if (activeTab.value === 'settlement') await loadSettlement()
})
watch(() => route.name, syncTabFromRoute)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ pageTitle }}</h2>
      <div class="toolbar">
        <el-input v-if="['contracts', 'partners', 'documents'].includes(activeTab)" v-model="q" :prefix-icon="Search" placeholder="検索" clearable style="width: 240px" />
        <span v-if="selectedRows.length" class="muted">{{ selectedRows.length }} 件選択中</span>
        <el-button v-if="hasBatchActions" type="danger" :icon="Trash2" :disabled="!selectedRows.length || (activeTab === 'partners' && !isAdmin)" @click="deleteSelectedRows">選択行を削除</el-button>
        <el-button v-if="hasBatchActions" :icon="Download" :disabled="!selectedRows.length" @click="downloadActiveRows(selectedRows, `${activeTab}-selected.csv`)">選択行をダウンロード</el-button>
        <el-button :icon="RefreshCw" @click="activeTab === 'settlement' ? loadSettlement() : loadAll()">更新</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="single-route-tabs" @tab-change="handleTabChange">
      <el-tab-pane v-if="activeTab === 'contracts'" label="新規契約締結" name="contracts">
        <div class="toolbar section-toolbar">
          <el-button type="primary" :icon="Plus" @click="openContractCreate">新規契約</el-button>
          <el-button :icon="Upload" @click="uploadDialog = true">上位契約アップロード</el-button>
        </div>
        <el-table :data="pagedContracts" height="calc(100vh - 310px)" stripe @selection-change="selectedRows = $event">
          <el-table-column type="selection" width="46" />
          <el-table-column prop="partner_name" label="会社名" min-width="220" sortable />
          <el-table-column label="区分" width="140" sortable>
            <template #default="{ row }">{{ partnerTypeLabel(row.direction) }}</template>
          </el-table-column>
          <el-table-column prop="title" label="タイトル" min-width="180" sortable />
          <el-table-column label="締結成功" width="120">
            <template #default="{ row }">{{ row.contracted_success ? 'はい' : 'いいえ' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状態" width="110" sortable />
          <el-table-column prop="contracted_at" label="締結日" width="130" sortable />
          <el-table-column fixed="right" label="操作" width="120">
            <template #default="{ row }">
              <el-button text type="primary" :icon="Pencil" @click="openContractEdit(row)" />
              <el-button text type="danger" :icon="Trash2" @click="deleteContract(row)" />
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="contractPager.page" v-model:page-size="contractPager.pageSize" :total="filteredContracts.length" />
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'partners'" label="締結済み会社" name="partners">
        <div class="toolbar section-toolbar">
          <el-button type="primary" :icon="Plus" @click="openPartnerCreate">会社追加</el-button>
        </div>
        <el-table :data="pagedPartners" height="calc(100vh - 310px)" stripe @selection-change="selectedRows = $event">
          <el-table-column type="selection" width="46" />
          <el-table-column prop="company_name" label="会社名" min-width="220" sortable />
          <el-table-column prop="company_kana" label="会社カナ" min-width="160" sortable />
          <el-table-column label="区分" width="150" sortable>
            <template #default="{ row }">{{ partnerTypeLabel(row.partner_type) }}</template>
          </el-table-column>
          <el-table-column prop="partner_login_id" label="パートナーアカウント" min-width="190" />
          <el-table-column prop="contracted_at" label="締結日" width="130" sortable />
          <el-table-column prop="contract_end_date" label="契約終了日" width="140" sortable />
          <el-table-column label="解約済み" width="120">
            <template #default="{ row }">{{ row.terminated ? 'はい' : 'いいえ' }}</template>
          </el-table-column>
          <el-table-column label="有効" width="110">
            <template #default="{ row }"><el-tag :type="row.contract_active ? 'success' : 'info'">{{ row.contract_active ? '有効' : '無効' }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="contact_name" label="担当者" width="140" />
          <el-table-column prop="email" label="メール" min-width="180" />
          <el-table-column prop="phone" label="電話" width="140" />
          <el-table-column label="関連人員" min-width="160">
            <template #default="{ row }">{{ row.attributes?.related_people || '-' }}</template>
          </el-table-column>
          <el-table-column fixed="right" label="操作" width="160">
            <template #default="{ row }">
              <el-button text type="primary" :icon="Pencil" @click="openPartnerEdit(row)" />
              <el-button v-if="['downstream', 'both'].includes(row.partner_type) && row.partner_login_id" text type="success" :icon="Send" title="アカウント情報を送信" @click="sendPartnerAccount(row)" />
              <el-button v-if="isAdmin" text type="danger" :icon="Trash2" @click="deletePartner(row)" />
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="partnerPager.page" v-model:page-size="partnerPager.pageSize" :total="filteredPartners.length" />
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'purchase'" label="発注書作成" name="purchase">
        <section class="settings-panel">
          <el-form :model="docForm" label-position="top" class="form-grid">
            <el-form-item label="承認済みパートナー見積書">
              <el-select v-model="docForm.source_document_id" filterable clearable @change="applyApprovedQuotation">
                <el-option v-for="doc in approvedPartnerQuotations" :key="doc.id" :label="`${doc.document_no} / ${doc.partner_name} / ${doc.target_month} / ${money(doc.total)}`" :value="doc.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="発行日"><el-date-picker v-model="docForm.issue_date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="支払期限"><el-date-picker v-model="docForm.due_date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="基準時間幅"><el-input v-model="docForm.base_hours" /></el-form-item>
            <el-form-item label="作業場所"><el-input v-model="docForm.workplace" /></el-form-item>
            <el-form-item label="備考" class="span-2"><el-input v-model="docForm.note" type="textarea" :rows="2" /></el-form-item>
          </el-form>
          <p class="muted">承認済みのパートナー見積書を選択した場合のみ発注書を作成できます。</p>
          <div class="toolbar">
            <el-button type="primary" :icon="FileText" :disabled="!canGeneratePurchaseOrder" @click="generatePurchaseOrder">発注書作成</el-button>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'quotation'" label="見積書作成" name="quotation">
        <section class="settings-panel">
          <el-form ref="quotationFormRef" :model="docForm" :rules="documentRules" label-position="top" class="form-grid">
            <el-form-item label="会社名" prop="partner_id">
              <el-select v-model="docForm.partner_id" filterable>
                <el-option v-for="partner in upstreamPartners" :key="partner.value" :label="partner.label" :value="partner.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="対象年月" prop="target_month"><el-date-picker v-model="docForm.target_month" type="month" value-format="YYYY-MM" /></el-form-item>
            <el-form-item label="発行日" prop="issue_date"><el-date-picker v-model="docForm.issue_date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="支払期限"><el-date-picker v-model="docForm.due_date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="項目" prop="item_name"><el-input v-model="docForm.item_name" /></el-form-item>
            <el-form-item label="数量" prop="quantity"><el-input-number v-model="docForm.quantity" :min="0" :controls="false" /></el-form-item>
            <el-form-item label="単価" prop="unit_price"><el-input-number v-model="docForm.unit_price" :min="0" :controls="false" /></el-form-item>
            <el-form-item label="作業場所"><el-input v-model="docForm.workplace" /></el-form-item>
            <el-form-item label="基準時間幅"><el-input v-model="docForm.base_hours" /></el-form-item>
            <el-form-item label="備考" class="span-2"><el-input v-model="docForm.note" type="textarea" :rows="2" /></el-form-item>
          </el-form>
          <p class="muted">上流会社、または上流・協力会社に対して見積書を作成できます。</p>
          <div class="toolbar">
            <el-button type="success" :icon="FileSpreadsheet" :disabled="!canGenerateUpstreamDocuments" @click="generateQuotation">見積書作成</el-button>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'invoice'" label="請求書作成" name="invoice">
        <section class="settings-panel">
          <h3>見積書から請求書を作成</h3>
          <div class="toolbar">
            <el-select v-model="quotationId" filterable placeholder="見積書を選択" style="width: 380px">
              <el-option v-for="doc in quotationDocuments" :key="doc.id" :label="`${doc.document_no} / ${doc.partner_name} / ${money(doc.total)}`" :value="doc.id" />
            </el-select>
            <el-button type="warning" :icon="FileText" :disabled="!selectedQuotation || !canGenerateInvoice" @click="generateInvoice">請求書作成</el-button>
          </div>
        </section>
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'documents'" label="書類履歴" name="documents">
        <el-alert v-if="partnerLoopWarnings.length" class="loop-warning" type="warning" show-icon :closable="false" :title="`三方書類の未完了 ${partnerLoopWarnings.length}件`">
          <template #default>
            <div v-for="item in partnerLoopWarnings" :key="item">{{ item }}</div>
          </template>
        </el-alert>
        <el-table :data="pagedDocuments" height="calc(100vh - 310px)" stripe @selection-change="selectedRows = $event">
          <el-table-column type="selection" width="46" />
          <el-table-column label="書類種別" min-width="150">
            <template #default="{ row }">{{ documentTypeLabel(row.document_type) }}</template>
          </el-table-column>
          <el-table-column prop="partner_name" label="会社名" min-width="240" sortable />
          <el-table-column prop="document_no" label="書類番号" min-width="220" sortable />
          <el-table-column prop="target_month" label="対象年月" min-width="120" sortable />
          <el-table-column label="合計金額" min-width="150" sortable>
            <template #default="{ row }">{{ money(row.total) }}</template>
          </el-table-column>
          <el-table-column fixed="right" label="操作" width="140">
            <template #default="{ row }">
              <el-button v-if="row.download_url" text type="primary" :icon="Download" @click="download(row.download_url)" />
              <el-button text type="danger" :icon="Trash2" @click="deleteDocument(row)" />
            </template>
          </el-table-column>
        </el-table>
        <TablePager v-model:page="documentPager.page" v-model:page-size="documentPager.pageSize" :total="filteredDocuments.length" />
      </el-tab-pane>

      <el-tab-pane v-if="activeTab === 'settlement'" label="月次精算" name="settlement">
        <div class="toolbar section-toolbar">
          <el-date-picker v-model="salaryMonth" type="month" value-format="YYYY-MM" :clearable="false" />
          <el-button :icon="RefreshCw" @click="loadSettlement">更新</el-button>
        </div>
        <el-descriptions v-if="settlement" :column="2" border>
          <el-descriptions-item label="請求書合計">{{ money(settlement.invoice_total) }}</el-descriptions-item>
          <el-descriptions-item label="パートナー請求書合計">{{ money(settlement.purchase_order_total) }}</el-descriptions-item>
          <el-descriptions-item label="実払給与合計">{{ money(settlement.salary_total) }}</el-descriptions-item>
          <el-descriptions-item label="当月収支">{{ money(settlement.net_income) }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="settlement" class="settlement-detail-grid">
          <section class="settlement-detail-panel">
            <h3>請求書入金明細</h3>
            <div class="settlement-table-wrap">
              <el-table class="settlement-table" :data="pagedInvoiceSettlementRows" stripe table-layout="fixed">
                <el-table-column prop="document_no" label="書類番号" width="180" />
                <el-table-column prop="partner_name" label="会社名" width="190" />
                <el-table-column label="合計" width="130"><template #default="{ row }">{{ money(row.total) }}</template></el-table-column>
                <el-table-column label="入金済み" width="120"><template #default="{ row }"><el-switch v-model="row.settlement_confirmed" :disabled="!canEditSettlement" /></template></el-table-column>
                <el-table-column label="実入金額" width="160"><template #default="{ row }"><el-input-number v-model="row.settlement_actual_amount" class="table-number-input" :min="0" :controls="false" :disabled="!canEditSettlement" /></template></el-table-column>
                <el-table-column label="計上額" width="140"><template #default="{ row }">{{ money(row.settlement_confirmed ? row.settlement_actual_amount : 0) }}</template></el-table-column>
                <el-table-column v-if="canEditSettlement" label="操作" width="90"><template #default="{ row }"><el-button text type="primary" :icon="Save" @click="updateSettlementDocument(row)" /></template></el-table-column>
              </el-table>
            </div>
            <TablePager v-model:page="invoiceSettlementPager.page" v-model:page-size="invoiceSettlementPager.pageSize" :total="invoiceSettlementRows.length" />
          </section>
          <section class="settlement-detail-panel">
            <h3>パートナー請求書支払明細</h3>
            <div class="settlement-table-wrap">
              <el-table class="settlement-table" :data="pagedPurchaseSettlementRows" stripe table-layout="fixed">
                <el-table-column prop="document_no" label="書類番号" width="180" />
                <el-table-column prop="partner_name" label="会社名" width="190" />
                <el-table-column label="合計" width="130"><template #default="{ row }">{{ money(row.total) }}</template></el-table-column>
                <el-table-column label="支払済み" width="120"><template #default="{ row }"><el-switch v-model="row.settlement_confirmed" :disabled="!canEditSettlement" /></template></el-table-column>
                <el-table-column label="実払額" width="160"><template #default="{ row }"><el-input-number v-model="row.settlement_actual_amount" class="table-number-input" :min="0" :controls="false" :disabled="!canEditSettlement" /></template></el-table-column>
                <el-table-column label="計上額" width="140"><template #default="{ row }">{{ money(row.settlement_confirmed ? row.settlement_actual_amount : 0) }}</template></el-table-column>
                <el-table-column v-if="canEditSettlement" label="操作" width="90"><template #default="{ row }"><el-button text type="primary" :icon="Save" @click="updateSettlementDocument(row)" /></template></el-table-column>
              </el-table>
            </div>
            <TablePager v-model:page="purchaseSettlementPager.page" v-model:page-size="purchaseSettlementPager.pageSize" :total="purchaseSettlementRows.length" />
          </section>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="partnerDialog" :title="editingPartnerId ? '会社編集' : '会社追加'" width="680px">
      <el-form ref="partnerFormRef" :model="partnerForm" :rules="partnerRules" label-position="top" class="form-grid">
        <el-form-item label="会社名" prop="company_name"><el-input v-model="partnerForm.company_name" /></el-form-item>
        <el-form-item label="会社カナ"><el-input v-model="partnerForm.company_kana" /></el-form-item>
        <el-form-item label="区分" prop="partner_type">
          <el-select v-model="partnerForm.partner_type">
            <el-option label="上流・協力会社" value="both" />
            <el-option label="上流会社" value="upstream" />
            <el-option label="協力会社" value="downstream" />
          </el-select>
        </el-form-item>
        <el-form-item label="締結日"><el-date-picker v-model="partnerForm.contracted_at" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="契約終了日"><el-date-picker v-model="partnerForm.contract_end_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="解約済み"><el-switch v-model="partnerForm.terminated" active-text="はい" inactive-text="いいえ" /></el-form-item>
        <el-form-item label="担当者"><el-input v-model="partnerForm.contact_name" /></el-form-item>
        <el-form-item label="メール" prop="email"><el-input v-model="partnerForm.email" /></el-form-item>
        <el-form-item label="電話"><el-input v-model="partnerForm.phone" /></el-form-item>
        <el-form-item label="関連人員"><el-input v-model="partnerForm.related_people" /></el-form-item>
        <el-form-item label="住所" class="span-2"><el-input v-model="partnerForm.address" /></el-form-item>
        <el-form-item label="備考" class="span-2"><el-input v-model="partnerForm.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="partnerDialog = false">キャンセル</el-button><el-button type="primary" :icon="Save" @click="savePartner">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="contractDialog" :title="editingContractId ? '契約編集' : '新規契約'" width="620px">
      <el-form ref="contractFormRef" :model="contractForm" :rules="contractRules" label-position="top" class="form-grid">
        <el-form-item label="会社名" prop="company_name"><el-input v-model="contractForm.company_name" :disabled="Boolean(editingContractId)" /></el-form-item>
        <el-form-item label="区分" prop="direction">
          <el-select v-model="contractForm.direction">
            <el-option label="上流・協力会社" value="both" />
            <el-option label="協力会社" value="downstream" />
            <el-option label="上流会社" value="upstream" />
          </el-select>
        </el-form-item>
        <el-form-item label="タイトル" prop="title"><el-input v-model="contractForm.title" /></el-form-item>
        <el-form-item label="担当者"><el-input v-model="contractForm.contact_name" /></el-form-item>
        <el-form-item label="メール" prop="email"><el-input v-model="contractForm.email" /></el-form-item>
        <el-form-item label="電話"><el-input v-model="contractForm.phone" /></el-form-item>
        <el-form-item label="締結成功"><el-switch v-model="contractForm.contracted_success" active-text="はい" inactive-text="いいえ" /></el-form-item>
        <el-form-item label="締結日"><el-date-picker v-model="contractForm.contracted_at" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="備考" class="span-2"><el-input v-model="contractForm.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="contractDialog = false">キャンセル</el-button><el-button type="primary" :icon="Save" @click="saveContract">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="uploadDialog" title="上位契約アップロード" width="560px">
      <el-form ref="uploadFormRef" :model="uploadForm" :rules="uploadRules" label-position="top">
        <el-form-item label="締結済み会社を使用">
          <el-switch v-model="uploadUseExisting" active-text="はい" inactive-text="いいえ" />
        </el-form-item>
        <el-form-item v-if="uploadUseExisting" label="会社名" prop="partner_id">
          <el-select v-model="uploadForm.partner_id" filterable>
            <el-option v-for="partner in upstreamPartners" :key="partner.value" :label="partner.label" :value="partner.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="会社名" prop="company_name">
          <el-input v-model="uploadForm.company_name" />
        </el-form-item>
        <el-form-item label="区分">
          <el-select v-model="uploadForm.direction">
            <el-option label="上流会社" value="upstream" />
            <el-option label="協力会社" value="downstream" />
            <el-option label="上流・協力会社" value="both" />
          </el-select>
        </el-form-item>
        <el-form-item label="タイトル" prop="title"><el-input v-model="uploadForm.title" /></el-form-item>
        <el-form-item label="締結日"><el-date-picker v-model="uploadForm.contracted_at" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="ファイル" prop="files">
          <el-upload multiple :auto-upload="false" :on-change="(_file, fileList) => { uploadForm.files = fileList.map((item) => item.raw).filter(Boolean); uploadFormRef?.clearValidate('files') }" :on-remove="(_file, fileList) => { uploadForm.files = fileList.map((item) => item.raw).filter(Boolean) }">
            <el-button :icon="Upload">アップロード</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="uploadDialog = false">キャンセル</el-button><el-button type="primary" @click="uploadContract">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.loop-warning {
  margin: 12px 0;
}

.single-route-tabs :deep(.el-tabs__header) {
  display: none;
}

.settings-panel {
  max-width: 980px;
}

.settlement-detail-panel {
  min-width: 0;
}

.settlement-table-wrap {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.settlement-table {
  min-width: 1010px;
}
</style>

