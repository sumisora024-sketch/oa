<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Building2, CalendarDays, Download, FileText, Mail, MapPin, MessageCircle, Pencil, RefreshCw, Send, ShieldCheck, Sparkles, TrainFront, UserRound, X } from 'lucide-vue-next'
import { api } from '../api/client'

const { t, locale } = useI18n()
const router = useRouter()
const data = ref(null)
const salaryDialog = ref(false)
const salaryMonth = ref(currentMonth())
const selectedSalary = ref(null)
const assistantOpen = ref(false)
const assistantConfig = ref({ enabled: false, title: 'NIT AI Assistant', greeting: '' })
const assistantMessages = ref([])
const assistantInput = ref('')
const assistantConversationId = ref(null)
const assistantLoading = ref(false)
const assistantBodyRef = ref(null)

const currentContract = computed(() => data.value?.current_contract || null)
const salary = computed(() => selectedSalary.value || data.value?.salary || null)
const salaryDetail = computed(() => salary.value?.calculation_detail || {})
const salaryAnnual = computed(() => salary.value?.estimated_annual_salary ?? data.value?.employee?.estimated_annual_salary ?? null)
const salaryPaymentItems = computed(() => normalizeMoneyItems(salaryDetail.value.payment_items, [
  { key: 'base_salary', label: t('fields.baseSalary'), amount: salaryValue('base_salary', 0) },
  { key: 'allowance_total', label: t('fields.allowanceTotal'), amount: salaryDetail.value.payroll_allowance_total ?? salaryDetail.value.allowance_total ?? 0 },
  { key: 'reimbursement_amount', label: t('fields.reimbursementAmount'), amount: salaryValue('reimbursement_amount', 0) },
  { key: 'other_payment', label: 'その他支給', amount: salaryValue('other_payment', 0) }
]))
const salaryDeductionItems = computed(() => normalizeMoneyItems(salaryDetail.value.deduction_items, [
  { key: 'health_insurance', label: '健康保険', amount: salaryValue('health_insurance', 0) },
  { key: 'pension', label: t('fields.pension'), amount: salaryValue('pension', 0) },
  { key: 'employment_insurance', label: '雇用保険', amount: salaryValue('employment_insurance', 0) },
  { key: 'income_tax', label: '所得税', amount: salaryValue('income_tax', 0) },
  { key: 'resident_tax', label: t('fields.residentTax'), amount: salaryValue('resident_tax', 0) },
  { key: 'other_deduction', label: 'その他控除', amount: salaryValue('other_deduction', 0) }
]))
const isPartner = computed(() => data.value?.user?.role === 'partner')
const profile = computed(() => data.value?.company_profile || {})
const assistantStatusText = computed(() => assistantConfig.value.enabled ? t('home.assistantOnline') : t('home.assistantOffline'))
const assistantSuggestions = computed(() => [
  t('home.assistantSuggestionPeople'),
  t('home.assistantSuggestionExpense'),
  t('home.assistantSuggestionContract')
])

