import { api } from './index'

// ===== 设备选型参数 =====
export interface EquipmentConfig {
  // 建筑负荷
  load_building_r: number
  capacity_factor: number // 冷机容量放大系数：实际单机容量 = 基准容量 × 该系数

  // 冷机参数
  Qr_chiller_BCH: number
  n_design_BCH: number
  Qr_chiller_SCH: number
  n_design_SCH: number
  ts_chw_design: number
  tr_chw_design: number
  tr_cw_design: number
  ts_cw_design: number

  // 冷却塔参数
  Pr_tower_BCH: number
  Hs_tower_BCH: number
  n_tower_BCH: number // 新增
  Pr_tower_SCH: number
  Hs_tower_SCH: number
  n_tower_SCH: number // 新增

  // 水泵参数
  Hr_pump_chw_BCH: number
  n_pump_chw_BCH: number // 新增
  Hr_pump_chw_SCH: number
  n_pump_chw_SCH: number // 新增
  Hr_pump_cw_BCH: number
  n_pump_cw_BCH: number // 新增
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

// ===== 仿真结果（七个区块，唯一类型来源）=====
export interface EnergyBreakdown {
  chiller: number
  pump_chw: number
  pump_cw: number
  tower: number
}

export interface WeeklyData {
  weekNumber: number
  weekLabel?: string | null
  weekStart?: string | null
  weekEnd?: string | null
  hours: number
  totalCoolingLoad: number
  peakCoolingLoad: number
  totalQStation: number
  totalEnergyConsumption: number
  avgSystemCop: number
  avgChillerCop: number
  avgOutdoorTemp: number
  breakdown?: EnergyBreakdown | null
  supplyGap: number
  unservedWhenOff: number
  unmetHours: number
  progressPercentage: number
}

export interface MonthlyData {
  month?: string | null
  hours: number
  totalCoolingLoad: number
  totalQStation: number
  totalEnergyConsumption: number
  avgChillerCop: number
  systemEER: number
  breakdown?: EnergyBreakdown | null
  supplyGap: number
}

export interface PeakContext {
  timestamp?: string | null
  load: number
  loadUnit: string
  temperature?: number | null
  humid?: number | null
  qStation: number
  chillerCOP: number
  systemEER: number
  loadRate: number
  nSCH: number
  nBCH: number
}

export interface SimulationSummary {
  totalEnergy: number
  totalCoolingLoad: number
  totalQStation: number
  peakCoolingLoad: number
  eui: number
  avgCop: number
  /** 全年冷机平均负荷率（%）= 冷源站总供冷量 ÷ Σ(在线冷机额定制冷量 × 1h) */
  avgChillerLoadRate?: number
  systemEER: number
  totalUnmet: number
  unmetHours: number
  totalUnservedOff: number
  carbonEmission: number
  area: number
}

export interface SimulationMeta {
  fileName?: string | null
  totalRows: number
  totalHours: number
  startTime?: string | null
  endTime?: string | null
  confirmedRange?: string | null
  correctedOutliers: number
  tDryMin?: number | null
  tDryMax?: number | null
  humidMin?: number | null
  humidMax?: number | null
  weeks: number
  projectName?: string | null
  buildingType?: string | null
  area: number
  caliberVersion: string
  // ===== 选型尺度（口径 v2）=====
  capacityFactor?: number | null   // 冷机容量放大系数
  peakLoad?: number | null         // 建筑负荷最大值 kW
  installedCapacity?: number | null // 总装机容量 kW
  designMargin?: number | null     // 设计裕度 = 总装机 ÷ 峰值负荷
  carbonFactor: Record<string, any>
  applicableRange: Record<string, any>
  applicableRangeSource?: string | null
  extrapolation: Record<string, any>
  parameters: Record<string, any>
  displayOnly: string[]
  displayOnlyDeviations: Record<string, any>
}

export interface UnmetHour {
  timestamp?: string | null
  demand: number
  served: number
  unmet: number
  loadRate: number
  nSCH: number
  nBCH: number
  temperature?: number | null
}

export interface SimulationResult {
  taskId: string
  projectId: number
  createdAt: string
  meta: SimulationMeta
  summary: SimulationSummary
  weekly: WeeklyData[]
  monthly: MonthlyData[]
  breakdown: EnergyBreakdown
  operating_stats: Record<string, number>
  peak_context: PeakContext
  unmet_hours_detail: UnmetHour[]
  /** 负荷率分布：长度恒为 10，第 i 个元素为负荷率落在 [i/10, (i+1)/10) 的逐时计数，末区间含 1.0 */
  load_rate_histogram: number[]
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
 * 获取仿真结果（七区块）
 */
export async function getSimulationResults(taskId: string): Promise<SimulationResult> {
  const response = await api.get(`/simulate/results/${taskId}`)
  return response.data
}
