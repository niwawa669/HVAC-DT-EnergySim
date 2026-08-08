import { ref, onMounted, onUnmounted } from 'vue'

/**
 * WebSocket 组合式函数
 * @param {string} url - WebSocket 连接地址
 * @param {Function} onMessage - 消息接收回调函数
 * @param {Function} onError - 错误回调函数
 * @returns {Object} WebSocket 控制对象
 */
export function useWebSocket(url, onMessage, onError) {
  const ws = ref(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5

  const connect = () => {
    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        console.log('WebSocket连接成功')
        isConnected.value = true
        reconnectAttempts.value = 0
      }

      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (onMessage && typeof onMessage === 'function') {
            onMessage(data)
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error)
        }
      }

      ws.value.onerror = (error) => {
        console.error('WebSocket错误:', error)
        if (onError && typeof onError === 'function') {
          onError(error)
        }
      }

      ws.value.onclose = () => {
        console.log('WebSocket连接关闭')
        isConnected.value = false
        // 自动重连
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++
          setTimeout(() => {
            console.log(`尝试重连 (${reconnectAttempts.value}/${maxReconnectAttempts})`)
            connect()
          }, 3000 * reconnectAttempts.value)
        }
      }
    } catch (error) {
      console.error('WebSocket连接失败:', error)
      if (onError && typeof onError === 'function') {
        onError(error)
      }
    }
  }

  const disconnect = () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.close()
    }
  }

  const sendMessage = (data) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket未连接，无法发送消息')
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
    sendMessage,
    disconnect,
    reconnectAttempts,
    connect,
  }
}
