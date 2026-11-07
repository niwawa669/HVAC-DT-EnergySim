// 通用类型定义
// 注意：仿真相关的周度/月度/结果类型以 `@/api/simulation` 为唯一来源，
// 此处仅做再导出，避免两套定义漂移（见 simulation-result-contract D9）。

export type {
  WeeklyData,
  MonthlyData,
  PeakContext,
  SimulationSummary,
  SimulationMeta,
  SimulationResult,
  EnergyBreakdown,
} from '@/api/simulation'

import type { WeeklyData as WeeklyDataFromApi } from '@/api/simulation'

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

// 项目相关类型：以 api/projects 为唯一来源（与后端项目接口一致）
export type { Project, LatestTask, LatestSummary } from '@/api/projects'

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

// WebSocket 消息类型（进度消息的 data 复用周度结构）
export interface WebSocketMessage {
  type: 'connected' | 'started' | 'progress' | 'completed' | 'failed' | 'cancelled' | 'pong'
  data?: WeeklyDataFromApi
  summary?: Record<string, any>
  error?: string
}
