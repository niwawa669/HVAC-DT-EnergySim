import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface User {
  id: number
  username: string
  role: string
  email?: string
}

interface AuthData {
  access_token: string
  user: User
}

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<User | null>(
    (() => {
      const data = localStorage.getItem('user')
      if (!data) return null
      try {
        return JSON.parse(data)
      } catch {
        return null
      }
    })(),
  )

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const userName = computed(() => user.value?.username || '未登录')
  const userRole = computed(() => user.value?.role || 'guest')

  function setAuth(data: AuthData) {
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function getAuthHeader() {
    return {
      Authorization: `Bearer ${token.value}`,
    }
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    userName,
    userRole,
    setAuth,
    logout,
    getAuthHeader,
  }
})
