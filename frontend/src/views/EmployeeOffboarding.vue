<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Download, Plus, RefreshCw, Search, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { downloadCsv as exportCsv } from '../utils/csv'

const auth = useAuthStore()
const rows = ref([])
const employees = ref([])
const selectedRows = ref([])
const q = ref('')
const dialog = ref(false)
const formRef = ref(null)
const loading = ref(false)

const canManage = computed(() => ['admin', 'hr'].includes(auth.user?.role))
const reasonOptions = ['自己都合', '会社都合', '契約終了', 'その他']
const form = reactive(defaultForm())
const filteredRows = computed(() => {
  const text = q.value.trim().toLowerCase()
  if (!text) return rows.value
  return rows.value.filter((row) => [
    row.full_name,
    row.email,
    row.phone,
    row.resignation_reason,
    row.status,
    row.final_salary_month
  ].some((value) => String(value || '').toLowerCase().includes(text)))
})
const selectedPendingRows = computed(() => selectedRows.value.filter((row) => row.status === 'pending'))
const { pager, pageRows } = usePagination(filteredRows)

const requiredRule = { required: true, message: '必須項目です', trigger: 'change' }
const rules = {
  employee_id: [requiredRule],
  resignation_date: [requiredRule],
  resignation_reason: [requiredRule],
  final_salary_month: [requiredRule]
}

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function defaultForm() {
  return {
    employee_id: null,
    resignation_date: '',
    last_work_date: '',
    resignation_reason: '自己都合',
    reason_detail: '',
    handover_note: '',
    final_salary_month: currentMonth(),
    final_salary_hours: null,
    final_salary_amount: null,
    final_salary_note: ''
  }
}

function resetForm() {
  Object.assign(form, defaultForm())
  if (!canManage.value) form.employee_id = auth.user?.employee_id || null
  formRef.value?.clearValidate()
}

function statusType(status) {
  return {
    pending: 'warning',
    scheduled: 'primary',
    approved: 'success',
    completed: 'info',
    rejected: 'danger',
    cancelled: 'info'
  }[status] || 'info'
}

function statusLabel(status) {
  return {
    pending: '承認待ち',
    scheduled: '予定',
    approved: '承認済み',
    completed: '完了',
    rejected: '却下',
    cancelled: '取消済み'
  }[status] || status
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

async function load() {
  loading.value = true
  try {
    rows.value = (await api.get('/offboardings')).data
    if (canManage.value) {
      employees.value = (await api.get('/employees')).data
    }
  } finally {
    loading.value = false
  }
}

function normalizePayload() {
  const payload = { ...form }
  Object.keys(payload).forEach((key) => {
    if (payload[key] === '') payload[key] = null
  })
  if (!canManage.value) payload.employee_id = auth.user?.employee_id
  return payload
}

async function submit() {
  try {
    await formRef.value?.validate()
    await api.post('/offboardings', normalizePayload())
    ElMessage.success('退職申請を提出しました')
    dialog.value = false
    await load()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || '処理に失敗しました')
  }
}

async function cancel(row) {
  try {
    await ElMessageBox.confirm('この退職申請を取り消しますか？', '取消', { type: 'warning' })
    await api.delete(`/offboardings/${row.id}`)
    ElMessage.success('取り消しました')
    await load()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(detail || '処理に失敗しました')
  }
}

async function deleteSelected() {
  if (!selectedRows.value.length) return
  if (!selectedPendingRows.value.length) {
    ElMessage.warning('削除できるのは承認待ちの退職申請のみです')
    return
  }
  try {
    const skipped = selectedRows.value.length - selectedPendingRows.value.length
    const message = skipped
      ? `${selectedPendingRows.value.length}件を削除します。${skipped}件は承認待ちではないため対象外です。`
      : `${selectedPendingRows.value.length}件を削除します。`
    await ElMessageBox.confirm(message, '削除', { type: 'warning' })
    await Promise.all(selectedPendingRows.value.map((row) => api.delete(`/offboardings/${row.id}`)))
    selectedRows.value = []
    ElMessage.success('削除しました')
    await load()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(detail || '処理に失敗しました')
  }
}

