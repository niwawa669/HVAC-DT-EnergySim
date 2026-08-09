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
                        首列必须是时间戳（格式：YYYY-MM-DD HH:00 或 YYYY/MM/DD HH:00）
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
                        <span>时间范围: {{ dataTimeRange }}</span>
                        <span v-if="parseResult.warnings.length > 0">
                            警告: {{ parseResult.warnings.length }} 条
                        </span>
                    </div>
                </template>
            </el-alert>
        </div>

        <!-- 时间范围选择和预览控制 -->
        <div v-if="allData.length > 0" class="preview-controls">
            <div class="controls-row">
                <div class="time-range-selectors">
                    <el-date-picker v-model="startTime" type="datetime" placeholder="选择开始时间" format="YYYY-MM-DD HH:00"
                        value-format="YYYY-MM-DD HH:00" :disabled-date="disabledStartDate" style="width: 220px;" />
                    <span style="margin: 0 10px; color: #909399;">至</span>
                    <el-date-picker v-model="endTime" type="datetime" placeholder="选择结束时间" format="YYYY-MM-DD HH:00"
                        value-format="YYYY-MM-DD HH:00" :disabled-date="disabledEndDate" style="width: 220px;" />
                </div>
                <div class="controls-actions">
                    <el-button size="small" @click="resetTimeRange">重置范围</el-button>
                    <el-button size="small" type="primary" :disabled="!canUpdatePreview" @click="updatePreviewData">
                        <el-icon>
                            <Refresh />
                        </el-icon> 更新预览
                    </el-button>
                    <el-button size="small" type="success" @click="handleDataConfirm" :disabled="!canConfirm">
                        确认数据
                    </el-button>
                </div>
            </div>
            <!-- 显示当前筛选结果 -->
            <div class="filter-info" v-if="filteredData.length > 0">
                当前显示: {{ filteredData.length }} / {{ allData.length }} 行
                ({{ startTime }} ~ {{ endTime }})
            </div>
            <div class="filter-info" v-else>
                暂无匹配数据，请调整时间范围
            </div>
        </div>

        <!-- 数据预览表格 -->
        <div v-if="displayData.length > 0" class="data-preview">
            <div class="preview-header">
                <span>
                    数据预览
                    <el-tag size="small" type="info">
                        显示 {{ displayData.length }} / {{ allData.length }} 行
                    </el-tag>
                </span>
                <div class="preview-actions">
                    <el-button size="small" @click="showFullData = !showFullData">
                        {{ showFullData ? '收起' : '展开全部' }}
                    </el-button>
                </div>
            </div>

            <el-table :data="displayData" border stripe max-height="400" style="width: 100%" v-loading="tableLoading">
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
import { ref, computed, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Refresh } from '@element-plus/icons-vue'
import {
    parseDataFile,
    detectDelimiter,
    validateTimeSeriesWithErrors,
    smartFormatTimestamp,
    fillMissingValues,
    detectOutliers
} from '@/utils/dataProcessor'

// ===== 类型定义 =====
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

// ===== Props & Emits =====
const emit = defineEmits<{
    (e: 'data-confirmed', data: any): void
}>()

// ===== State =====
const fileList = ref<any[]>([])
const parseResult = ref<ParseResult | null>(null)
const validationResult = ref<ValidationResult | null>(null)
const showFullData = ref(true)  // ✅ 默认展开全部
const showErrorTable = ref(false)
const workingData = ref<Record<string, any>[]>([])
const tableLoading = ref(false)

// 时间范围
const startTime = ref<string>('')
const endTime = ref<string>('')
const filteredData = ref<Record<string, any>[]>([])
const allData = ref<Record<string, any>[]>([])
const canUpdatePreview = ref(false)
const isInitialized = ref(false)

// ===== Computed =====
const getTimeColumnName = () => {
    if (!parseResult.value) return ''
    return parseResult.value.headers[0] || ''
}