async function load() {
  const res = await api.get('/homepage')
  data.value = res.data
  selectedSalary.value = res.data.salary
  salaryMonth.value = res.data.salary?.year_month || currentMonth()
  try {
    assistantConfig.value = (await api.get('/ai-assistant/config')).data
    resetAssistantConversation()
  } catch {
    assistantConfig.value = { enabled: false, title: 'NIT AI Assistant', greeting: '' }
    resetAssistantConversation()
  }
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

async function loadSalaryMonth() {
  const { data } = await api.get('/contracts/salaries/self', { params: { year_month: salaryMonth.value } })
  selectedSalary.value = data
}

function displayEndDate(value) {
  return value === '9999-12-31' ? t('contracts.longTerm') : value || '-'
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function salaryValue(key, fallback = null) {
  const current = salary.value || {}
  const detail = salaryDetail.value || {}
  return current[key] ?? detail[key] ?? fallback
}

function normalizeMoneyItems(items, fallbackItems) {
  const source = Array.isArray(items) && items.length ? items : fallbackItems
  return source.map((item) => ({
    key: item.key || item.label,
    label: item.label || item.key || '-',
    amount: Number(item.amount || 0)
  }))
}

function download(url) {
  if (url) window.open(url, '_blank')
}

function salaryPdfUrl(kind) {
  if (!salary.value?.id) return null
  const version = encodeURIComponent(salary.value.updated_at || Date.now())
  return kind === 'annual'
    ? `/api/contracts/salaries/${salary.value.id}/annual-estimate.pdf?v=${version}`
    : `/api/contracts/salaries/${salary.value.id}/payslip.pdf?v=${version}`
}

function difyLanguage(value) {
  const text = String(value || '').toLowerCase()
  if (text.startsWith('zh')) return 'zh-CN'
  return 'ja-JP'
}

function resetAssistantConversation() {
  assistantConversationId.value = null
  assistantMessages.value = [{ role: 'assistant', content: assistantConfig.value.greeting || t('home.assistantGreeting') }]
}

async function scrollAssistantToBottom() {
  await nextTick()
  if (assistantBodyRef.value) {
    assistantBodyRef.value.scrollTop = assistantBodyRef.value.scrollHeight
  }
}

async function sendAssistantMessage(presetMessage = '') {
  const message = String(presetMessage || assistantInput.value).trim()
  if (!message || assistantLoading.value) return
  if (!assistantConfig.value.enabled) {
    assistantMessages.value.push({ role: 'assistant', content: t('home.assistantOfflineHint') })
    await scrollAssistantToBottom()
    return
  }
  assistantMessages.value.push({ role: 'user', content: message })
  assistantInput.value = ''
  assistantLoading.value = true
  await scrollAssistantToBottom()
  try {
    const response = await api.post('/ai-assistant/chat', {
      message,
      conversation_id: assistantConversationId.value,
      inputs: {
        language: difyLanguage(locale.value),
        user_role: data.value?.user?.role,
        user_name: data.value?.user?.full_name,
        partner_company: data.value?.partner?.company_name || ''
      }
    })
    const result = response.data
    assistantConversationId.value = result.conversation_id || assistantConversationId.value
    assistantMessages.value.push({
      role: 'assistant',
      content: result.answer || '-',
      sources: result.sources || []
    })
  } catch (error) {
    assistantMessages.value.push({ role: 'assistant', content: error.response?.data?.detail || t('home.assistantError') })
  } finally {
    assistantLoading.value = false
    await scrollAssistantToBottom()
  }
}

onMounted(load)
</script>

<template>
  <div class="page" v-if="data">
    <template v-if="isPartner">
      <section class="portal-hero partner-hero">
        <div>
          <p class="portal-eyebrow">NIT Partner Portal</p>
          <h1>{{ profile.company_name }}</h1>
          <p>{{ t('home.partnerHero') }}</p>
          <div class="hero-actions">
            <el-button type="primary" @click="router.push('/subcontracting')">{{ t('nav.subcontracting') }}</el-button>
          </div>
        </div>
        <div class="partner-card">
          <Building2 :size="28" />
          <strong>{{ data.partner?.company_name || data.user.full_name }}</strong>
          <span>{{ data.partner?.partner_type || 'partner' }}</span>
        </div>
      </section>

      <section class="service-grid">
        <article v-for="service in profile.services || []" :key="service.title" class="service-tile">
          <Sparkles :size="18" />
          <h3>{{ service.title }}</h3>
          <p>{{ service.description }}</p>
        </article>
      </section>

      <section class="portal-band">
        <div class="contact-lines">
          <div><MapPin :size="16" />{{ profile.address }}</div>
          <div><Mail :size="16" />{{ profile.email }}</div>
        </div>
        <el-button @click="download(profile.url)">{{ profile.url }}</el-button>
      </section>
    </template>

    <template v-else>
      <section class="portal-hero">
        <div>
          <p class="portal-eyebrow">NIT OA system</p>
          <h1>{{ t('home.welcome') }} {{ data.employee?.full_name || data.user.full_name }}</h1>
          <p>{{ t('home.heroCopy') }}</p>
        </div>
        <div class="hero-metrics">
          <div>
            <span>{{ t('fields.actualSalary') }}</span>
            <strong>{{ money(data.salary?.actual_salary) }}</strong>
          </div>
          <div>
            <span>{{ t('fields.estimatedAnnualSalary') }}</span>
            <strong>{{ money(data.employee?.estimated_annual_salary) }}</strong>
          </div>
        </div>
      </section>

      <section class="home-dashboard">
        <article class="home-panel profile-panel">
          <div class="panel-title-row">
            <h3>{{ t('home.profile') }}</h3>
            <el-button v-if="data.employee" text type="primary" :icon="Pencil" @click="router.push('/profile')">{{ t('common.edit') }}</el-button>
          </div>
          <template v-if="data.employee">
            <div class="fact"><UserRound :size="16" /> {{ data.employee.full_name }}</div>
            <div class="fact"><Mail :size="16" /> {{ data.employee.email }}</div>
            <div class="fact"><MapPin :size="16" /> {{ data.employee.residence || '-' }}</div>
            <div class="fact"><TrainFront :size="16" /> {{ data.employee.nearest_station || '-' }}</div>
          </template>
          <div v-else class="muted">{{ t('home.contactAdmin') }}</div>
        </article>

        <article class="home-panel">
          <h3>{{ t('home.contracts') }}</h3>
          <div v-if="!currentContract" class="muted">{{ t('home.contactAdmin') }}</div>
          <div v-else class="status-card">
            <FileText :size="18" />
            <div>
              <strong>{{ currentContract.contract_type || '-' }}</strong>
              <span>{{ displayEndDate(currentContract.end_date) }}</span>
            </div>
          </div>
        </article>

        <article class="home-panel salary-panel" @click="salaryDialog = true">
          <h3>{{ t('home.salary') }}</h3>
          <div v-if="!data.salary" class="muted">{{ t('home.contactAdmin') }}</div>
          <template v-else>
            <div class="salary-big">{{ money(data.salary.actual_salary) }}</div>
            <div class="salary-sub">{{ data.salary.year_month }} · {{ t('fields.reimbursementAmount') }} {{ money(data.salary.reimbursement_amount) }}</div>
          </template>
        </article>

        <article class="home-panel">
          <h3>{{ t('home.projects') }}</h3>
          <div v-if="!data.projects.length" class="muted">{{ t('home.noData') }}</div>
          <div v-for="project in data.projects" :key="project.id" class="list-row">
            <CalendarDays :size="16" />
            <span>{{ project.project_name }}</span>
            <small>{{ project.workplace }}</small>
          </div>
        </article>
      </section>
    </template>

    <el-dialog v-model="salaryDialog" :title="t('home.salaryDetail')" width="680px">
      <div class="toolbar section-toolbar">
        <el-date-picker v-model="salaryMonth" type="month" value-format="YYYY-MM" :clearable="false" @change="loadSalaryMonth" />
        <el-button :icon="Download" :disabled="!salary?.id" @click="download(salaryPdfUrl('salary'))">{{ t('home.downloadPayslip') }}</el-button>
        <el-button :icon="Download" :disabled="!salary?.id" @click="download(salaryPdfUrl('annual'))">{{ t('home.downloadAnnual') }}</el-button>
      </div>
      <template v-if="salary">
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="t('fields.yearMonth')">{{ salary.year_month }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.monthlyHours')">{{ salary.monthly_hours ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.hoursRange')">{{ salaryValue('hours_range', '140-180') }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.baseUnitPriceLow')">{{ money(salaryValue('base_unit_price_low')) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.baseUnitPriceHigh')">{{ money(salaryValue('base_unit_price_high')) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.estimatedSalary')">{{ money(salaryValue('estimated_salary')) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.reimbursementAmount')">{{ money(salaryValue('reimbursement_amount', 0)) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.grossPaymentTotal')">{{ money(salaryValue('gross_payment_total', 0)) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.deductionTotal')">{{ money(salaryValue('deduction_total', 0)) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.actualSalary')">{{ money(salary.actual_salary) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.estimatedAnnualSalary')">{{ money(salaryAnnual) }}</el-descriptions-item>
          <el-descriptions-item :label="t('fields.locked')">
            <ShieldCheck :size="15" /> {{ salary.locked ? t('common.yes') : t('common.no') }}
          </el-descriptions-item>
        </el-descriptions>
        <p class="salary-detail-note">{{ t('home.salaryCalculationNote') }}</p>
        <div class="salary-detail-grid">
          <section>
            <h4>{{ t('home.paymentItems') }}</h4>
            <el-table :data="salaryPaymentItems" size="small" border>
              <el-table-column prop="label" :label="t('common.detail')" />
              <el-table-column :label="t('fields.amount')" width="150" align="right">
                <template #default="{ row }">{{ money(row.amount) }}</template>
              </el-table-column>
            </el-table>
          </section>
          <section>
            <h4>{{ t('home.deductionItems') }}</h4>
            <el-table :data="salaryDeductionItems" size="small" border>
              <el-table-column prop="label" :label="t('common.detail')" />
              <el-table-column :label="t('fields.amount')" width="150" align="right">
                <template #default="{ row }">{{ money(row.amount) }}</template>
              </el-table-column>
            </el-table>
          </section>
        </div>
      </template>
    </el-dialog>

    <div class="assistant-widget" :class="{ open: assistantOpen }">
      <button v-if="!assistantOpen" class="assistant-bubble" type="button" @click="assistantOpen = true">
        <MessageCircle :size="22" />
      </button>
      <section v-else class="assistant-panel">
        <header>
          <div>
            <strong>{{ assistantConfig.title || 'NIT AI Assistant' }}</strong>
            <span>{{ assistantStatusText }}</span>
          </div>
          <div class="assistant-header-actions">
            <button type="button" :title="t('home.assistantNewChat')" @click="resetAssistantConversation"><RefreshCw :size="16" /></button>
            <button type="button" @click="assistantOpen = false"><X :size="18" /></button>
          </div>
        </header>
        <div ref="assistantBodyRef" class="assistant-messages">
          <div v-for="(message, index) in assistantMessages" :key="index" :class="['assistant-message', message.role]">
            <p>{{ message.content }}</p>
            <div v-if="message.sources?.length" class="assistant-sources">
              <span>{{ t('home.assistantSources') }}</span>
              <small v-for="source in message.sources" :key="source.title">{{ source.title }}</small>
            </div>
          </div>
          <div v-if="assistantMessages.length <= 1" class="assistant-suggestions">
            <button v-for="suggestion in assistantSuggestions" :key="suggestion" type="button" @click="sendAssistantMessage(suggestion)">
              {{ suggestion }}
            </button>
          </div>
        </div>
        <form class="assistant-input" @submit.prevent="sendAssistantMessage">
          <el-input v-model="assistantInput" :placeholder="t('home.assistantPlaceholder')" :disabled="assistantLoading || !assistantConfig.enabled" />
          <el-button type="primary" :icon="Send" native-type="submit" :loading="assistantLoading" :disabled="!assistantConfig.enabled" circle />
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.portal-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
  gap: 24px;
  align-items: stretch;
  min-height: 220px;
  padding: 28px;
  color: #102027;
  background: linear-gradient(135deg, #f7faf9 0%, #e9f2ef 58%, #d8e6df 100%);
  border: 1px solid #d7e0dc;
  border-radius: 8px;
}

.portal-hero h1 {
  max-width: 760px;
  margin: 0 0 12px;
  font-size: 34px;
  line-height: 1.2;
}

.portal-hero p {
  max-width: 680px;
  margin: 0;
  color: #50606b;
  line-height: 1.7;
}

.portal-eyebrow {
  margin: 0 0 10px !important;
  color: #2f6f73 !important;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.hero-metrics,
.partner-card {
  display: grid;
  align-content: center;
  gap: 12px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(255, 255, 255, 0.86);
  border-radius: 8px;
}

.hero-metrics div {
  display: grid;
  gap: 4px;
}

.hero-metrics span,
.salary-sub {
  color: #697781;
  font-size: 13px;
}

.hero-metrics strong,
.salary-big {
  color: #15242c;
  font-size: 28px;
  font-weight: 800;
}

.home-dashboard,
.service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.home-panel,
.service-tile,
.portal-band {
  background: #fff;
  border: 1px solid #d9dfdc;
  border-radius: 8px;
  padding: 18px;
}

.home-panel h3,
.service-tile h3 {
  margin: 0 0 14px;
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-title-row h3 {
  margin: 0;
}

.salary-panel {
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}

.salary-panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(21, 36, 44, 0.1);
}

.salary-detail-note {
  margin: 12px 0 0;
  color: #697781;
  font-size: 12px;
  line-height: 1.6;
}

.salary-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.salary-detail-grid h4 {
  margin: 0 0 8px;
  color: #15242c;
}

.status-card {
  display: flex;
  gap: 12px;
  align-items: center;
}

.status-card div,
.partner-card {
  display: grid;
}

.status-card span,
.partner-card span {
  color: #697781;
  font-size: 13px;
}

.service-tile p {
  margin: 0;
  color: #697781;
  line-height: 1.65;
}

.portal-band {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}

.contact-lines {
  display: grid;
  gap: 8px;
}

.contact-lines div {
  display: flex;
  gap: 8px;
  align-items: center;
}

.hero-actions {
  margin-top: 22px;
}

.assistant-widget {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 10;
}

.assistant-bubble {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, #1b83d7, #20c5d8 58%, #70d756);
  border: 0;
  border-radius: 50%;
  box-shadow: 0 18px 38px rgba(19, 71, 88, 0.28);
  cursor: pointer;
}

.assistant-panel {
  width: min(360px, calc(100vw - 32px));
  overflow: hidden;
  background: #fff;
  border: 1px solid #d9dfdc;
  border-radius: 8px;
  box-shadow: 0 22px 58px rgba(20, 42, 52, 0.2);
}

.assistant-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  color: #fff;
  background: #173f4a;
}

.assistant-panel header div {
  display: grid;
  gap: 2px;
}

.assistant-panel header span {
  color: #b9d4d9;
  font-size: 12px;
}

.assistant-header-actions {
  display: flex !important;
  align-items: center;
  gap: 6px !important;
}

.assistant-panel header button {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  color: inherit;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.assistant-panel header button:hover {
  background: rgba(255, 255, 255, 0.12);
}

.assistant-messages {
  max-height: 320px;
  display: grid;
  gap: 10px;
  padding: 14px;
  overflow: auto;
  background: #f6f8f7;
}

.assistant-message {
  max-width: 86%;
  padding: 9px 11px;
  border-radius: 8px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.assistant-message p {
  margin: 0;
}

.assistant-message.assistant {
  justify-self: start;
  background: #fff;
  border: 1px solid #d9dfdc;
}

.assistant-message.user {
  justify-self: end;
  color: #fff;
  background: #2f6f73;
}

.assistant-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  color: #5f717a;
  font-size: 12px;
}

.assistant-sources span {
  width: 100%;
  font-weight: 700;
}

.assistant-sources small {
  max-width: 150px;
  padding: 2px 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: #edf4f2;
  border-radius: 999px;
}

.assistant-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.assistant-suggestions button {
  padding: 7px 10px;
  color: #23535b;
  background: #eef6f4;
  border: 1px solid #d4e4df;
  border-radius: 999px;
  cursor: pointer;
}

.assistant-suggestions button:hover {
  background: #e0f0ec;
}

.assistant-input {
  display: flex;
  gap: 8px;
  padding: 12px;
  background: #fff;
}

@media (max-width: 900px) {
  .portal-hero,
  .portal-band {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .portal-hero h1 {
    font-size: 26px;
  }
}
</style>
