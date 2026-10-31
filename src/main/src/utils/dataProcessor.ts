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

  // ===== 首列就是时间列 =====
  const timeColumn = headers[0]

  // 解析数据行
  const data: Record<string, any>[] = []
  let rowCount = 0

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(delimiter).map((v) => v.trim())

    if (values.length !== headers.length) {
      warnings.push(`第 ${i + 1} 行列数不匹配 (期望 ${headers.length}，实际 ${values.length})`)
      continue
    }

    const row: Record<string, any> = {}
    headers.forEach((header, index) => {
      const value = values[index] || ''

      // ===== 关键修复：如果是时间列（首列），保留字符串，不转换为数字 =====
      if (index === 0) {
        // 时间列保持为字符串
        row[header] = value
      } else {
        // 其他列尝试转换为数字
        const numValue = parseFloat(value)
        row[header] = isNaN(numValue) ? value : numValue
      }
    })

    data.push(row)
    rowCount++
  }

  // ===== 格式化时间列（首列） =====
  if (timeColumn) {
    data.forEach((row) => {
      if (row[timeColumn] !== undefined && row[timeColumn] !== null && row[timeColumn] !== '') {
        row[timeColumn] = smartFormatTimestamp(row[timeColumn])
      }
    })
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
 * 智能格式化时间戳 - 专门处理您的格式
 */
export function smartFormatTimestamp(value: any): string {
  if (!value && value !== 0) return ''

  const str = String(value).trim()
  if (!str) return ''

  // ============================================
  // 处理: 2025/1/1 0:00 或 2025/1/1 00:00
  // 关键：小时可以是 0-23，分钟可以是 00-59
  // ============================================
  // 匹配格式: YYYY/M/D H:MM 或 YYYY/M/D HH:MM
  const match1 = str.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})\s+(\d{1,2}):(\d{2})$/)
  if (match1) {
    const year = match1[1]
    const month = String(match1[2]).padStart(2, '0')
    const day = String(match1[3]).padStart(2, '0')
    const hour = String(match1[4]).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:00`
  }

  // ============================================
  // 处理: 2025/1/1 (只有日期)
  // ============================================
  const match2 = str.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/)
  if (match2) {
    const year = match2[1]
    const month = String(match2[2]).padStart(2, '0')
    const day = String(match2[3]).padStart(2, '0')
    return `${year}-${month}-${day} 00:00`
  }

  // ============================================
  // 处理: 2025-01-01 00:00:00
  // ============================================
  const match3 = str.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/)
  if (match3) {
    return `${match3[1]}-${match3[2]}-${match3[3]} ${match3[4]}:00`
  }

  // ============================================
  // 处理: 2025-01-01 00:00
  // ============================================
  const match4 = str.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/)
  if (match4) {
    return `${match4[1]}-${match4[2]}-${match4[3]} ${match4[4]}:00`
  }

  // ============================================
  // 处理: 2025/08/01 00:00:00
  // ============================================
  const match5 = str.match(/^(\d{4})\/(\d{2})\/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/)
  if (match5) {
    return `${match5[1]}-${match5[2]}-${match5[3]} ${match5[4]}:00`
  }

  // ============================================
  // 处理: 2025/08/01 00:00
  // ============================================
  const match6 = str.match(/^(\d{4})\/(\d{2})\/(\d{2})\s+(\d{2}):(\d{2})$/)
  if (match6) {
    return `${match6[1]}-${match6[2]}-${match6[3]} ${match6[4]}:00`
  }

  // ============================================
  // 处理: 2025-08-01T00:00:00 (ISO)
  // ============================================
  const match7 = str.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/)
  if (match7) {
    return `${match7[1]}-${match7[2]}-${match7[3]} ${match7[4]}:00`
  }

  // ============================================
  // 处理: 01/08/2025 00:00 (美式)
  // ============================================
  const match8 = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})$/)
  if (match8) {
    const month = String(match8[1]).padStart(2, '0')
    const day = String(match8[2]).padStart(2, '0')
    const year = match8[3]
    const hour = String(match8[4]).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:00`
  }

  // ============================================
  // 使用 JavaScript Date 解析
  // ============================================
  try {
    const date = new Date(str)
    if (!isNaN(date.getTime()) && date.getFullYear() > 1970 && date.getFullYear() < 2100) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hour = String(date.getHours()).padStart(2, '0')
      return `${year}-${month}-${day} ${hour}:00`
    }
  } catch (e) {
    // 忽略
  }

  return str
}

/**
 * 格式化时间戳（兼容旧版本）
 */
export function formatTimestamp(value: any): string {
  return smartFormatTimestamp(value)
}

/**
 * 查找时间列 - 直接返回首列
 */
