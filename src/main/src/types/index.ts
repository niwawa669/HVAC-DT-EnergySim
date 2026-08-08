// 用户相关类型
export interface User {
  id: number
  username: string
  role: string
  email?: string
  avatar?: string
}

export interface AuthData {
  access_token: string
  token_type?: string
  user: User
}

export interface LoginParams {
  username: string
  password: string
}

// 项目相关类型
export interface Project {
  id: number
  name: string
  buildingType: string
  systemType: string
  operationSchedule: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
  updatedAt?: string
  ownerId?: number
  config?: Record<string, any>
}

// 仿真任务相关类型
export interface SimulationTask {
  id: string
  projectId: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  currentWeek: number
  totalWeeks: number
  startedAt?: string
  finishedAt?: string
  errorMessage?: string
}

// 周度数据
export interface WeeklyData {
  weekNumber: number
  progressPercentage: number
  totalEnergyConsumption: number
  totalCoolingLoad: number
  totalHeatingLoad: number
  avgOutdoorTemp: number
  avgSystemCop: number
}

// WebSocket 消息类型
export interface WebSocketMessage {
  type: 'progress' | 'completed' | 'failed'
  data?: WeeklyData
  summary?: {
    total_energy: number
    eui: number
    peak_load: number
    avg_cop: number
  }
  error?: string
}
