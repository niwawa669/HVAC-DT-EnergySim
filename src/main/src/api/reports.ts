import { api } from './index'

// 报告接口封装。类型以 design.md D1/D6 的契约为准：
// 报告由后端生成自包含 HTML 快照，前端只负责展示与打印。

export interface GenerateReportResponse {
  reportId: string
  taskId: string
  status: string
  generatedAt: string
  caliberVersion: string
  chapters: string[]
  downloadUrl: string
}

export interface ReportMeta {
  reportId: string
  taskId: string
  ownerId?: number | null
  reportVersion: string
  caliberVersion: string
  generatedAt: string
  carbonFactor: Record<string, any>
  chapterOrder: string[]
  chapterTitles: Record<string, string>
}

export interface ReportListItem {
  reportId: string
  generatedAt: string
  caliberVersion: string
  reportVersion: string
}

/** 生成报告（仅接受已完成的仿真任务） */
export async function generateReport(taskId: string): Promise<GenerateReportResponse> {
  const response = await api.post(`/reports/generate/${taskId}`)
  return response.data
}

/** 查询报告元信息 */
export async function getReportMeta(reportId: string): Promise<ReportMeta> {
  const response = await api.get(`/reports/${reportId}`)
  return response.data
}

/**
 * 取报告 HTML 文本。
 * 下载端点需要 Bearer 鉴权，iframe 的 src 无法携带请求头，
 * 因此这里以文本方式取回，再转成 Blob URL 交给 iframe。
 */
export async function getReportHtml(reportId: string): Promise<string> {
  const response = await api.get(`/reports/download/${reportId}`, {
    responseType: 'text',
    transformResponse: [(data) => data],
  })
  return response.data as string
}

/** 列出某任务的历史报告 */
export async function listReports(taskId: string): Promise<{ taskId: string; reports: ReportListItem[]; total: number }> {
  const response = await api.get(`/reports/list/${taskId}`)
  return response.data
}
