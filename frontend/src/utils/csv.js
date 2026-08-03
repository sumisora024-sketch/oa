export function csvValue(value) {
  const text = value === null || value === undefined ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

export function downloadCsv(rows, columns, filename, emptyMessage = 'ダウンロード対象がありません') {
  if (!rows.length) {
    return { ok: false, message: emptyMessage }
  }
  const header = columns.map((column) => csvValue(column.label)).join(',')
  const body = rows.map((row) => columns.map((column) => {
    const value = typeof column.value === 'function' ? column.value(row) : row[column.key]
    return csvValue(value)
  }).join(',')).join('\n')
  const blob = new Blob([`\uFEFF${header}\n${body}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
  return { ok: true }
}
