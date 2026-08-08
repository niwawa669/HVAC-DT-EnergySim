/**
 * 数据预处理工具函数
 * 用于解析、清洗和校验 CSV/TXT 数据
 */

// 数据解析结果接口
export interface ParseResult {
  headers: string[]
  data: Record<string, any>[]
  rowCount: number
  columnCount: number
  previewData: Record<string, any>[]
  warnings: string[]
  errors: string[]
}

// 数据校验结果
export interface ValidationResult {
  isValid: boolean
  errors: ValidationError[]
  warnings: string[]
  summary: {
    totalRows: number
    validRows: number
    invalidRows: number
    missingValues: Record<string, number>
  }
}

// 错误数据详情
export interface ValidationError {
  rowIndex: number
  column: string
  value: any
  message: string
  suggestion?: any
}

/**
 * 解析 CSV/TXT 文件内容
 */
export function parseDataFile(content: string, delimiter: string = ','): ParseResult {
  const warnings: string[] = []
  const errors: string[] = []

  // 按行分割
  const lines = content.split(/\r?\n/).filter((line) => line.trim() !== '')

  if (lines.length < 2) {
    errors.push('文件内容不足，至少需要标题行和一行数据')
    return {
      headers: [],
      data: [],
      rowCount: 0,
      columnCount: 0,
      previewData: [],
      warnings,
      errors,
    }
  }

  // 解析标题行
  const headers = lines[0].split(delimiter).map((h) => h.trim())

  if (headers.length < 2) {
    errors.push('数据列数不足，至少需要2列数据')
    return {
      headers,
      data: [],
      rowCount: 0,
      columnCount: headers.length,
      previewData: [],
      warnings,
      errors,
    }
  }

  // 检查是否有时间戳列
  const timeColumn = headers.find(
    (h) =>
      h.includes('时间') ||
      h.includes('time') ||
      h.includes('日期') ||
      h.includes('date') ||
      h.includes('Time') ||
      h.includes('Date'),
  )

  if (!timeColumn) {
    errors.push('未找到时间戳列，请确保首列包含时间数据（列名包含"时间"、"日期"、"time"或"date"）')
  }

  // 解析数据行
  const data: Record<string, any>[] = []
  let rowCount = 0

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(delimiter).map((v) => v.trim())

    // 检查列数是否匹配
    if (values.length !== headers.length) {
      warnings.push(`第 ${i + 1} 行列数不匹配 (期望 ${headers.length}，实际 ${values.length})`)
      continue
    }

    const row: Record<string, any> = {}
    headers.forEach((header, index) => {
      const value = values[index] || ''
      // 尝试转换为数字
      const numValue = parseFloat(value)
      row[header] = isNaN(numValue) ? value : numValue
    })

    data.push(row)
    rowCount++
  }

  // 预览数据（前10行）
  const previewData = data.slice(0, 10)

  return {
    headers,
    data,
    rowCount,
    columnCount: headers.length,
    previewData,
    warnings,
    errors,
  }
}

/**
 * 检测分隔符
 */
export function detectDelimiter(content: string): string {
  const firstLine = content.split(/\r?\n/)[0] || ''

  const tabCount = (firstLine.match(/\t/g) || []).length
  const commaCount = (firstLine.match(/,/g) || []).length
  const semicolonCount = (firstLine.match(/;/g) || []).length

  if (tabCount >= commaCount && tabCount >= semicolonCount) {
    return '\t'
  } else if (semicolonCount >= commaCount) {
    return ';'
  } else {
    return ','
  }
}

/**
 * 格式化时间戳（只保留日期和小时）
 */
