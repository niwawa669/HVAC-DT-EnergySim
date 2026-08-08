import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 用户信息接口
interface User {
  id: number
  username: string
  role: string
  email?: string
  avatar?: string
}

// 登录响应数据接口
interface AuthData {
  access_token: string
  token_type?: string
  user: User
}

// 登录请求参数接口
interface LoginParams {
  username: string
  password: string
}

export const useUserStore = defineStore('user', () => {
  // State - 使用 null 作为初始值
  const token = ref<string>('')
  const user = ref<User | null>(null)

  // Getters
  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const userName = computed(() => user.value?.username || '未登录')
  const userRole = computed(() => user.value?.role || 'guest')

  // Actions
  function setAuth(data: AuthData) {
    token.value = data.access_token
    user.value = data.user

    // 保存到 localStorage
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
  }

  // 从 localStorage 恢复状态
  function restoreState() {
    const savedToken = localStorage.getItem('token')
    const savedUser = localStorage.getItem('user')

    if (savedToken) {
      token.value = savedToken
    }
    if (savedUser) {
      try {
        user.value = JSON.parse(savedUser)
      } catch {
        user.value = null
      }
    }
  }

  function login(params: LoginParams): Promise<AuthData> {
    // 模拟登录API调用
    return new Promise((resolve) => {
      setTimeout(() => {
        const authData: AuthData = {
          access_token: 'mock-token-' + Date.now(),
          token_type: 'Bearer',
          user: {
            id: 1,
            username: params.username,
            role: params.username === 'admin' ? 'admin' : 'engineer',
            email: `${params.username}@example.com`,
          },
        }
        setAuth(authData)
        resolve(authData)
      }, 500)
    })
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function updateUser(updatedUser: Partial<User>) {
    if (user.value) {
      user.value = { ...user.value, ...updatedUser }
      localStorage.setItem('user', JSON.stringify(user.value))
    }
  }

  function getToken(): string {
    return token.value
  }

  function getAuthHeader(): Record<string, string> {
    return {
      Authorization: `Bearer ${token.value}`,
    }
  }

  return {
    // State
    token,
    user,

    // Getters
    isLoggedIn,
    isAdmin,
    userName,
    userRole,

    // Actions
    setAuth,
    restoreState,
    login,
    logout,
    updateUser,
    getToken,
    getAuthHeader,
  }
})
