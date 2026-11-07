import { api } from './index'

export interface LatestTask {
  taskId: string
  status: string
  progress: number
  updatedAt?: string | null
}

export interface LatestSummary {
  totalEnergy?: number | null
  totalCoolingLoad?: number | null
  eui?: number | null
  carbonEmission?: number | null
  peakLoad?: number | null
  createdAt?: string | null
}

export interface Project {
  id: number
  name: string
  buildingType?: string | null
  area?: number | null
  /** pending / running / completed / failed / cancelled */
  status: string
  createdAt: string
  updatedAt?: string | null
  latestTask?: LatestTask | null
  latestSummary?: LatestSummary | null
}

export interface CreateProjectParams {
  name: string
  buildingType?: string
  area?: number
}

/**
 * 获取项目列表（含最近一次仿真与结果摘要）
 */
export async function getProjects(): Promise<Project[]> {
  const response = await api.get('/projects')
  return response.data
}

/**
 * 获取项目详情
 */
export async function getProject(id: number): Promise<Project> {
  const response = await api.get(`/projects/${id}`)
  return response.data
}

/**
 * 创建项目
 */
export async function createProject(params: CreateProjectParams): Promise<Project> {
  const response = await api.post('/projects', params)
  return response.data
}

/**
 * 删除项目（仿真任务与结果保留，任务变为未关联）
 */
export async function deleteProject(id: number): Promise<{ message: string; projectId: number }> {
  const response = await api.delete(`/projects/${id}`)
  return response.data
}