export function formatTimestamp(value: any): string {
  if (!value) return ''

  // 如果是数字（Excel 时间戳）
  if (typeof value === 'number') {
    // Excel 时间戳转换（从1900-01-01开始）
    const excelEpoch = new Date(1899, 11, 30)
    const date = new Date(excelEpoch.getTime() + value * 86400000)
    return formatDateToHour(date)
  }

  // 如果是字符串
  if (typeof value === 'string') {
    // 尝试解析各种日期格式
    const patterns = [
      /(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})/,
      /(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2})/,
      /(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s+(\d{1,2}):(\d{2})/,
      /(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s+(\d{1,2})/,
    ]

    for (const pattern of patterns) {
      const match = value.match(pattern)
      if (match) {
        let year, month, day, hour
        if (match[1].length === 4) {
          year = parseInt(match[1])
          month = parseInt(match[2])
          day = parseInt(match[3])
          hour = parseInt(match[4] || '0')
        } else {
          year = parseInt(match[3])
          month = parseInt(match[1])
          day = parseInt(match[2])
          hour = parseInt(match[4] || '0')
        }
        const date = new Date(year, month - 1, day, hour)
        return formatDateToHour(date)
      }
    }

    // 尝试直接解析
    const date = new Date(value)
    if (!isNaN(date.getTime())) {
      return formatDateToHour(date)
    }
  }

  return value
}

/**
 * 格式化日期为 "YYYY-MM-DD HH:00"
 */
