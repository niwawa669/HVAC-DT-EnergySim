import { api } from './index'

// ===== 设备选型参数 =====
export interface EquipmentConfig {
  // 建筑负荷
  load_building_r: number
  load_coe: number
  coe: number
  coe_tower_efficience: number

  // 冷机参数
  Qr_chiller_BCH: number
  n_design_BCH: number
  COP_chiller_BCH: number // 新增
  Qr_chiller_SCH: number
  n_design_SCH: number
  COP_chiller_SCH: number // 新增
  ts_chw_design: number
  tr_chw_design: number
  tr_cw_design: number
  ts_cw_design: number

  // 冷却塔参数
  Gr_tower_BCH: number
  Pr_tower_BCH: number
  Hs_tower_BCH: number
  n_tower_BCH: number // 新增
  Gr_tower_SCH: number
  Pr_tower_SCH: number
  Hs_tower_SCH: number
  n_tower_SCH: number // 新增

  // 水泵参数
  Gr_pump_chw_BCH: number
  Hr_pump_chw_BCH: number
  n_pump_chw_BCH: number // 新增
  Gr_pump_chw_SCH: number
  Hr_pump_chw_SCH: number
  n_pump_chw_SCH: number // 新增
  Gr_pump_cw_BCH: number
  Hr_pump_cw_BCH: number
  n_pump_cw_BCH: number // 新增
  Gr_pump_cw_SCH: number
  Hr_pump_cw_SCH: number
  n_pump_cw_SCH: number // 新增

  // 管道压降
  Hr_pt: number
  Hr_chiller_chw_BCH: number
  Hr_chiller_cw_BCH: number
  Hr_chiller_chw_SCH: number
  Hr_chiller_cw_SCH: number
}

// ===== 群控控制参数 =====
export interface ControlConfig {
  // 温度控制
  ta_dry_r: number
  ta_wet_r: number
  ts_chw_set: number
  delta_t_chw: number
  delta_t_cw: number
  tr_cw_min: number
  approach_set: number

  // 负荷控制
  load_up: number
  load_min: number

  // 冷机加机优先级
  Qr_list: number[]
  n_design_list: number[]

  // ===== 频率控制（修改后） =====
  // 冷冻/冷却泵频率
  freq_pump_max: number
  freq_pump_min: number
  // 冷却塔风机频率
  freq_tower_max: number
  freq_tower_min: number
}

// ===== 完整配置 =====
export interface SimulationConfig extends EquipmentConfig, ControlConfig {}

// ===== 启动仿真请求参数 =====
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

// ===== 启动仿真响应 =====
export interface StartSimulationResponse {
  taskId: string
  status: string
  message: string
}

// ===== 仿真状态 =====
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

// ===== 仿真结果 =====
export interface SimulationResult {
  taskId: string
  projectId: number
  summary: {
    totalEnergy: number
    totalCoolingLoad: number
    totalQStation: number
    peakCoolingLoad: number
    eui: number
    avgCop: number
    carbonEmission: number
  }
  weeklyData: Array<{
    weekNumber: number
    totalCoolingLoad: number
    peakCoolingLoad: number
    totalQStation: number
    totalEnergyConsumption: number
    avgSystemCop: number
    avgOutdoorTemp: number
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
 * 重新仿真 - 使用相同的 task_id 重新计算
 */
export async function restartSimulation(
  taskId: string,
): Promise<{ taskId: string; status: string; message: string }> {
  const response = await api.post(`/simulate/restart/${taskId}`)
  return response.data
}

/**
 * 获取仿真结果
 */
export async function getSimulationResults(taskId: string): Promise<SimulationResult> {
  const response = await api.get(`/simulate/results/${taskId}`)
  return response.data
}
