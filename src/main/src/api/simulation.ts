import { api } from './index'

export interface SimulationConfig {
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

export interface StartSimulationParams {
  projectName: string
  buildingType: string
  area: number
  config: SimulationConfig
  data: {
    headers: string[]
    rows: Record<string, any>[]
  }
}

export interface StartSimulationResponse {
  taskId: string
  status: string
  message: string
}

export interface SimulationStatus {
  taskId: string
  status: string
  progress: number
  currentWeek: number
  totalWeeks: number
  startedAt?: string
  updatedAt?: string
  message?: string
}

export interface SimulationResult {
  taskId: string
  projectId: number
  summary: {
    totalEnergy: number
    eui: number
    peakCoolingLoad: number
    peakHeatingLoad: number
    avgCop: number
    carbonEmission: number
  }
  weeklyData: Array<{
    weekNumber: number
    avgOutdoorTemp: number
    totalCoolingLoad: number
    totalHeatingLoad: number
    totalEnergyConsumption: number
    avgSystemCop: number
  }>
  createdAt: string
}

/**
 * 启动仿真
 */
export async function startSimulation(
  params: StartSimulationParams,
): Promise<StartSimulationResponse> {
  const response = await api.post('/simulate/start', params)
  return response.data
}

/**
 * 获取仿真状态
 */
export async function getSimulationStatus(taskId: string): Promise<SimulationStatus> {
  const response = await api.get(`/simulate/status/${taskId}`)
  return response.data
}

/**
 * 取消仿真
 */
export async function cancelSimulation(taskId: string): Promise<{ message: string }> {
  const response = await api.post(`/simulate/cancel/${taskId}`)
  return response.data
}

/**
 * 获取仿真结果
 */
export async function getSimulationResults(taskId: string): Promise<SimulationResult> {
  const response = await api.get(`/simulate/results/${taskId}`)
  return response.data
}