function formatDateToHour(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:00`
}

/**
 * 校验时间序列数据
 */
export function validateTimeSeriesWithErrors(
  data: Record<string, any>[],
  timeColumn: string,
): ValidationResult {
  const errors: ValidationError[] = []
  const warnings: string[] = []
  const missingValues: Record<string, number> = {}

  // 检查数据量
  if (data.length !== 8760) {
    warnings.push(`数据行数为 ${data.length}，期望 8760 行（全年逐时数据）`)
  }

  // 检查时间列
  if (!timeColumn || !data[0]?.hasOwnProperty(timeColumn)) {
    errors.push({
      rowIndex: -1,
      column: timeColumn || '时间戳',
      value: null,
      message: `时间列 "${timeColumn}" 不存在`,
      suggestion: '请确保数据中包含名为"时间"、"日期"、"time"或"date"的列',
    })
    return {
      isValid: false,
      errors,
      warnings,
      summary: {
        totalRows: data.length,
        validRows: 0,
        invalidRows: data.length,
        missingValues: {},
      },
    }
  }

  // 检查每行的数据
  let validRows = 0

  data.forEach((row, index) => {
    const headers = Object.keys(row)
    let rowValid = true

    // 检查时间戳
    const timeValue = row[timeColumn]
    if (!timeValue || timeValue === '' || timeValue === null) {
      errors.push({
        rowIndex: index,
        column: timeColumn,
        value: timeValue,
        message: '时间戳为空',
        suggestion: '请输入有效的时间',
      })
      rowValid = false
    } else {
      // 格式化时间戳
      const formatted = formatTimestamp(timeValue)
      if (formatted !== timeValue && typeof timeValue === 'string') {
        // 自动修正时间格式
        row[timeColumn] = formatted
      }

      // 验证时间格式是否正确
      const timePattern = /^\d{4}-\d{2}-\d{2} \d{2}:00$/
      if (!timePattern.test(row[timeColumn])) {
        errors.push({
          rowIndex: index,
          column: timeColumn,
          value: timeValue,
          message: `时间格式不正确 (应为 "YYYY-MM-DD HH:00")`,
          suggestion: formatTimestamp(timeValue),
        })
        rowValid = false
      }
    }

    // 检查其他列是否为数字
    headers.forEach((header) => {
      if (header === timeColumn) return
      const value = row[header]

      if (value === '' || value === null || value === undefined) {
        if (!missingValues[header]) missingValues[header] = 0
        missingValues[header]++
        rowValid = false
        errors.push({
          rowIndex: index,
          column: header,
          value: value,
          message: '数据缺失',
          suggestion: 0,
        })
      } else if (typeof value === 'string' && isNaN(parseFloat(value))) {
        errors.push({
          rowIndex: index,
          column: header,
          value: value,
          message: `"${value}" 不是有效数字`,
          suggestion: 0,
        })
        rowValid = false
      } else if (typeof value === 'number' && isNaN(value)) {
        errors.push({
          rowIndex: index,
          column: header,
          value: value,
          message: '不是有效数字',
          suggestion: 0,
        })
        rowValid = false
      }
    })

    if (rowValid) {
      validRows++
    }
  })

  const invalidRows = data.length - validRows
  const isValid = errors.length === 0

  return {
    isValid,
    errors,
    warnings,
    summary: {
      totalRows: data.length,
      validRows,
      invalidRows,
      missingValues,
    },
  }
}

/**
 * 数据清洗 - 填充缺失值
 */
export function fillMissingValues(
  data: Record<string, any>[],
  method: 'linear' | 'mean' | 'forward' = 'linear',
): Record<string, any>[] {
  const result = JSON.parse(JSON.stringify(data))
  const headers = Object.keys(result[0] || {})

  headers.forEach((header) => {
    // 检查是否包含缺失值
    const missingIndices: number[] = []
    result.forEach((row, index) => {
      const value = row[header]
      if (value === '' || value === null || value === undefined || isNaN(value)) {
        missingIndices.push(index)
      }
    })

    if (missingIndices.length === 0) return

    // 获取有效值
    const validValues: { index: number; value: number }[] = []
    result.forEach((row, index) => {
      if (!missingIndices.includes(index)) {
        const val = parseFloat(row[header])
        if (!isNaN(val)) {
          validValues.push({ index, value: val })
        }
      }
    })

    if (validValues.length === 0) {
      // 如果没有有效值，填充0
      missingIndices.forEach((idx) => {
        result[idx][header] = 0
      })
      return
    }

    if (method === 'mean') {
      // 使用平均值填充
      const mean = validValues.reduce((sum, v) => sum + v.value, 0) / validValues.length
      missingIndices.forEach((idx) => {
        result[idx][header] = mean
      })
    } else if (method === 'forward') {
      // 前向填充
      missingIndices.forEach((idx) => {
        const prev = validValues.filter((v) => v.index < idx)
        if (prev.length > 0) {
          result[idx][header] = prev[prev.length - 1].value
        } else {
          result[idx][header] = validValues[0].value
        }
      })
    } else {
      // 线性插值
      missingIndices.forEach((idx) => {
        const prev = validValues.filter((v) => v.index < idx)
        const next = validValues.filter((v) => v.index > idx)

        if (prev.length === 0 && next.length === 0) {
          result[idx][header] = 0
        } else if (prev.length === 0) {
          result[idx][header] = next[0].value
        } else if (next.length === 0) {
          result[idx][header] = prev[prev.length - 1].value
        } else {
          const p = prev[prev.length - 1]
          const n = next[0]
          const ratio = (idx - p.index) / (n.index - p.index)
          result[idx][header] = p.value + (n.value - p.value) * ratio
        }
      })
    }
  })

  return result
}

/**
 * 检测异常值（使用3σ原则）
 */
export function detectOutliers(data: Record<string, any>[], column: string): number[] {
  const values: number[] = []
  data.forEach((row) => {
    const val = parseFloat(row[column])
    if (!isNaN(val)) {
      values.push(val)
    }
  })

  if (values.length < 3) return []

  const mean = values.reduce((sum, v) => sum + v, 0) / values.length
  const std = Math.sqrt(values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length)

  const outliers: number[] = []
  data.forEach((row, index) => {
    const val = parseFloat(row[column])
    if (!isNaN(val) && Math.abs(val - mean) > 3 * std) {
      outliers.push(index)
    }
  })

  return outliers
}

/**
 * 修复单行数据
 */
export function fixRowData(
  row: Record<string, any>,
  timeColumn: string,
  fixes: Record<string, any>,
): Record<string, any> {
  const fixed = { ...row }

  Object.keys(fixes).forEach((key) => {
    fixed[key] = fixes[key]
  })

  // 如果修复了时间戳，重新格式化
  if (fixes[timeColumn]) {
    fixed[timeColumn] = formatTimestamp(fixes[timeColumn])
  }

  return fixed
}
