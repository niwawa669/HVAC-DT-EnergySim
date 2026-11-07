import { api } from './index'

export type UserRole = 'admin' | 'engineer'

export interface AccountItem {
  id: number
  username: string
  email?: string | null
  role: UserRole | string
  isActive: boolean
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UserListResponse {
  items: AccountItem[]
  total: number
  page: number
  pageSize: number
}

export interface CreateUserParams {
  username: string
  password: string
  email?: string | null
  role: UserRole
}

export interface UpdateUserParams {
  email?: string | null
  role?: UserRole
  isActive?: boolean
}

export async function listUsers(params: {
  search?: string
  page?: number
  pageSize?: number
}): Promise<UserListResponse> {
  const response = await api.get('/users', { params })
  return response.data
}

export async function createUser(params: CreateUserParams): Promise<AccountItem> {
  const response = await api.post('/users', params)
  return response.data
}

export async function updateUser(
  id: number,
  params: UpdateUserParams,
): Promise<AccountItem> {
  const response = await api.patch(`/users/${id}`, params)
  return response.data
}

export async function resetUserPassword(
  id: number,
  newPassword: string,
): Promise<{ message: string; userId: number }> {
  const response = await api.post(`/users/${id}/password`, { newPassword })
  return response.data
}

export async function deleteUser(id: number): Promise<{ message: string; userId: number }> {
  const response = await api.delete(`/users/${id}`)
  return response.data
}
