import { api } from './index'

export interface LoginParams {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: {
    id: number
    username: string
    role: string
    email: string
  }
}

/**
 * 用户登录
 */
export async function login(params: LoginParams): Promise<LoginResponse> {
  const response = await api.post('/auth/login', params)
  return response.data
}

/**
 * 获取当前用户信息
 */
export async function getCurrentUser(): Promise<any> {
  const response = await api.get('/auth/me')
  return response.data
}
