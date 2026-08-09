/**
 * 模拟WebSocket数据推送
 * @param {string} taskId - 任务ID
 * @param {Function} onMessage - 消息接收回调函数
 * @returns {Function} 停止模拟的函数
 */
export function mockSimulationData(taskId, onMessage) {
  let week = 0
  const totalWeeks = 52

  const interval = setInterval(() => {
    week++
    if (week > totalWeeks) {
      // 仿真完成
      if (onMessage && typeof onMessage === 'function') {
        onMessage({
          type: 'completed',
          summary: {
            total_energy: 125000,
            eui: 85.6,
            peak_load: 450,
            avg_cop: 3.2,
          },
        })
      }
      clearInterval(interval)
      return
    }

    // 生成模拟数据
    const progress = Math.round((week / totalWeeks) * 100)
    const energy = 2000 + Math.random() * 1500
    const coolingLoad = 300 + Math.random() * 200
    const heatingLoad = 100 + Math.random() * 150
    const temp = 15 + 10 * Math.sin((week / 52) * 2 * Math.PI) + Math.random() * 3

    if (onMessage && typeof onMessage === 'function') {
      onMessage({
        type: 'progress',
        data: {
          week_number: week,
          progress_percentage: progress,
          total_energy_consumption: energy,
          total_cooling_load: coolingLoad,
          total_heating_load: heatingLoad,
          avg_outdoor_temp: temp,
          avg_system_cop: 3.0 + Math.random() * 0.5,
        },
      })
    }
  }, 1500) // 每1.5秒推送一周数据

  // 返回停止函数
  return () => {
    clearInterval(interval)
    console.log('停止模拟数据推送')
  }
}
