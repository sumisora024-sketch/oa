<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Bot, Columns3, Eye, Inbox, Pencil, Plus, RefreshCw, RotateCcw, Search, Sparkles, Trash2, UserMinus, UserPlus } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import TablePager from '../components/TablePager.vue'
import { usePagination } from '../composables/pagination'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const rows = ref([])
const employees = ref([])
const assignments = ref([])
const recommendations = ref([])
const selectedProject = ref(null)
const detailRow = ref(null)
const editingId = ref(null)
const dialog = ref(false)
const analyzeDialog = ref(false)
const assignDialog = ref(false)
const detailDrawer = ref(false)
const assignMode = ref('create')
const q = ref('')
const formRef = ref(null)
const emailFormRef = ref(null)
const assignFormRef = ref(null)
const form = reactive(defaultForm())
const emailForm = reactive({ subject: '', body: '', attachment_text: '' })
const assignForm = reactive({ assignment_id: null, project_id: null, employee_id: null, role: '', status: 'assigned' })
const nationalityRequirementOptions = ['日本籍のみ', '制限なし']
const visibleColumns = reactive({
  client_company: true,
  project_name: true,
  workplace: true,
  required_skills: true,
  headcount: true,
  assigned_employees: true,
  unit_price: true,
  nationality_requirement: true,
  duration: false,
  description: false,
  created_at: false
})
const columnOptions = [
  'client_company', 'project_name', 'workplace', 'required_skills', 'headcount', 'assigned_employees',
  'unit_price', 'nationality_requirement', 'duration', 'description', 'created_at'
]
const rules = computed(() => ({
  client_company: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  project_name: [{ required: true, message: t('validation.required'), trigger: 'blur' }],
  workplace: [{ required: true, message: t('validation.required'), trigger: 'blur' }]
}))
const emailRules = computed(() => ({
  body: [{ required: true, message: t('validation.required'), trigger: 'blur' }]
}))
const assignRules = computed(() => ({
  employee_id: [{ required: true, message: t('validation.required'), trigger: 'change' }]
}))
const filteredProjects = computed(() => {
  const text = q.value.trim().toLowerCase()
  if (!text) return rows.value
  return rows.value.filter((row) => [
    row.client_company,
    row.project_name,
    row.workplace,
    row.unit_price,
    row.nationality_requirement,
    ...(row.required_skills || [])
  ].some((value) => String(value || '').toLowerCase().includes(text)))
})
const { pager: projectPager, pageRows: pagedProjects } = usePagination(filteredProjects)
const { pager: recommendationPager, pageRows: pagedRecommendations } = usePagination(recommendations)

function defaultForm() {
  return { client_company: '', project_name: '', description: '', required_skills_text: '', workplace: '', nationality_requirement: '', duration: '', headcount: null, unit_price: '' }
}

function payload() {
  return {
    client_company: form.client_company,
    project_name: form.project_name,
    description: form.description,
    required_skills: (form.required_skills_text || '').split(/[,，、;\n]/).map((x) => x.trim()).filter(Boolean),
    workplace: form.workplace,
    nationality_requirement: form.nationality_requirement || null,
    duration: form.duration || null,
    headcount: form.headcount,
    unit_price: form.unit_price || null
  }
}

function columnLabel(key) {
  const labels = {
    client_company: t('fields.clientCompany'),
    project_name: t('fields.projectName'),
    workplace: t('fields.workplace'),
    required_skills: t('fields.requiredSkills'),
    headcount: t('fields.headcount'),
    assigned_employees: t('fields.assignedEmployees'),
    unit_price: t('fields.unitPrice'),
    nationality_requirement: t('fields.nationalityRequirement'),
    duration: t('fields.duration'),
    description: t('fields.description'),
    created_at: t('fields.createdAt')
  }
  return labels[key]
}

const projectAssignmentsById = computed(() => {
  const grouped = {}
  for (const assignment of assignments.value) {
    grouped[assignment.project_id] ||= []
    grouped[assignment.project_id].push(assignment)
  }
  return grouped
})

async function load() {
  rows.value = (await api.get('/projects')).data
  try {
    assignments.value = (await api.get('/projects/assignments')).data
  } catch {
    assignments.value = []
  }
  try {
    employees.value = (await api.get('/employees')).data
  } catch {
    employees.value = []
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  dialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    client_company: row.client_company,
    project_name: row.project_name,
    description: row.description,
    required_skills_text: (row.required_skills || []).join(', '),
    workplace: row.workplace,
    nationality_requirement: row.nationality_requirement || '',
    duration: row.duration || '',
    headcount: row.headcount,
    unit_price: row.unit_price || ''
  })
  dialog.value = true
}

