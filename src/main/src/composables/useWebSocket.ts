import { ref, onMounted, onUnmounted } from 'vue'

export interface WebSocketMessage {
  type: 'connected' | 'progress' | 'completed' | 'failed' | 'heartbeat'
  data?: {
    weekNumber: number
    progressPercentage: number
    totalEnergyConsumption: number
    totalCoolingLoad: number
    totalHeatingLoad: number
    avgOutdoorTemp: number
    avgSystemCop: number
  }
  summary?: {
    totalEnergy: number
    eui: number
    peakCoolingLoad: number
    peakHeatingLoad: number
    avgCop: number
    carbonEmission: number
  }
  error?: string
  message?: string
}

export function useWebSocket(taskId: string) {
  // WebSocket 连接地址（从环境变量读取）
  const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/ws'

  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isSimulating = ref(false)
  const lastMessage = ref<WebSocketMessage | null>(null)
  const reconnectCount = ref(0)
  const maxReconnects = 5

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null

  // 消息回调
  const messageHandlers: ((message: WebSocketMessage) => void)[] = []
  const errorHandlers: ((error: Event) => void)[] = []
  const connectHandlers: (() => void)[] = []
  const disconnectHandlers: (() => void)[] = []

  /**
   * 获取 WebSocket URL
   */
  const getWsUrl = (): string => {
    const token = localStorage.getItem('token') || ''
    return `${WS_BASE_URL}/simulate/${taskId}?token=${encodeURIComponent(token)}`
  }

  /**
   * 连接 WebSocket
   */
  const connect = () => {
    if (ws.value?.readyState === WebSocket.OPEN) return

    try {
      const url = getWsUrl()
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        console.log('WebSocket 连接成功')
        isConnected.value = true
        reconnectCount.value = 0
        isSimulating.value = true

        connectHandlers.forEach((handler) => handler())

        // 启动心跳
        startHeartbeat()

        // 发送连接成功消息
        const msg: WebSocketMessage = {
          type: 'connected',
          message: '连接成功',
        }
        lastMessage.value = msg
        messageHandlers.forEach((handler) => handler(msg))
      }

      ws.value.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data)
          lastMessage.value = data
          messageHandlers.forEach((handler) => handler(data))
        } catch (error) {
          console.error('解析 WebSocket 消息失败:', error)
        }
      }

      ws.value.onerror = (error) => {
        console.error('WebSocket 错误:', error)
        errorHandlers.forEach((handler) => handler(error))
      }

      ws.value.onclose = () => {
        console.log('WebSocket 连接关闭')
        isConnected.value = false
        isSimulating.value = false
        stopHeartbeat()
        disconnectHandlers.forEach((handler) => handler())
        attemptReconnect()
      }
    } catch (error) {
      console.error('WebSocket 连接失败:', error)
      attemptReconnect()
    }
  }

  /**
   * 重连尝试
   */
  const attemptReconnect = () => {
    if (reconnectCount.value >= maxReconnects) {
      console.log('达到最大重连次数，停止重连')
      return
    }

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }

    reconnectCount.value++
    const delay = Math.min(1000 * Math.pow(2, reconnectCount.value), 30000)
    console.log(`将在 ${delay}ms 后尝试第 ${reconnectCount.value} 次重连`)

    reconnectTimer = setTimeout(() => {
      connect()
    }, delay)
  }

  /**
   * 心跳机制（保持连接活跃）
   */
  const startHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
    }
    heartbeatTimer = setInterval(() => {
      if (ws.value?.readyState === WebSocket.OPEN) {
        ws.value.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000) // 每30秒发送一次心跳
  }

  const stopHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  /**
   * 断开连接
   */
  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopHeartbeat()

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    isConnected.value = false
    isSimulating.value = false
  }

  /**
   * 发送消息到服务器
   */
  const sendMessage = (message: any) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket 未连接，无法发送消息')
    }
  }

  /**
   * 注册消息回调
   */
  const onMessage = (handler: (message: WebSocketMessage) => void) => {
    messageHandlers.push(handler)
    return () => {
      const index = messageHandlers.indexOf(handler)
      if (index > -1) {
        messageHandlers.splice(index, 1)
      }
    }
  }

  /**
   * 注册错误回调
   */
  const onError = (handler: (error: Event) => void) => {
    errorHandlers.push(handler)
    return () => {
      const index = errorHandlers.indexOf(handler)
      if (index > -1) {
        errorHandlers.splice(index, 1)
      }
    }
  }

  /**
   * 注册连接回调
   */
  const onConnect = (handler: () => void) => {
    connectHandlers.push(handler)
    return () => {
      const index = connectHandlers.indexOf(handler)
      if (index > -1) {
        connectHandlers.splice(index, 1)
      }
    }
  }

  /**
   * 注册断开连接回调
   */
  const onDisconnect = (handler: () => void) => {
    disconnectHandlers.push(handler)
    return () => {
      const index = disconnectHandlers.indexOf(handler)
      if (index > -1) {
        disconnectHandlers.splice(index, 1)
      }
    }
  }

  // 生命周期
  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    isSimulating,
    lastMessage,
    reconnectCount,
    connect,
    disconnect,
    sendMessage,
    onMessage,
    onError,
    onConnect,
    onDisconnect,
  }
}
