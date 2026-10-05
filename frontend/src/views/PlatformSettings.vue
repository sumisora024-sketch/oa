<script setup>
import { computed, onMounted, ref } from 'vue'
import { RefreshCw, Save } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'

const { locale } = useI18n()
const loading = ref(false)
const saving = ref('')
const active = ref('notifications')
const config = ref({ roles: [], channels: [], users: [], notification_rules: [], workflow_definitions: [], document_policies: [] })
const copy = computed(() => ({
  ja: { title: '共通機能設定', note: '通知、承認フロー、文書閲覧権限を業務ルールとして管理します。変更は新規申請から適用されます。', notifications: '通知ルール', workflows: '承認フロー', documents: '文書権限', enabled: '有効', channels: '通知方法', recipients: '通知先ロール', users: '個別通知先', related: '関連担当者を含む', schedule: '通知日（期限前）', steps: '承認ステップ', roles: '承認ロール', approvers: '指定承認者', owner: '本人閲覧', relation: '関連者閲覧', save: '保存', reload: '再読込', saved: '設定を保存しました' },
  zh: { title: '公共能力设置', note: '统一管理通知、审批流和文件查看权限。审批流变更从新申请开始生效。', notifications: '通知规则', workflows: '审批流程', documents: '文件权限', enabled: '启用', channels: '通知渠道', recipients: '通知角色', users: '指定通知人', related: '包含相关人员', schedule: '到期前提醒天数', steps: '审批步骤', roles: '审批角色', approvers: '指定审批人', owner: '本人可见', relation: '相关人员可见', save: '保存', reload: '刷新', saved: '设置已保存' },
  en: { title: 'Shared capability settings', note: 'Manage notifications, approval flows, and document access. Workflow changes apply to new requests.', notifications: 'Notifications', workflows: 'Approval flows', documents: 'Document access', enabled: 'Enabled', channels: 'Channels', recipients: 'Recipient roles', users: 'Specific recipients', related: 'Include related users', schedule: 'Days before due date', steps: 'Approval steps', roles: 'Approver roles', approvers: 'Specific approvers', owner: 'Owner access', relation: 'Related access', save: 'Save', reload: 'Reload', saved: 'Settings saved' }
}[locale.value] || {}))
const userOptions = computed(() => config.value.users.map((row) => ({ value: row.id, label: `${row.full_name} (${row.role})` })))

async function load() {
  loading.value = true
  try { config.value = (await api.get('/platform/config')).data }
  catch (error) { ElMessage.error(error.response?.data?.detail || 'Load failed') }
  finally { loading.value = false }
}

async function saveRule(row) {
  saving.value = `event:${row.event_code}`
  try {
    await api.put(`/platform/event-rules/${row.event_code}`, {
      enabled: row.enabled, channels: row.channels, recipient_roles: row.recipient_roles,
      recipient_user_ids: row.recipient_user_ids, include_related: row.include_related, schedule: row.schedule || {}
    })
    ElMessage.success(copy.value.saved)
  } finally { saving.value = '' }
}

function addStep(row) { row.steps.push({ kind: 'role', roles: [], user_ids: [], label: `${copy.value.steps} ${row.steps.length + 1}` }) }

async function saveWorkflow(row) {
  saving.value = `flow:${row.workflow_type}`
  try { await api.put(`/platform/workflows/${row.workflow_type}`, { enabled: row.enabled, steps: row.steps }); ElMessage.success(copy.value.saved) }
  catch (error) { ElMessage.error(error.response?.data?.detail || 'Save failed') }
  finally { saving.value = '' }
}