function downloadSelected() {
  const result = exportCsv(selectedRows.value, [
    { key: 'full_name', label: '氏名' },
    { key: 'email', label: 'メール' },
    { key: 'phone', label: '電話' },
    { key: 'residence', label: '住所' },
    { key: 'resignation_date', label: '退職日' },
    { key: 'last_work_date', label: '最終出勤日' },
    { key: 'resignation_reason', label: '退職理由' },
    { key: 'final_salary_month', label: '最終給与月' },
    { key: 'final_salary_hours', label: '最終月工数' },
    { key: 'final_salary_amount', label: '最終給与上書き額' },
    { label: '状態', value: (row) => statusLabel(row.status) },
    { key: 'approver_name', label: '承認者' }
  ], 'offboarding-selected.csv')
  if (!result.ok) ElMessage.warning(result.message)
}

onMounted(async () => {
  resetForm()
  await load()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>退職</h2>
      <div class="toolbar">
        <el-input v-model="q" :prefix-icon="Search" placeholder="検索" clearable style="width: 240px" />
        <span v-if="selectedRows.length" class="muted">{{ selectedRows.length }} 件選択中</span>
        <el-button type="danger" :icon="Trash2" :disabled="!selectedRows.length" @click="deleteSelected">選択行を削除</el-button>
        <el-button :icon="Download" :disabled="!selectedRows.length" @click="downloadSelected">選択行をダウンロード</el-button>
        <el-button :icon="RefreshCw" @click="load">更新</el-button>
        <el-button type="primary" :icon="Plus" @click="resetForm(); dialog = true">退職申請</el-button>
      </div>
    </div>

    <el-table :data="pageRows" v-loading="loading" height="calc(100vh - 280px)" stripe @selection-change="selectedRows = $event">
      <el-table-column type="selection" width="46" />
      <el-table-column prop="full_name" label="氏名" min-width="150" sortable />
      <el-table-column prop="email" label="メール" min-width="210" sortable />
      <el-table-column prop="phone" label="電話" min-width="130" />
      <el-table-column prop="residence" label="住所" min-width="180" show-overflow-tooltip />
      <el-table-column prop="resignation_date" label="退職日" width="120" sortable />
      <el-table-column prop="last_work_date" label="最終出勤日" width="130" sortable />
      <el-table-column prop="resignation_reason" label="退職理由" width="130" />
      <el-table-column prop="final_salary_month" label="最終給与月" width="130" sortable />
      <el-table-column prop="final_salary_hours" label="最終月工数" width="130" sortable />
      <el-table-column label="最終給与上書き額" width="150">
        <template #default="{ row }">{{ money(row.final_salary_amount) }}</template>
      </el-table-column>
      <el-table-column label="状態" width="120">
        <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="approver_name" label="承認者" min-width="130" />
      <el-table-column fixed="right" label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" text type="danger" :icon="Trash2" @click="cancel(row)" />
        </template>
      </el-table-column>
    </el-table>
    <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="filteredRows.length" />

    <el-dialog v-model="dialog" title="退職申請" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item v-if="canManage" label="対象社員" prop="employee_id">
          <el-select v-model="form.employee_id" filterable>
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.full_name" :value="employee.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="退職日" prop="resignation_date"><el-date-picker v-model="form.resignation_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="最終出勤日"><el-date-picker v-model="form.last_work_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="退職理由" prop="resignation_reason">
          <el-select v-model="form.resignation_reason">
            <el-option v-for="option in reasonOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="最終給与月" prop="final_salary_month"><el-date-picker v-model="form.final_salary_month" type="month" value-format="YYYY-MM" /></el-form-item>
        <el-form-item label="最終月工数"><el-input-number v-model="form.final_salary_hours" :min="0" :step="0.5" :controls="false" /></el-form-item>
        <el-form-item label="最終給与上書き額"><el-input-number v-model="form.final_salary_amount" :min="0" :controls="false" /></el-form-item>
        <el-form-item class="span-2" label="理由詳細"><el-input v-model="form.reason_detail" type="textarea" :rows="3" /></el-form-item>
        <el-form-item class="span-2" label="引き継ぎメモ"><el-input v-model="form.handover_note" type="textarea" :rows="3" /></el-form-item>
        <el-form-item class="span-2" label="最終給与メモ"><el-input v-model="form.final_salary_note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">キャンセル</el-button>
        <el-button type="primary" @click="submit">提出</el-button>
      </template>
    </el-dialog>
  </div>
</template>
