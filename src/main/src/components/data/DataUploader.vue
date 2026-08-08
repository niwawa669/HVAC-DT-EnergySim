<template>
    <div class="data-uploader">
        <!-- 上传区域 -->
        <el-upload drag action="#" :auto-upload="false" :on-change="handleFileUpload" :file-list="fileList" multiple
            accept=".csv,.txt" class="upload-area">
            <el-icon class="el-icon--upload">
                <UploadFilled />
            </el-icon>
            <div class="el-upload__text">
                拖拽数据文件到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
                <div class="el-upload__tip">
                    <el-text size="small" type="info">
                        支持 .csv 和 .txt 格式<br>
                        首列必须是时间戳（格式：YYYY-MM-DD HH:00），其他列必须为数值
                    </el-text>
                </div>
            </template>
        </el-upload>

        <!-- 解析状态 -->
        <div v-if="parseResult" class="parse-status">
            <el-alert :title="parseResult.errors.length > 0 ? '解析完成，存在错误' : '解析成功'"
                :type="parseResult.errors.length > 0 ? 'error' : 'success'" :closable="false">
                <template #default>
                    <div class="parse-detail">
                        <span>数据行数: {{ parseResult.rowCount }}</span>
                        <span>列数: {{ parseResult.columnCount }}</span>
                        <span v-if="parseResult.warnings.length > 0">
                            警告: {{ parseResult.warnings.length }} 条
                        </span>
                    </div>
                </template>
            </el-alert>
        </div>

        <!-- 数据预览表格 -->
        <div v-if="previewData.length > 0" class="data-preview">
            <div class="preview-header">
                <span>数据预览 (前10行)</span>
                <div class="preview-actions">
                    <el-button size="small" @click="showFullData = !showFullData">
                        {{ showFullData ? '收起' : '展开全部' }}
                    </el-button>
                    <el-button v-if="validationResult && !validationResult.isValid" size="small" type="warning"
                        @click="showErrorTable = !showErrorTable">
                        {{ showErrorTable ? '隐藏' : '查看' }}错误数据 ({{ validationResult.errors.length }})
                    </el-button>
                    <el-button size="small" type="primary" @click="handleDataConfirm">
                        确认数据
                    </el-button>
                </div>
            </div>

            <el-table :data="displayData" border stripe max-height="400" style="width: 100%">
                <el-table-column v-for="col in displayHeaders" :key="col" :prop="col" :label="col" min-width="120"
                    :class-name="getColumnClass(col)">
                    <template #default="{ row }">
                        <span :style="getCellStyle(row, col)">
                            {{ row[col] }}
                        </span>
                    </template>
                </el-table-column>
            </el-table>
        </div>

        <!-- 错误数据表格 -->
        <div v-if="showErrorTable && validationResult && validationResult.errors.length > 0" class="error-table">
            <el-divider>
                <span style="color: #f56c6c;">错误数据列表 ({{ validationResult.errors.length }} 条)</span>
            </el-divider>

            <el-alert title="错误数据说明" type="error" :closable="false" style="margin-bottom: 16px;">
                <template #default>
                    <ul style="margin: 8px 0; padding-left: 20px;">
                        <li>时间戳格式必须为 <code>YYYY-MM-DD HH:00</code>（如：2024-01-01 00:00）</li>
                        <li>除时间戳列外，所有列必须为数值</li>
                        <li>在"建议修正值"列输入修正值后，点击"应用修正"按钮</li>
                    </ul>
                </template>
            </el-alert>

            <el-table :data="errorDataList" border stripe style="width: 100%" max-height="400">
                <el-table-column prop="rowIndex" label="行号" width="80">
                    <template #default="{ row }">
                        第 {{ row.rowIndex + 1 }} 行
                    </template>
                </el-table-column>
                <el-table-column prop="column" label="列名" width="140">
                    <template #default="{ row }">
                        <el-tag :type="isTimeColumn(row.column) ? 'primary' : 'danger'" size="small">
                            {{ row.column }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="value" label="原始值" min-width="150">
                    <template #default="{ row }">
                        <span style="color: #f56c6c; font-weight: bold;">{{ row.value === '' || row.value === null ?
                            '(空)' : row.value }}</span>
                    </template>
                </el-table-column>
                <el-table-column prop="message" label="错误信息" min-width="200" />
                <el-table-column prop="suggestion" label="建议修正值" min-width="150">
                    <template #default="{ row }">
                        <el-input v-model="row.suggestion" size="small" placeholder="输入修正值"
                            @input="handleSuggestionChange(row)" />
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="120">
                    <template #default="{ row }">
                        <el-button size="small" type="primary" @click="applyFix(row)"
                            :disabled="!row.suggestion && row.suggestion !== 0">
                            应用修正
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>

            <div style="margin-top: 16px; text-align: right;">
                <el-button v-if="validationResult && validationResult.errors.length > 0" type="warning" size="small"
                    @click="autoFixAll">
                    一键修正所有错误
                </el-button>
            </div>
        </div>

        <!-- 数据校验结果 -->
        <div v-if="validationResult" class="validation-result">
            <el-divider>数据校验结果</el-divider>

            <el-row :gutter="20">
                <el-col :span="6">
                    <el-statistic title="总行数" :value="validationResult.summary.totalRows" />
                </el-col>
                <el-col :span="6">
                    <el-statistic title="有效行数" :value="validationResult.summary.validRows"
                        :value-style="{ color: '#67c23a' }" />
                </el-col>
                <el-col :span="6">
                    <el-statistic title="无效行数" :value="validationResult.summary.invalidRows"
                        :value-style="{ color: '#f56c6c' }" />
                </el-col>
                <el-col :span="6">
                    <el-statistic title="错误数量" :value="validationResult.errors.length"
                        :value-style="{ color: '#f56c6c' }" />
                </el-col>
            </el-row>

            <div v-if="validationResult.warnings.length > 0" style="margin-top: 16px;">
                <el-alert title="警告信息" type="warning" :closable="false">
                    <ul>
                        <li v-for="(warn, index) in validationResult.warnings" :key="index">
                            {{ warn }}
                        </li>
                    </ul>
                </el-alert>
            </div>

            <div v-if="validationResult.isValid" style="margin-top: 16px;">
                <el-alert title="✅ 所有数据校验通过！" type="success" :closable="false" show-icon />
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import {
    parseDataFile,
    detectDelimiter,
    validateTimeSeriesWithErrors,
    formatTimestamp,
    fillMissingValues
} from '@/utils/dataProcessor'

// 类型定义
interface ParseResult {
    headers: string[]
    data: Record<string, any>[]
    rowCount: number
    columnCount: number
    previewData: Record<string, any>[]
    warnings: string[]
    errors: string[]
}

interface ValidationError {
    rowIndex: number
    column: string
    value: any
    message: string
    suggestion?: any
}

interface ValidationResult {
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

// Props
const emit = defineEmits<{
    (e: 'data-confirmed', data: any): void
}>()

// State
const fileList = ref<any[]>([])
const parseResult = ref<ParseResult | null>(null)
const validationResult = ref<ValidationResult | null>(null)
const showFullData = ref(false)
const showErrorTable = ref(false)
const rawContent = ref('')
const workingData = ref<Record<string, any>[]>([])

// Computed
const previewData = computed(() => {
    if (!parseResult.value) return []
    return parseResult.value.previewData || []
})

const displayData = computed(() => {
    if (!parseResult.value) return []
    // 如果有工作数据，使用工作数据
    if (workingData.value.length > 0) {
        return showFullData.value ? workingData.value : workingData.value.slice(0, 10)
    }
    return showFullData.value ? parseResult.value.data : parseResult.value.previewData
})

const displayHeaders = computed(() => {
    if (!parseResult.value) return []
    return parseResult.value.headers
})

const errorDataList = computed(() => {
    if (!validationResult.value) return []
    return validationResult.value.errors.map(err => ({
        ...err,
        suggestion: err.suggestion !== undefined && err.suggestion !== null ? err.suggestion : ''
    }))
})

// Methods
const getTimeColumn = () => {
    if (!parseResult.value) return ''
    return parseResult.value.headers.find((h: string) =>
        h.includes('时间') || h.includes('time') || h.includes('日期') || h.includes('date')
    ) || ''
}

const isTimeColumn = (col: string) => {
    const timeCol = getTimeColumn()
    return col === timeCol
}

const getColumnClass = (col: string) => {
    return isTimeColumn(col) ? 'time-column' : ''
}

const getCellStyle = (row: any, col: string) => {
    const value = row[col]
    if (value === '' || value === null || value === undefined) {
        return { color: '#f56c6c' }
    }
    if (typeof value === 'string' && isNaN(parseFloat(value)) && !isTimeColumn(col)) {
        return { color: '#f56c6c' }
    }
    return {}
}

const handleFileUpload = (file: any) => {
    fileList.value.push(file)

    // 重置状态
    workingData.value = []
    validationResult.value = null
    showErrorTable.value = false

    const reader = new FileReader()
    reader.onload = (e: any) => {
        const content = e.target.result
        rawContent.value = content

        // 检测分隔符并解析
        const delimiter = detectDelimiter(content)
        const result = parseDataFile(content, delimiter)
        parseResult.value = result

        if (result.errors.length === 0) {
            ElMessage.success(`成功解析 ${result.rowCount} 行数据`)

            // 初始化工作数据
            workingData.value = result.data.map(row => ({ ...row }))

            // 自动校验时间序列
            const timeColumn = getTimeColumn()

            if (timeColumn) {
                // 先格式化时间戳
                const formattedData = workingData.value.map(row => {
                    const newRow = { ...row }
                    if (newRow[timeColumn]) {
                        newRow[timeColumn] = formatTimestamp(newRow[timeColumn])
                    }
                    return newRow
                })
                workingData.value = formattedData

                const validation = validateTimeSeriesWithErrors(formattedData, timeColumn)
                validationResult.value = validation

                // 如果有错误，自动显示错误表格
                if (validation.errors.length > 0) {
                    showErrorTable.value = true
                    ElMessage.warning(`发现 ${validation.errors.length} 个数据错误`)
                } else {
                    ElMessage.success('数据校验通过！')
                }
            } else {
                ElMessage.warning('未找到时间列，请确保列名包含"时间"、"日期"、"time"或"date"')
            }
        } else {
            ElMessage.error(`解析失败: ${result.errors.join(', ')}`)
        }
    }
    reader.readAsText(file.raw)
}

const handleSuggestionChange = (row: ValidationError) => {
    // 更新建议值
    const error = validationResult.value?.errors.find(e =>
        e.rowIndex === row.rowIndex && e.column === row.column
    )
    if (error) {
        error.suggestion = row.suggestion
    }
}

const applyFix = (row: ValidationError) => {
    if (!parseResult.value || !validationResult.value || !workingData.value.length) {
        ElMessage.warning('数据未就绪')
        return
    }

    const fixValue = row.suggestion !== undefined && row.suggestion !== '' ? row.suggestion : null

    if (fixValue === null || fixValue === '') {
        ElMessage.warning('请输入修正值')
        return
    }

    const rowIndex = row.rowIndex
    const column = row.column

    // 检查行索引是否有效
    if (rowIndex < 0 || rowIndex >= workingData.value.length) {
        ElMessage.error('无效的行索引')
        return
    }

    // 验证修正值
    if (isTimeColumn(column)) {
        // 时间列：验证格式
        const formatted = formatTimestamp(fixValue)
        if (!formatted || !/^\d{4}-\d{2}-\d{2} \d{2}:00$/.test(formatted)) {
            ElMessage.warning('时间格式应为 "YYYY-MM-DD HH:00"，例如：2024-01-01 00:00')
            return
        }
        // 更新数据
        workingData.value[rowIndex][column] = formatted
    } else {
        // 数值列：验证是否为数字
        const numValue = parseFloat(fixValue)
        if (isNaN(numValue)) {
            ElMessage.warning('请输入有效的数字')
            return
        }
        // 更新数据
        workingData.value[rowIndex][column] = numValue
    }

    // 重新校验
    const timeColumn = getTimeColumn()
    if (timeColumn) {
        const validation = validateTimeSeriesWithErrors(workingData.value, timeColumn)
        validationResult.value = validation

        // 如果还有错误
        if (validation.errors.length > 0) {
            ElMessage.success(`已修正 1 个错误，剩余 ${validation.errors.length} 个`)
        } else {
            showErrorTable.value = false
            ElMessage.success('🎉 所有错误已修正完成！')
        }
    }
}

const autoFixAll = () => {
    if (!validationResult.value || !workingData.value.length) return

    const errors = validationResult.value.errors
    if (errors.length === 0) {
        ElMessage.info('没有需要修正的错误')
        return
    }

    ElMessageBox.confirm(
        `将自动修正所有 ${errors.length} 个错误（使用建议值），确定继续吗？`,
        '一键修正',
        {
            confirmButtonText: '确定修正',
            cancelButtonText: '取消',
            type: 'info'
        }
    ).then(() => {
        let fixedCount = 0

        errors.forEach(error => {
            const fixValue = error.suggestion !== undefined && error.suggestion !== '' ? error.suggestion : null
            if (fixValue === null || fixValue === '') return

            const rowIndex = error.rowIndex
            const column = error.column

            if (rowIndex < 0 || rowIndex >= workingData.value.length) return

            if (isTimeColumn(column)) {
                const formatted = formatTimestamp(fixValue)
                if (formatted && /^\d{4}-\d{2}-\d{2} \d{2}:00$/.test(formatted)) {
                    workingData.value[rowIndex][column] = formatted
                    fixedCount++
                }
            } else {
                const numValue = parseFloat(fixValue)
                if (!isNaN(numValue)) {
                    workingData.value[rowIndex][column] = numValue
                    fixedCount++
                }
            }
        })

        // 重新校验
        const timeColumn = getTimeColumn()
        if (timeColumn) {
            const validation = validateTimeSeriesWithErrors(workingData.value, timeColumn)
            validationResult.value = validation

            if (validation.errors.length === 0) {
                showErrorTable.value = false
                ElMessage.success(`🎉 成功修正 ${fixedCount} 个错误，所有数据校验通过！`)
            } else {
                ElMessage.warning(`修正了 ${fixedCount} 个错误，剩余 ${validation.errors.length} 个需要手动处理`)
            }
        }
    }).catch(() => { })
}

const handleDataConfirm = () => {
    if (!parseResult.value) {
        ElMessage.warning('请先上传数据文件')
        return
    }

    if (parseResult.value.errors.length > 0) {
        ElMessage.warning('数据存在解析错误，请检查文件格式')
        return
    }

    if (!validationResult.value) {
        ElMessage.warning('请先进行数据校验')
        return
    }

    // 检查是否有未修正的错误
    const errors = validationResult.value.errors
    if (errors.length > 0) {
        ElMessageBox.confirm(
            `数据中仍有 ${errors.length} 个错误未修正，确定要继续吗？`,
            '警告',
            {
                confirmButtonText: '继续',
                cancelButtonText: '取消',
                type: 'warning'
            }
        ).then(() => {
            confirmData()
        }).catch(() => { })
        return
    }

    confirmData()
}

const confirmData = () => {
    if (!parseResult.value || !workingData.value.length) return

    // 检测异常值
    const timeColumn = getTimeColumn()
    const numericColumns = parseResult.value.headers.filter((h: string) => h !== timeColumn)

    const outliers: Record<string, number[]> = {}
    numericColumns.forEach((col: string) => {
        const values = workingData.value.map((row: any) => parseFloat(row[col])).filter((v: any) => !isNaN(v))
        if (values.length > 3) {
            const mean = values.reduce((a: any, b: any) => a + b, 0) / values.length
            const std = Math.sqrt(values.reduce((a: any, b: any) => a + Math.pow(b - mean, 2), 0) / values.length)
            if (std > 0) {
                workingData.value.forEach((row: any, index: number) => {
                    const val = parseFloat(row[col])
                    if (!isNaN(val) && Math.abs(val - mean) > 3 * std) {
                        if (!outliers[col]) outliers[col] = []
                        outliers[col].push(index)
                    }
                })
            }
        }
    })

    if (Object.keys(outliers).length > 0) {
        ElMessage.warning(`检测到 ${Object.keys(outliers).length} 列存在异常值`)
    }

    // 触发确认事件
    emit('data-confirmed', {
        data: workingData.value,
        headers: parseResult.value.headers,
        outliers: outliers,
        summary: validationResult.value?.summary
    })
}
</script>

<style scoped>
.data-uploader {
    padding: 10px 0;
}

.upload-area {
    width: 100%;
}

.parse-status {
    margin-top: 16px;
}

.parse-detail {
    display: flex;
    gap: 20px;
    margin-top: 8px;
    font-size: 13px;
    color: #606266;
}

.data-preview {
    margin-top: 20px;
}

.preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    flex-wrap: wrap;
    gap: 8px;
}

.preview-header span {
    font-weight: 500;
    font-size: 15px;
}

.preview-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.error-table {
    margin-top: 20px;
}

.validation-result {
    margin-top: 20px;
}

:deep(.time-column) {
    color: #409EFF;
    font-weight: 500;
}

:deep(.el-statistic) {
    text-align: center;
}

:deep(.el-table .cell) {
    word-break: break-all;
}
</style>