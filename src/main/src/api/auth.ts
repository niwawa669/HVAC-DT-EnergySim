import { api } from './index'

export interface LoginParams {
  username: string
  password: string
}

export interface AccountUser {
  id: number
  username: string
  role: string
  email?: string | null
  isActive?: boolean
  createdAt?: string | null
  updatedAt?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: AccountUser
}

export interface UpdateProfileParams {
  email?: string | null
}

export interface ChangePasswordParams {
  currentPassword: string
  newPassword: string
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
export async function getCurrentUser(): Promise<AccountUser> {
  const response = await api.get('/auth/me')
  return response.data
}

/**
 * 更新当前账户资料
 */
export async function updateProfile(params: UpdateProfileParams): Promise<AccountUser> {
  const response = await api.put('/auth/me', params)
  return response.data
}

/**
 * 修改当前账户密码
 */
export async function changePassword(
  params: ChangePasswordParams,
): Promise<{ message: string }> {
  const response = await api.post('/auth/change-password', params)
  return response.data
}
