import { api } from './index'

// ===== 类型定义 =====

// 启动仿真请求参数
export interface StartSimulationRequest {
  projectName: string
  buildingType: string
  area: number
  config: {
    systemType: string
    operationSchedule: string
    startTime?: string
    endTime?: string
    coolingSetpoint: number
    heatingSetpoint: number
    occupancyDensity: number
    lightingPowerDensity: number
    equipmentPowerDensity: number
  }
  // 数据可以是 CSV 内容或已解析的 JSON
  data: {
    headers: string[]
    rows: Record<string, any>[]
  }
}

// 启动仿真响应
export interface StartSimulationResponse {
  taskId: string
  status: 'pending' | 'running'
  message: string
}

// 仿真任务状态
export interface SimulationTaskStatus {
  taskId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number // 0-100
  currentWeek: number
  totalWeeks: number
  startedAt: string
  updatedAt: string
  errorMessage?: string
}

// 仿真结果
export interface SimulationResult {
  taskId: string
  projectId: number
  summary: {
    totalEnergy: number // kWh
    eui: number // kWh/m²
    peakCoolingLoad: number // kW
    peakHeatingLoad: number // kW
    avgCop: number
    carbonEmission: number // kg CO₂
  }
  weeklyData: {
    weekNumber: number
    avgOutdoorTemp: number
    totalCoolingLoad: number
    totalHeatingLoad: number
    totalEnergyConsumption: number
    avgSystemCop: number
  }[]
  createdAt: string
}

// ===== API 函数 =====

/**
 * 启动仿真任务
 * 调用 Python 后端的 /simulate/start 接口
 */
export async function startSimulation(
  data: StartSimulationRequest,
): Promise<StartSimulationResponse> {
  const response = await api.post('/simulate/start', data)
  return response.data
}

/**
 * 获取仿真任务状态
 * 调用 Python 后端的 /simulate/status/{taskId} 接口
 */
export async function getSimulationStatus(taskId: string): Promise<SimulationTaskStatus> {
  const response = await api.get(`/simulate/status/${taskId}`)
  return response.data
}

/**
 * 取消仿真任务
 * 调用 Python 后端的 /simulate/cancel/{taskId} 接口
 */
export async function cancelSimulation(taskId: string): Promise<{ message: string }> {
  const response = await api.post(`/simulate/cancel/${taskId}`)
  return response.data
}

/**
 * 获取仿真结果
 * 调用 Python 后端的 /simulate/results/{taskId} 接口
 */
export async function getSimulationResults(taskId: string): Promise<SimulationResult> {
  const response = await api.get(`/simulate/results/${taskId}`)
  return response.data
}

/**
 * 获取项目列表（含仿真状态）
 */
export async function getProjects(): Promise<any[]> {
  const response = await api.get('/projects')
  return response.data
}

/**
 * 获取项目详情
 */
export async function getProject(projectId: number): Promise<any> {
  const response = await api.get(`/projects/${projectId}`)
  return response.data
}

/**
 * 上传数据文件（CSV/TXT）
 * 使用 FormData 上传文件到 Python 后端
 */
export async function uploadDataFile(file: File): Promise<{
  headers: string[]
  preview: Record<string, any>[]
  rowCount: number
}> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

/**
 * 数据校验
 * 调用 Python 后端校验数据格式
 */
export async function validateData(data: {
  headers: string[]
  rows: Record<string, any>[]
}): Promise<{
  isValid: boolean
  errors: { row: number; column: string; message: string }[]
  warnings: string[]
  summary: {
    totalRows: number
    validRows: number
    invalidRows: number
  }
}> {
  const response = await api.post('/validate', data)
  return response.data
}
