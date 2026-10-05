<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Bell, CheckCheck } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'

const router = useRouter()
const { locale } = useI18n()
const open = ref(false)
const loading = ref(false)
const count = ref(0)
const rows = ref([])
let timer

const text = computed(() => ({
  ja: { title: '通知', allRead: 'すべて既読', empty: '新しい通知はありません' },
  zh: { title: '通知', allRead: '全部已读', empty: '暂无新通知' },
  en: { title: 'Notifications', allRead: 'Mark all read', empty: 'No new notifications' }
}[locale.value] || { title: '通知', allRead: 'すべて既読', empty: '新しい通知はありません' }))

async function loadCount() {
  try { count.value = (await api.get('/notifications/unread-count')).data.count || 0 } catch { count.value = 0 }
}

async function loadRows() {
  loading.value = true
  try { rows.value = (await api.get('/notifications', { params: { limit: 30 } })).data } finally { loading.value = false }
}

async function toggle() {
  open.value = !open.value
  if (open.value) await loadRows()
}

async function selectRow(row) {
  if (!row.is_read) {
    await api.patch(`/notifications/${row.id}/read`)
    row.is_read = true
    count.value = Math.max(0, count.value - 1)
  }
  open.value = false
  if (row.link) router.push(row.link)
}

async function readAll() {
  await api.post('/notifications/read-all')
  rows.value.forEach((row) => { row.is_read = true })
  count.value = 0
}

onMounted(() => {
  loadCount()
  timer = window.setInterval(loadCount, 60000)
})
onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <el-popover :visible="open" placement="bottom-end" :width="390" trigger="manual" @hide="open = false">
    <template #reference>
      <el-badge :value="count" :hidden="!count" :max="99">
        <el-button circle :icon="Bell" :aria-label="text.title" @click="toggle" />
      </el-badge>
    </template>
    <div class="notification-head">
      <strong>{{ text.title }}</strong>
      <el-button link type="primary" :icon="CheckCheck" :disabled="!count" @click="readAll">{{ text.allRead }}</el-button>
    </div>
    <div v-loading="loading" class="notification-list">
      <button v-for="row in rows" :key="row.id" class="notification-row" :class="{ unread: !row.is_read }" @click="selectRow(row)">
        <span class="notification-title">{{ row.title }}</span>
        <span class="notification-message">{{ row.message }}</span>
        <time>{{ new Date(row.created_at).toLocaleString(locale) }}</time>
      </button>
      <el-empty v-if="!loading && !rows.length" :description="text.empty" :image-size="48" />
    </div>
  </el-popover>
</template>

<style scoped>
.notification-head { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 10px; border-bottom: 1px solid var(--el-border-color-lighter); }
.notification-list { max-height: min(520px, 70vh); overflow: auto; }
.notification-row { display: grid; width: 100%; gap: 4px; padding: 12px 8px 12px 14px; text-align: left; border: 0; border-bottom: 1px solid var(--el-border-color-lighter); background: transparent; color: var(--el-text-color-primary); cursor: pointer; position: relative; }
.notification-row:hover { background: var(--el-fill-color-light); }
.notification-row.unread::before { content: ''; position: absolute; left: 3px; top: 18px; width: 5px; height: 5px; border-radius: 50%; background: var(--el-color-primary); }
.notification-title { font-weight: 650; }
.notification-message { color: var(--el-text-color-regular); line-height: 1.45; }
time { color: var(--el-text-color-secondary); font-size: 12px; }
</style>
