import { api } from './index'

export interface Project {
  id: number
  name: string
  buildingType: string
  area: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
  updatedAt: string
}

export interface CreateProjectParams {
  name: string
  buildingType: string
  area: number
}

/**
 * 获取项目列表
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
