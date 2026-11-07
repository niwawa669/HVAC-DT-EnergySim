/** 项目展示用的中文标签与格式化（前端唯一来源，避免各页面各写一套映射）。 */

export const BUILDING_TYPE_LABELS: Record<string, string> = {
  office: '办公建筑',
  commercial: '商业建筑',
  residential: '住宅建筑',
  hospital: '医院建筑',
  industrial: '工业建筑',
}

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: '待处理',
  pending: '待处理',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export function buildingTypeLabel(value?: string | null): string {
  if (!value) return '—'
  return BUILDING_TYPE_LABELS[value] || value
}

export function projectStatusLabel(value?: string | null): string {
  if (!value) return '—'
  return PROJECT_STATUS_LABELS[value] || value
}

export function projectStatusTagType(
  value?: string | null,
): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  switch (value) {
    case 'completed':
      return 'success'
    case 'running':
      return 'warning'
    case 'failed':
      return 'danger'
    case 'cancelled':
      return 'info'
    case 'pending':
    case 'draft':
      return 'primary'
    default:
      return 'info'
  }
}

/** ISO 时间 -> YYYY-MM-DD HH:mm（本地时间）；无法解析时原样返回。 */
export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function formatNumberFixed(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

export function formatArea(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value.toLocaleString('zh-CN')} m²`
}
