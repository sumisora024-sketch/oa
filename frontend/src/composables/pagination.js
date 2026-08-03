import { computed, reactive, watch } from 'vue'

export function usePagination(source, defaultPageSize = 20) {
  const pager = reactive({ page: 1, pageSize: defaultPageSize })

  const pageRows = computed(() => {
    const rows = source.value || []
    const start = (pager.page - 1) * pager.pageSize
    return rows.slice(start, start + pager.pageSize)
  })

  watch(
    () => [source.value?.length || 0, pager.pageSize],
    ([total]) => {
      const maxPage = Math.max(Math.ceil(total / pager.pageSize), 1)
      if (pager.page > maxPage) pager.page = maxPage
    }
  )

  return { pager, pageRows }
}