async function save() {
  try {
    await formRef.value?.validate()
    if (editingId.value) {
      await api.put(`/projects/${editingId.value}`, payload())
    } else {
      await api.post('/projects', payload())
    }
    ElMessage.success(t('common.success'))
    dialog.value = false
    editingId.value = null
    await load()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  }
}

async function deleteProject(row) {
  try {
    await ElMessageBox.confirm(t('common.confirmDelete'), t('common.delete'), { type: 'warning' })
    await api.delete(`/projects/${row.id}`)
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(detail || t('common.failed'))
  }
}

async function analyze() {
  try {
    await emailFormRef.value?.validate()
    const { data } = await api.post('/projects/analyze-email', {
      subject: emailForm.subject || null,
      body: emailForm.body,
      attachment_text: emailForm.attachment_text || null
    })
    ElMessage.success(data.project_name)
    analyzeDialog.value = false
    await load()
  } catch (error) {
    const detail = error.response?.data?.detail
    if (detail) ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail)
  }
}

async function pollMailbox() {
  const { data } = await api.post('/projects/mailbox/poll')
  if (data.error) {
    ElMessage.error(data.error)
    return
  }
  ElMessage.success(`checked ${data.checked}, imported ${data.imported.length}`)
  await load()
}

async function recommend(row) {
  selectedProject.value = row
  recommendations.value = (await api.get(`/projects/${row.id}/recommendations`)).data
}

function assignedList(row) {
  return projectAssignmentsById.value[row.id] || []
}

function activeAssignedList(row) {
  return assignedList(row).filter((assignment) => assignment.status === 'assigned')
}

function assignedCount(row) {
  return activeAssignedList(row).length
}

function isFull(row) {
  return row.headcount !== null && row.headcount !== undefined && assignedCount(row) >= row.headcount
}

function openAssign(row) {
  if (isFull(row)) {
    ElMessage.warning(t('projects.assignmentFull'))
    return
  }
  selectedProject.value = row
  assignMode.value = 'create'
  Object.assign(assignForm, { assignment_id: null, project_id: row.id, employee_id: null, role: '', status: 'assigned' })
  assignDialog.value = true
}

function openReassign(row, assignment) {
  selectedProject.value = row
  assignMode.value = 'edit'
  Object.assign(assignForm, {
    assignment_id: assignment.id,
    project_id: assignment.project_id,
    employee_id: assignment.employee_id,
    role: assignment.role || '',
    status: 'assigned'
  })
  assignDialog.value = true
}

function openDetail(row) {
  detailRow.value = row
  detailDrawer.value = true
}

function textOrDash(value) {
  return value || '-'
}

function listText(value) {
  return Array.isArray(value) && value.length ? value.join(', ') : '-'
}

