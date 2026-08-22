import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url: string) {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const lastMessage = ref<any>(null)
  const reconnectCount = ref(0)
  const maxReconnects = 5
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  const messageHandlers: ((message: any) => void)[] = []
  const errorHandlers: ((error: Event) => void)[] = []

  const connect = () => {
    if (ws.value?.readyState === WebSocket.OPEN) return

    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        console.log('WebSocket 连接成功')
        isConnected.value = true
        reconnectCount.value = 0
      }

      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
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
        attemptReconnect()
      }
    } catch (error) {
      console.error('WebSocket 连接失败:', error)
      attemptReconnect()
    }
  }

  const attemptReconnect = () => {
    if (reconnectCount.value >= maxReconnects) {
      console.log('达到最大重连次数')
      return
    }

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }

    reconnectCount.value++
    const delay = Math.min(1000 * Math.pow(2, reconnectCount.value), 30000)
    console.log(`${delay}ms 后重连 (${reconnectCount.value}/${maxReconnects})`)

    reconnectTimer = setTimeout(() => {
      connect()
    }, delay)
  }

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    isConnected.value = false
  }

  const sendMessage = (message: any) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket 未连接')
    }
  }

  const onMessage = (handler: (message: any) => void) => {
    console.log('📌 注册消息处理器')
    messageHandlers.push(handler)
    return () => {
      const index = messageHandlers.indexOf(handler)
      if (index > -1) {
        messageHandlers.splice(index, 1)
      }
    }
  }

  const onError = (handler: (error: Event) => void) => {
    errorHandlers.push(handler)
    return () => {
      const index = errorHandlers.indexOf(handler)
      if (index > -1) {
        errorHandlers.splice(index, 1)
      }
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    lastMessage,
    reconnectCount,
    connect,
    disconnect,
    sendMessage,
    onMessage,
    onError,
  }
}
