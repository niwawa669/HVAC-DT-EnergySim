/**
 * 格式化数字显示
 * @param {number} num - 要格式化的数字
 * @returns {string} 格式化后的字符串
 */
export function formatNumber(num) {
  if (!num || isNaN(num)) return '0'
  if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
  if (num >= 1e3) return (num / 1e3).toFixed(2) + 'k'
  return num.toFixed(2)
}

/**
 * 格式化日期显示
 * @param {string|Date} date - 日期对象或字符串
 * @returns {string} 格式化后的日期字符串
 */
export function formatDate(date) {
  const d = new Date(date)
  return d.toLocaleString('zh-CN')
}

/**
 * 格式化时间（秒数转时分秒）
 * @param {number} seconds - 总秒数
 * @returns {string} 格式化后的时间字符串 (HH:MM:SS)
 */
export function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '00:00:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/**
 * 格式化能耗数值
 * @param {number} value - 能耗值 (kWh)
 * @returns {string} 格式化后的字符串
 */
export function formatEnergy(value) {
  if (!value || isNaN(value)) return '0 kWh'
  if (value >= 1e6) return (value / 1e6).toFixed(2) + ' GWh'
  if (value >= 1e3) return (value / 1e3).toFixed(2) + ' MWh'
  return value.toFixed(2) + ' kWh'
}

/**
 * 格式化温度
 * @param {number} value - 温度值
 * @returns {string} 格式化后的温度字符串
 */
export function formatTemperature(value) {
  if (value === undefined || value === null || isNaN(value)) return '-- °C'
  return value.toFixed(1) + ' °C'
}

/**
 * 格式化百分比
 * @param {number} value - 百分比值 (0-100)
 * @returns {string} 格式化后的百分比字符串
 */
export function formatPercentage(value) {
  if (!value || isNaN(value)) return '0%'
  return value.toFixed(1) + '%'
}

/**
 * 截断文本
 * @param {string} text - 原始文本
 * @param {number} length - 保留长度
 * @returns {string} 截断后的文本
 */
export function truncateText(text, length = 20) {
  if (!text) return ''
  if (text.length <= length) return text
  return text.substring(0, length) + '...'
}

/**
 * 解析CSV文件内容
 * @param {string} content - CSV文件内容
 * @returns {Array<Object>} 解析后的数据数组
 */
export function parseCSV(content) {
  const lines = content.split('\n')
  if (lines.length < 2) return []

  const headers = lines[0].split(',').map((h) => h.trim())
  const result = []

  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue
    const values = lines[i].split(',').map((v) => v.trim())
    const row = {}
    headers.forEach((header, index) => {
      row[header] = values[index] || ''
    })
    result.push(row)
  }

  return result
}

/**
 * 下载文件
 * @param {string} content - 文件内容
 * @param {string} filename - 文件名
 * @param {string} type - 文件类型 (text/csv, application/pdf等)
 */
export function downloadFile(content, filename, type = 'text/csv') {
  const blob = new Blob([content], { type: type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 深拷贝对象
 * @param {Object} obj - 要拷贝的对象
 * @returns {Object} 拷贝后的新对象
 */
export function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj
  return JSON.parse(JSON.stringify(obj))
}

/**
 * 判断是否为有效的时间序列数据
 * @param {Array} data - 数据数组
 * @param {number} expectedLength - 期望的数据长度 (默认8760)
 * @returns {boolean} 是否有效
 */
export function isValidTimeSeries(data, expectedLength = 8760) {
  if (!data || !Array.isArray(data)) return false
  return data.length === expectedLength
}
