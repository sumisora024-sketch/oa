<script setup>
import { computed, onMounted, ref } from 'vue'
import { Download, RefreshCw, Search, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'

const rows = ref([])
const q = ref('')
const documentType = ref('')
const loading = ref(false)

const typeOptions = computed(() => {
  const values = Array.from(new Set(rows.value.map((row) => row.document_type).filter(Boolean)))
  return values.sort().map((value) => ({ label: documentTypeLabel(value), value }))
})
const filteredRows = computed(() => {
  const text = q.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    const typeOk = !documentType.value || row.document_type === documentType.value
    if (!typeOk) return false
    if (!text) return true
    return [
      row.source,
      documentTypeLabel(row.document_type),
      row.name,
      row.owner_name,
      row.partner_name,
      row.employee_name,
      row.target_month,
      row.directory_path,
      row.status,
      row.amount
    ].some((value) => String(value || '').toLowerCase().includes(text))
  })
})
const { pager, pageRows } = usePagination(filteredRows)

function documentTypeLabel(value) {
  const labels = {
    purchase_order: '発注書',
    quotation: '見積書',
    invoice: '請求書',
    uploaded_contract: 'アップロード契約',
    partner_quotation: 'パートナー見積書',
    partner_invoice: 'パートナー請求書',
    reimbursement: '経費証憑',
    resume: '履歴書',
    avatar: '顔写真',
    timesheet: '勤務表',
    document: '書類',
    'nit-3': 'NIT-3',
    'nit-4': 'NIT-4'
  }
  return labels[value] || value
}

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  return Number(value).toLocaleString()
}

function download(url) {
  if (url) window.open(url, '_blank')
}

async function load() {
  loading.value = true
  try {
    rows.value = (await api.get('/documents')).data
  } finally {
    loading.value = false
  }
}

async function deleteRow(row) {
  try {
    await ElMessageBox.confirm('この書類を管理一覧から削除しますか？', '削除', { type: 'warning' })
    await api.delete('/documents/items', { params: { key: row.key } })
    ElMessage.success('削除しました')
    await load()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(detail || '削除に失敗しました')
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>書類管理</h2>
      <div class="toolbar">
        <el-input v-model="q" :prefix-icon="Search" placeholder="書類名、会社名、社員名で検索" clearable style="width: 280px" />
        <el-select v-model="documentType" placeholder="種別" clearable style="width: 180px">
          <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button :icon="RefreshCw" @click="load">更新</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="pageRows" height="calc(100vh - 275px)" stripe>
      <el-table-column prop="source" label="出所" min-width="130" sortable />
      <el-table-column label="書類種別" min-width="150" sortable>
        <template #default="{ row }">{{ documentTypeLabel(row.document_type) }}</template>
      </el-table-column>
      <el-table-column prop="name" label="書類名" min-width="260" show-overflow-tooltip sortable />
      <el-table-column prop="partner_name" label="会社" min-width="190" show-overflow-tooltip sortable />
      <el-table-column prop="employee_name" label="社員/人員" min-width="160" show-overflow-tooltip sortable />
      <el-table-column prop="target_month" label="対象年月" width="120" sortable />
      <el-table-column prop="directory_path" label="保存先" min-width="180" show-overflow-tooltip sortable />
      <el-table-column prop="status" label="状態" width="120" sortable />
      <el-table-column label="金額" width="130" sortable>
        <template #default="{ row }">{{ money(row.amount) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="登録日時" min-width="170" sortable />
      <el-table-column fixed="right" label="操作" width="120">
        <template #default="{ row }">
          <el-button text type="primary" :icon="Download" @click="download(row.download_url)" />
          <el-button text type="danger" :icon="Trash2" @click="deleteRow(row)" />
        </template>
      </el-table-column>
    </el-table>
    <TablePager v-model:page="pager.page" v-model:page-size="pager.pageSize" :total="filteredRows.length" />
  </div>
</template>
