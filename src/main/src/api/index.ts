import axios from 'axios'
import { useUserStore } from '@/stores/userStore'
import { ElMessage } from 'element-plus'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ===== 请求拦截器：自动添加 Token =====
api.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    console.log('当前 Token:', userStore.token) // 调试日志
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// ===== 响应拦截器：401 跳转登录 =====
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      ElMessage.error('登录已过期，请重新登录')
      window.location.href = '/login'
    } else if (error.response?.status === 500) {
      ElMessage.error('服务器错误，请稍后重试')
    } else if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    } else {
      ElMessage.error(error.message || '请求失败')
    }
    return Promise.reject(error)
  },
)

export { api, API_BASE_URL }