function percent(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function prettyJson(value) {
  return value ? JSON.stringify(value, null, 2) : '-'
}

function projectOptionLabel(project) {
  return [project.client_company, project.project_name].filter(Boolean).join(' / ')
}

async function assign() {
  try {
    await assignFormRef.value?.validate()
    const body = {
      employee_id: assignForm.employee_id,
      role: assignForm.role || null,
      status: 'assigned'
    }
    if (assignForm.assignment_id) {
      await api.put(`/projects/assignments/${assignForm.assignment_id}`, {
        ...body,
        project_id: assignForm.project_id
      })
    } else {
      await api.post(`/projects/${assignForm.project_id}/assignments`, body)
    }
    ElMessage.success(t('common.success'))
    assignDialog.value = false
    await load()
  } catch (error) {
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  }
}

async function unassign(row, assignment) {
  try {
    await ElMessageBox.confirm(t('projects.unassignConfirm'), t('projects.unassign'), { type: 'warning' })
    await api.delete(`/projects/assignments/${assignment.id}`)
    ElMessage.success(t('common.success'))
    await load()
  } catch (error) {
    if (error === 'cancel') return
    const detail = error.response?.data?.detail
    ElMessage.error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(' / ') : detail || t('common.failed'))
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ t('nav.projects') }}</h2>
      <div class="toolbar">
        <el-input v-model="q" :prefix-icon="Search" :placeholder="t('common.search')" clearable style="width: 240px" />
        <el-button :icon="RefreshCw" @click="load">{{ t('common.refresh') }}</el-button>
        <el-button v-if="auth.can('projects', 'create')" type="primary" :icon="Plus" @click="openCreate">{{ t('common.create') }}</el-button>
        <el-button v-if="auth.can('projects', 'create')" :icon="Bot" @click="analyzeDialog = true">{{ t('projects.analyzeEmail') }}</el-button>
        <el-button v-if="auth.can('projects', 'create')" :icon="Inbox" @click="pollMailbox">{{ t('projects.pollMailbox') }}</el-button>
        <el-popover placement="bottom-end" width="240" trigger="click">
          <template #reference>
            <el-button :icon="Columns3">{{ t('common.columns') }}</el-button>
          </template>
          <div class="column-menu">
            <el-checkbox v-for="column in columnOptions" :key="column" v-model="visibleColumns[column]">
              {{ columnLabel(column) }}
            </el-checkbox>
          </div>
        </el-popover>
      </div>
    </div>
    <el-table :data="pagedProjects" height="calc(100vh - 280px)" stripe>
      <el-table-column v-if="visibleColumns.client_company" prop="client_company" :label="t('fields.clientCompany')" min-width="180" sortable />
      <el-table-column v-if="visibleColumns.project_name" prop="project_name" :label="t('fields.projectName')" min-width="200" sortable />
      <el-table-column v-if="visibleColumns.workplace" prop="workplace" :label="t('fields.workplace')" min-width="180" sortable />
      <el-table-column v-if="visibleColumns.required_skills" prop="required_skills" :label="t('fields.requiredSkills')" min-width="220">
        <template #default="{ row }">{{ (row.required_skills || []).join(', ') }}</template>
      </el-table-column>
      <el-table-column v-if="visibleColumns.headcount" prop="headcount" :label="t('fields.headcount')" width="100" sortable />
      <el-table-column v-if="visibleColumns.assigned_employees" :label="t('fields.assignedEmployees')" min-width="260">
        <template #default="{ row }">
          <div class="assigned-list">
            <template v-if="activeAssignedList(row).length">
              <div v-for="assignment in activeAssignedList(row)" :key="assignment.id" class="assignment-chip">
                <el-tag size="small" effect="plain">{{ assignment.employee_name }}</el-tag>
                <div v-if="auth.can('projects', 'update')" class="assignment-chip-actions">
                  <el-tooltip :content="t('projects.reassign')" placement="top">
                    <el-button text size="small" :icon="RotateCcw" @click="openReassign(row, assignment)" />
                  </el-tooltip>
                  <el-tooltip :content="t('projects.unassign')" placement="top">
                    <el-button text size="small" type="danger" :icon="UserMinus" @click="unassign(row, assignment)" />
                  </el-tooltip>
                </div>
              </div>
            </template>
            <span v-else>-</span>
            <small class="inline-meta">{{ assignedCount(row) }}/{{ row.headcount ?? '-' }}</small>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="visibleColumns.unit_price" prop="unit_price" :label="t('fields.unitPrice')" width="140" sortable />
      <el-table-column v-if="visibleColumns.nationality_requirement" prop="nationality_requirement" :label="t('fields.nationalityRequirement')" width="130" sortable />
      <el-table-column v-if="visibleColumns.duration" prop="duration" :label="t('fields.duration')" min-width="160" sortable />
      <el-table-column v-if="visibleColumns.description" prop="description" :label="t('fields.description')" min-width="260" show-overflow-tooltip />
      <el-table-column v-if="visibleColumns.created_at" prop="created_at" :label="t('fields.createdAt')" width="170" sortable />
      <el-table-column fixed="right" :label="t('common.actions')" width="260">
        <template #default="{ row }">
          <el-button text :icon="Eye" @click="openDetail(row)" />
          <el-button v-if="auth.can('projects', 'recommend')" text :icon="Sparkles" @click="recommend(row)" />
          <el-button v-if="auth.can('projects', 'update')" text :icon="UserPlus" :disabled="isFull(row)" @click="openAssign(row)" />
          <el-button v-if="auth.can('projects', 'update')" text :icon="Pencil" @click="openEdit(row)" />
          <el-button v-if="auth.can('projects', 'delete')" text type="danger" :icon="Trash2" @click="deleteProject(row)" />
        </template>
      </el-table-column>
    </el-table>
    <TablePager v-model:page="projectPager.page" v-model:page-size="projectPager.pageSize" :total="filteredProjects.length" />

    <section v-if="recommendations.length" class="below-panel">
      <h3>{{ t('projects.recommendations') }}: {{ selectedProject?.project_name }}</h3>
      <el-table :data="pagedRecommendations" size="small">
        <el-table-column :label="t('fields.fullName')" min-width="160">
          <template #default="{ row }">{{ row.employee.full_name }}</template>
        </el-table-column>
        <el-table-column prop="score" :label="t('projects.score')" width="100" />
        <el-table-column :label="t('projects.reasons')">
          <template #default="{ row }">{{ row.reasons.join(' / ') }}</template>
        </el-table-column>
      </el-table>
      <TablePager v-model:page="recommendationPager.page" v-model:page-size="recommendationPager.pageSize" :total="recommendations.length" />
    </section>

    <el-dialog v-model="dialog" :title="editingId ? t('common.edit') : t('common.create')" width="760px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-grid">
        <el-form-item :label="t('fields.clientCompany')" prop="client_company"><el-input v-model="form.client_company" /></el-form-item>
        <el-form-item :label="t('fields.projectName')" prop="project_name"><el-input v-model="form.project_name" /></el-form-item>
        <el-form-item class="span-2" :label="t('fields.description')"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item :label="t('fields.requiredSkills')"><el-input v-model="form.required_skills_text" /></el-form-item>
        <el-form-item :label="t('fields.workplace')" prop="workplace"><el-input v-model="form.workplace" /></el-form-item>
        <el-form-item :label="t('fields.nationalityRequirement')">
          <el-select v-model="form.nationality_requirement" clearable>
            <el-option v-for="option in nationalityRequirementOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.duration')"><el-input v-model="form.duration" /></el-form-item>
        <el-form-item :label="t('fields.headcount')"><el-input-number v-model="form.headcount" :min="0" /></el-form-item>
        <el-form-item :label="t('fields.unitPrice')"><el-input v-model="form.unit_price" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="save">{{ t('common.save') }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="analyzeDialog" :title="t('projects.analyzeEmail')" width="760px">
      <el-form ref="emailFormRef" :model="emailForm" :rules="emailRules" label-position="top">
        <el-form-item :label="t('fields.subject')"><el-input v-model="emailForm.subject" /></el-form-item>
        <el-form-item :label="t('fields.body')" prop="body"><el-input v-model="emailForm.body" type="textarea" :rows="8" /></el-form-item>
        <el-form-item :label="t('fields.attachmentText')"><el-input v-model="emailForm.attachment_text" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="analyzeDialog = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="analyze">{{ t('common.analyze') }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="assignDialog" :title="assignMode === 'edit' ? t('projects.reassign') : t('common.assign')" width="520px">
      <el-form ref="assignFormRef" :model="assignForm" :rules="assignRules" label-position="top">
        <el-form-item v-if="assignMode === 'edit'" :label="t('fields.projectName')" prop="project_id">
          <el-select v-model="assignForm.project_id" filterable>
            <el-option
              v-for="project in rows"
              :key="project.id"
              :disabled="project.id !== selectedProject?.id && isFull(project)"
              :label="projectOptionLabel(project)"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('fields.employee')" prop="employee_id">
          <el-select v-model="assignForm.employee_id" filterable>
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.full_name" :value="employee.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('app.role')"><el-input v-model="assignForm.role" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="assignDialog = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="assign">{{ t('common.save') }}</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailDrawer" :title="t('projects.detailTitle')" size="46%">
      <div v-if="detailRow" class="detail-sections">
        <section class="detail-section">
          <h3>{{ t('common.detail') }}</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('fields.clientCompany')">{{ textOrDash(detailRow.client_company) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.projectName')">{{ textOrDash(detailRow.project_name) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.workplace')">{{ textOrDash(detailRow.workplace) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.requiredSkills')">{{ listText(detailRow.required_skills) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.headcount')">{{ textOrDash(detailRow.headcount) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.unitPrice')">{{ textOrDash(detailRow.unit_price) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.nationalityRequirement')">{{ textOrDash(detailRow.nationality_requirement) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.duration')">{{ textOrDash(detailRow.duration) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.createdAt')">{{ textOrDash(detailRow.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="detail-section">
          <h3>{{ t('projects.aiResult') }}</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('fields.source')">{{ textOrDash(detailRow.attributes?.source) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.confidence')">{{ percent(detailRow.attributes?.source_confidence) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.remoteType')">{{ textOrDash(detailRow.attributes?.remote_type) }}</el-descriptions-item>
            <el-descriptions-item :label="t('fields.station')">{{ textOrDash(detailRow.attributes?.station) }}</el-descriptions-item>
            <el-descriptions-item v-if="detailRow.attributes?.ai_error" :label="t('fields.aiError')" :span="2">
              <span class="danger-text">{{ detailRow.attributes.ai_error }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="detail-section">
          <h3>{{ t('fields.description') }}</h3>
          <pre class="detail-raw">{{ textOrDash(detailRow.description) }}</pre>
        </section>

        <section class="detail-section">
          <h3>{{ t('fields.rawEmail') }}</h3>
          <pre class="detail-raw">{{ textOrDash(detailRow.raw_email) }}</pre>
        </section>

        <section class="detail-section">
          <h3>{{ t('fields.attributes') }}</h3>
          <pre class="detail-json">{{ prettyJson(detailRow.attributes) }}</pre>
        </section>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.assigned-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 28px;
}

.assignment-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.assignment-chip-actions {
  display: inline-flex;
  align-items: center;
  gap: 0;
}

.assignment-chip-actions :deep(.el-button) {
  width: 24px;
  height: 24px;
  padding: 0;
}
</style>