export function findTimeColumn(headers: string[]): string | null {
  if (!headers || headers.length === 0) return null
  return headers[0]
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
 * 校验时间序列数据
 */
export function validateTimeSeriesWithErrors(
  data: Record<string, any>[],
  timeColumn: string,
): ValidationResult {
  const errors: ValidationError[] = []
  const warnings: string[] = []
  const missingValues: Record<string, number> = {}

  if (!data || data.length === 0) {
    return {
      isValid: false,
      errors: [{ rowIndex: -1, column: '', value: null, message: '数据为空' }],
      warnings: [],
      summary: { totalRows: 0, validRows: 0, invalidRows: 0, missingValues: {} },
    }
  }

  // 检查数据量
  if (data.length !== 8760) {
    warnings.push(`数据行数为 ${data.length}，期望 8760 行（全年逐时数据）`)
  }

  // ===== 检查时间列（首列） =====
  if (!timeColumn) {
    errors.push({
      rowIndex: -1,
      column: '时间戳',
      value: null,
      message: '未找到时间列',
      suggestion: '请确保第一列为时间数据',
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
    if (!timeValue && timeValue !== 0) {
      errors.push({
        rowIndex: index,
        column: timeColumn,
        value: timeValue,
        message: '时间戳为空',
        suggestion: `${String(index + 1).padStart(4, '0')}-01-01 00:00`,
      })
      rowValid = false
    } else {
      // 验证时间格式
      const timePattern = /^\d{4}-\d{2}-\d{2} \d{2}:00$/
      if (!timePattern.test(String(timeValue))) {
        // 尝试自动修正
        const formatted = smartFormatTimestamp(timeValue)
        if (formatted !== String(timeValue) && timePattern.test(formatted)) {
          row[timeColumn] = formatted
        } else {
          errors.push({
            rowIndex: index,
            column: timeColumn,
            value: timeValue,
            message: `时间格式不正确 (应为 "YYYY-MM-DD HH:00")`,
            suggestion: smartFormatTimestamp(timeValue),
          })
          rowValid = false
        }
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
        // 尝试转换
        const numValue = parseFloat(value.replace(/,/g, ''))
        if (!isNaN(numValue)) {
          row[header] = numValue
        } else {
          errors.push({
            rowIndex: index,
            column: header,
            value: value,
            message: `"${value}" 不是有效数字`,
            suggestion: 0,
          })
          rowValid = false
        }
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
    const missingIndices: number[] = []
    result.forEach((row: Record<string, any>, index: number) => {
      const value = row[header]
      if (value === '' || value === null || value === undefined || isNaN(value)) {
        missingIndices.push(index)
      }
    })

    if (missingIndices.length === 0) return

    const validValues: { index: number; value: number }[] = []
    result.forEach((row: Record<string, any>, index: number) => {
      if (!missingIndices.includes(index)) {
        const val = parseFloat(row[header])
        if (!isNaN(val)) {
          validValues.push({ index, value: val })
        }
      }
    })

    if (validValues.length === 0) {
      missingIndices.forEach((idx) => {
        result[idx][header] = 0
      })
      return
    }

    if (method === 'mean') {
      const mean = validValues.reduce((sum, v) => sum + v.value, 0) / validValues.length
      missingIndices.forEach((idx) => {
        result[idx][header] = mean
      })
    } else if (method === 'forward') {
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
 * 检测异常值 - 使用99%置信区间方法
 * 均值 ± 2.576 * 标准差 作为99%置信区间
 * 超出此区间的数据点被标记为异常值
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

  // 计算均值和标准差
  const mean = values.reduce((sum, v) => sum + v, 0) / values.length
  const std = Math.sqrt(values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length)

  if (std === 0) return []

  // 99%置信区间：均值 ± 2.576 * 标准差
  const zScore = 2.576
  const lowerBound = mean - zScore * std
  const upperBound = mean + zScore * std

  const outliers: number[] = []
  data.forEach((row, index) => {
    const val = parseFloat(row[column])
    if (!isNaN(val) && (val < lowerBound || val > upperBound)) {
      outliers.push(index)
    }
  })

  return outliers
}

/**
 * 检测异常值 - 使用IQR（四分位距）方法（备选）
 * 更稳健的非参数方法，不依赖正态分布假设
 */
export function detectOutliersIQR(data: Record<string, any>[], column: string): number[] {
  const values: number[] = []
  data.forEach((row) => {
    const val = parseFloat(row[column])
    if (!isNaN(val)) {
      values.push(val)
    }
  })

  if (values.length < 4) return []

  // 排序
  const sorted = [...values].sort((a, b) => a - b)

  // 计算Q1（25%分位数）和Q3（75%分位数）
  const q1Index = Math.floor(sorted.length * 0.25)
  const q3Index = Math.floor(sorted.length * 0.75)
  const q1 = sorted[q1Index]
  const q3 = sorted[q3Index]
  const iqr = q3 - q1

  if (iqr === 0) return []

  // IQR方法：小于 Q1 - 1.5*IQR 或大于 Q3 + 1.5*IQR 的为异常值
  const lowerBound = q1 - 1.5 * iqr
  const upperBound = q3 + 1.5 * iqr

  const outliers: number[] = []
  data.forEach((row, index) => {
    const val = parseFloat(row[column])
    if (!isNaN(val) && (val < lowerBound || val > upperBound)) {
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

  if (fixes[timeColumn]) {
    fixed[timeColumn] = smartFormatTimestamp(fixes[timeColumn])
  }

  return fixed
}