async function savePolicy(row) {
  saving.value = `doc:${row.document_type}`
  try { await api.put(`/platform/document-policies/${row.document_type}`, { allowed_roles: row.allowed_roles, owner_access: row.owner_access, related_access: row.related_access }); ElMessage.success(copy.value.saved) }
  finally { saving.value = '' }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div><h2>{{ copy.title }}</h2><p class="muted">{{ copy.note }}</p></div>
      <el-button :icon="RefreshCw" @click="load">{{ copy.reload }}</el-button>
    </div>
    <el-tabs v-model="active" v-loading="loading">
      <el-tab-pane :label="copy.notifications" name="notifications">
        <div class="setting-list">
          <section v-for="row in config.notification_rules" :key="row.event_code" class="setting-block">
            <div class="setting-head"><div><strong>{{ row.display_name }}</strong><code>{{ row.event_code }}</code></div><el-switch v-model="row.enabled" :active-text="copy.enabled" /></div>
            <div class="setting-grid">
              <label><span>{{ copy.channels }}</span><el-select v-model="row.channels" multiple><el-option v-for="item in config.channels" :key="item" :label="item" :value="item" /></el-select></label>
              <label><span>{{ copy.recipients }}</span><el-select v-model="row.recipient_roles" multiple><el-option v-for="item in config.roles" :key="item" :label="item" :value="item" /></el-select></label>
              <label><span>{{ copy.users }}</span><el-select v-model="row.recipient_user_ids" multiple filterable><el-option v-for="item in userOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></label>
              <label v-if="row.event_code === 'contract.expiring'"><span>{{ copy.schedule }}</span><el-select v-model="row.schedule.days_before" multiple allow-create filterable><el-option v-for="day in [90,60,30,14,7,1]" :key="day" :label="String(day)" :value="day" /></el-select></label>
            </div>
            <div class="setting-foot"><el-checkbox v-model="row.include_related">{{ copy.related }}</el-checkbox><el-button type="primary" :icon="Save" :loading="saving === `event:${row.event_code}`" @click="saveRule(row)">{{ copy.save }}</el-button></div>
          </section>
        </div>
      </el-tab-pane>
      <el-tab-pane :label="copy.workflows" name="workflows">
        <div class="setting-list">
          <section v-for="row in config.workflow_definitions" :key="row.workflow_type" class="setting-block">
            <div class="setting-head"><div><strong>{{ row.display_name }}</strong><code>{{ row.workflow_type }} / v{{ row.version }}</code></div><el-switch v-model="row.enabled" :active-text="copy.enabled" /></div>
            <div v-for="(step, index) in row.steps" :key="index" class="flow-step">
              <b>{{ index + 1 }}</b><el-input v-model="step.label" />
              <el-select v-model="step.roles" multiple :placeholder="copy.roles"><el-option v-for="role in config.roles" :key="role" :label="role" :value="role" /></el-select>
              <el-select v-model="step.user_ids" multiple filterable :placeholder="copy.approvers"><el-option v-for="item in userOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select>
              <el-button text type="danger" :disabled="row.steps.length === 1" @click="row.steps.splice(index, 1)">×</el-button>
            </div>
            <div class="setting-foot"><el-button @click="addStep(row)">+ {{ copy.steps }}</el-button><el-button type="primary" :icon="Save" :loading="saving === `flow:${row.workflow_type}`" @click="saveWorkflow(row)">{{ copy.save }}</el-button></div>
          </section>
        </div>
      </el-tab-pane>
      <el-tab-pane :label="copy.documents" name="documents">
        <el-table :data="config.document_policies" border>
          <el-table-column prop="display_name" min-width="150" /><el-table-column prop="document_type" min-width="160" />
          <el-table-column :label="copy.roles" min-width="280"><template #default="{ row }"><el-select v-model="row.allowed_roles" multiple><el-option v-for="role in config.roles" :key="role" :label="role" :value="role" /></el-select></template></el-table-column>
          <el-table-column :label="copy.owner" width="110"><template #default="{ row }"><el-switch v-model="row.owner_access" /></template></el-table-column>
          <el-table-column :label="copy.relation" width="120"><template #default="{ row }"><el-switch v-model="row.related_access" /></template></el-table-column>
          <el-table-column width="110"><template #default="{ row }"><el-button type="primary" :icon="Save" :loading="saving === `doc:${row.document_type}`" @click="savePolicy(row)">{{ copy.save }}</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.setting-list { display: grid; gap: 14px; }
.setting-block { border: 1px solid var(--el-border-color-light); background: var(--el-bg-color); padding: 16px; border-radius: 8px; }
.setting-head, .setting-foot { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.setting-head div { display: grid; gap: 4px; } code { color: var(--el-text-color-secondary); }
.setting-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 16px 0; }
.setting-grid label { display: grid; gap: 6px; }
.flow-step { display: grid; grid-template-columns: 34px minmax(140px, .8fr) minmax(180px, 1fr) minmax(220px, 1.3fr) 40px; align-items: center; gap: 10px; margin: 12px 0; }
.flow-step b { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; color: white; background: var(--el-color-primary); }
@media (max-width: 860px) { .setting-grid { grid-template-columns: 1fr; } .flow-step { grid-template-columns: 34px 1fr; } }
</style>