const isTimeColumn = (col: string) => {
    const timeCol = getTimeColumnName()
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

// ===== ✅ 显示数据 - 默认显示全部 =====
const displayData = computed(() => {
    const sourceData = filteredData.value.length > 0 ? filteredData.value : allData.value
    if (showFullData.value) {
        return sourceData
    }
    // 收起时显示10行
    return sourceData.slice(0, 10)
})

const dataTimeRange = computed(() => {
    if (allData.value.length === 0) return '无数据'
    const timeCol = getTimeColumnName()
    if (!timeCol) return '未检测到时间列'

    const times = allData.value.map(row => row[timeCol]).filter(t => t)
    if (times.length === 0) return '无有效时间'

    const sorted = [...times].sort()
    return `${sorted[0]} ~ ${sorted[sorted.length - 1]}`
})

const canConfirm = computed(() => {
    return parseResult.value !== null &&
        parseResult.value.errors.length === 0 &&
        validationResult.value !== null &&
        validationResult.value.isValid
})

// ===== 监听时间变化，启用更新按钮 =====
watch([startTime, endTime], () => {
    if (startTime.value && endTime.value && isInitialized.value) {
        canUpdatePreview.value = true
    }
})

// ===== 根据时间范围过滤数据 =====
const filterDataByTimeRange = (start: string, end: string) => {
    const timeCol = getTimeColumnName()
    if (!timeCol || allData.value.length === 0) return

    const startTimeMs = new Date(start).getTime()
    const endTimeMs = new Date(end).getTime()

    filteredData.value = allData.value.filter(row => {
        const timeStr = row[timeCol]
        if (!timeStr) return false
        const time = new Date(timeStr).getTime()
        return time >= startTimeMs && time <= endTimeMs
    })

    console.log(`筛选数据: ${filteredData.value.length} / ${allData.value.length} 行`)
}

// ===== 初始化时间范围（默认显示8月1日） =====
const initializeTimeRange = () => {
    const timeCol = getTimeColumnName()
    if (!timeCol || allData.value.length === 0) return

    const times = allData.value
        .map(row => row[timeCol])
        .filter(t => t && t !== '' && t !== null && t !== undefined && typeof t === 'string')

    if (times.length === 0) return

    const sorted = [...times].sort()

    // ===== 查找8月1日的数据 =====
    const targetDatePatterns = [
        '2025-08-01', '2025/08/01', '2025-8-1', '2025/8/1',
        '2024-08-01', '2024/08/01', '2024-8-1', '2024/8/1'
    ]

    let targetStartTime = null
    let targetEndTime = null
    let foundTargetDate = false

    for (const pattern of targetDatePatterns) {
        const matchingTimes = sorted.filter(t => t.startsWith(pattern))
        if (matchingTimes.length > 0) {
            targetStartTime = matchingTimes[0]
            targetEndTime = matchingTimes[matchingTimes.length - 1]
            foundTargetDate = true
            break
        }
    }

    if (!foundTargetDate) {
        const firstDay = sorted[0]?.split(' ')[0]
        if (firstDay) {
            const firstDayTimes = sorted.filter(t => t.startsWith(firstDay))
            if (firstDayTimes.length > 0) {
                targetStartTime = firstDayTimes[0]
                targetEndTime = firstDayTimes[firstDayTimes.length - 1]
            }
        }
    }

    if (!targetStartTime || !targetEndTime) {
        targetStartTime = sorted[0]
        targetEndTime = sorted[sorted.length - 1]
    }

    startTime.value = targetStartTime
    endTime.value = targetEndTime

    filterDataByTimeRange(targetStartTime, targetEndTime)

    isInitialized.value = true
    canUpdatePreview.value = false
}

// ===== Methods =====
const handleFileUpload = (file: any) => {
    fileList.value.push(file)

    workingData.value = []
    allData.value = []
    filteredData.value = []
    validationResult.value = null
    showErrorTable.value = false
    startTime.value = ''
    endTime.value = ''
    canUpdatePreview.value = false
    isInitialized.value = false

    const reader = new FileReader()
    reader.onload = (e: any) => {
        const content = e.target.result
        const delimiter = detectDelimiter(content)
        const result = parseDataFile(content, delimiter)
        parseResult.value = result

        if (result.errors.length === 0) {
            ElMessage.success(`成功解析 ${result.rowCount} 行数据`)

            workingData.value = result.data.map(row => ({ ...row }))
            allData.value = result.data.map(row => ({ ...row }))

            const timeColumn = getTimeColumnName()

            if (timeColumn) {
                const formattedData = workingData.value.map(row => {
                    const newRow = { ...row }
                    if (newRow[timeColumn]) {
                        newRow[timeColumn] = smartFormatTimestamp(newRow[timeColumn])
                    }
                    return newRow
                })
                workingData.value = formattedData
                allData.value = formattedData

                nextTick(() => {
                    initializeTimeRange()
                })

                const validation = validateTimeSeriesWithErrors(formattedData, timeColumn)
                validationResult.value = validation

                if (validation.errors.length > 0) {
                    showErrorTable.value = true
                    ElMessage.warning(`发现 ${validation.errors.length} 个数据错误`)
                } else {
                    ElMessage.success('数据校验通过！')
                }
            } else {
                ElMessage.warning('未检测到时间列，请确保第一列为时间数据')
            }
        } else {
            ElMessage.error(`解析失败: ${result.errors.join(', ')}`)
        }
    }
    reader.readAsText(file.raw)
}

const disabledStartDate = (time: Date) => {
    if (!endTime.value) return false
    const end = new Date(endTime.value)
    return time.getTime() > end.getTime()
}

const disabledEndDate = (time: Date) => {
    if (!startTime.value) return false
    const start = new Date(startTime.value)
    return time.getTime() < start.getTime()
}

const resetTimeRange = () => {
    const timeCol = getTimeColumnName()
    if (!timeCol || allData.value.length === 0) return

    const times = allData.value
        .map(row => row[timeCol])
        .filter(t => t && t !== '' && t !== null && t !== undefined)
        .sort()

    if (times.length === 0) return

    startTime.value = times[0]
    endTime.value = times[times.length - 1]
    canUpdatePreview.value = true
}

const updatePreviewData = () => {
    if (!startTime.value || !endTime.value) {
        ElMessage.warning('请选择完整的时间范围')
        return
    }

    const timeCol = getTimeColumnName()
    if (!timeCol) {
        ElMessage.warning('未检测到时间列')
        return
    }

    tableLoading.value = true

    try {
        filterDataByTimeRange(startTime.value, endTime.value)
        ElMessage.success(`筛选完成，显示 ${filteredData.value.length} 行数据`)
        canUpdatePreview.value = false
    } catch (error) {
        ElMessage.error('时间范围选择无效')
    } finally {
        tableLoading.value = false
    }
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

    const timeColumn = getTimeColumnName()
    const numericColumns = parseResult.value.headers.filter((h: string) => h !== timeColumn)

    const outliers: Record<string, number[]> = {}
    numericColumns.forEach((col: string) => {
        const result = detectOutliers(workingData.value, col)
        if (result.length > 0) {
            outliers[col] = result
        }
    })

    if (Object.keys(outliers).length > 0) {
        ElMessage.warning(`检测到 ${Object.keys(outliers).length} 列存在异常值`)
    }

    emit('data-confirmed', {
        data: workingData.value,
        headers: parseResult.value.headers,
        outliers: outliers,
        summary: validationResult.value?.summary
    })
}

// ===== 错误处理函数 =====
const handleSuggestionChange = (row: ValidationError) => {
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

    if (rowIndex < 0 || rowIndex >= workingData.value.length) {
        ElMessage.error('无效的行索引')
        return
    }

    if (isTimeColumn(column)) {
        const formatted = smartFormatTimestamp(fixValue)
        if (!formatted || !/^\d{4}-\d{2}-\d{2} \d{2}:00$/.test(formatted)) {
            ElMessage.warning('时间格式应为 "YYYY-MM-DD HH:00"')
            return
        }
        workingData.value[rowIndex][column] = formatted
        allData.value[rowIndex][column] = formatted
        const filteredIndex = filteredData.value.findIndex((_, idx) => idx === rowIndex)
        if (filteredIndex !== -1) {
            filteredData.value[filteredIndex][column] = formatted
        }
    } else {
        const numValue = parseFloat(fixValue)
        if (isNaN(numValue)) {
            ElMessage.warning('请输入有效的数字')
            return
        }
        workingData.value[rowIndex][column] = numValue
        allData.value[rowIndex][column] = numValue
        const filteredIndex = filteredData.value.findIndex((_, idx) => idx === rowIndex)
        if (filteredIndex !== -1) {
            filteredData.value[filteredIndex][column] = numValue
        }
    }

    const timeColumn = getTimeColumnName()
    if (timeColumn) {
        const validation = validateTimeSeriesWithErrors(workingData.value, timeColumn)
        validationResult.value = validation

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
                const formatted = smartFormatTimestamp(fixValue)
                if (formatted && /^\d{4}-\d{2}-\d{2} \d{2}:00$/.test(formatted)) {
                    workingData.value[rowIndex][column] = formatted
                    allData.value[rowIndex][column] = formatted
                    fixedCount++
                }
            } else {
                const numValue = parseFloat(fixValue)
                if (!isNaN(numValue)) {
                    workingData.value[rowIndex][column] = numValue
                    allData.value[rowIndex][column] = numValue
                    fixedCount++
                }
            }
        })

        const timeColumn = getTimeColumnName()
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
    flex-wrap: wrap;
}

.preview-controls {
    margin-top: 16px;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;
}

.controls-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}

.time-range-selectors {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
}

.controls-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.filter-info {
    margin-top: 10px;
    font-size: 13px;
    color: #606266;
    text-align: center;
    background: #e8f0fe;
    padding: 4px 12px;
    border-radius: 4px;
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

@media (max-width: 768px) {
    .controls-row {
        flex-direction: column;
        align-items: stretch;
    }

    .time-range-selectors {
        flex-direction: column;
        align-items: stretch;
    }

    .time-range-selectors span {
        text-align: center;
        margin: 4px 0 !important;
    }

    .controls-actions {
        justify-content: center;
    }
}
</style>