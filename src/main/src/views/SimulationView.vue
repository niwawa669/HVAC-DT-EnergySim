<template>
    <div class="simulation-view">
        <!-- ===== 顶部信息栏 ===== -->
        <div class="simulation-header">
            <el-page-header @back="goBack" content="仿真运行监控" />
            <div class="header-status">
                <el-tag :type="statusType" size="large">
                    <el-icon>
                        <component :is="statusIcon" />
                    </el-icon>
                    {{ statusText }}
                </el-tag>
                <span class="task-id">任务ID: {{ taskId }}</span>
                <span class="connection-status" :class="{ connected: isConnected }">
                    {{ isConnected ? '🟢 已连接' : '🔴 未连接' }}
                </span>
            </div>
        </div>

        <!-- ===== 主要监控区域 ===== -->
        <el-row :gutter="20" class="monitor-row">
            <el-col :span="8">
                <el-card shadow="hover" class="status-card">
                    <div class="progress-container">
                        <el-progress type="circle" :percentage="progress" :status="progressStatus" :width="160"
                            :stroke-width="12">
                            <template #default>
                                <div class="progress-text">
                                    <span class="percentage">{{ progress }}%</span>
                                    <span class="sub-text">完成度</span>
                                </div>
                            </template>
                        </el-progress>

                        <div class="progress-info">
                            <div class="info-item">
                                <span class="label">当前周数</span>
                                <span class="value">{{ currentWeek }} / 52</span>
                            </div>
                            <div class="info-item">
                                <span class="label">运行时间</span>
                                <span class="value">{{ elapsedTime }}</span>
                            </div>
                            <div class="info-item" v-if="estimatedRemaining">
                                <span class="label">预计剩余</span>
                                <span class="value">{{ estimatedRemaining }}</span>
                            </div>
                        </div>
                    </div>
                </el-card>
            </el-col>

            <el-col :span="16">
                <el-row :gutter="20">
                    <el-col :span="12" v-for="metric in metrics" :key="metric.label">
                        <el-card shadow="hover" class="metric-card">
                            <div class="metric-content">
                                <div class="metric-icon" :style="{ backgroundColor: metric.bgColor }">
                                    <el-icon :size="24" :color="metric.color">
                                        <component :is="metric.icon" />
                                    </el-icon>
                                </div>
                                <div class="metric-info">
                                    <span class="metric-label">{{ metric.label }}</span>
                                    <span class="metric-value">{{ metric.value }}</span>
                                </div>
                            </div>
                        </el-card>
                    </el-col>
                </el-row>
            </el-col>
        </el-row>

        <!-- ===== 图表区域 ===== -->
        <el-card shadow="hover" class="chart-card">
            <template #header>
                <div class="chart-header">
                    <span>逐周能耗与负荷趋势</span>
                    <div class="chart-controls">
                        <el-tag size="small" type="info">
                            {{ receivedWeeks > 0 ? `已接收 ${receivedWeeks} 周数据` : '等待数据...' }}
                        </el-tag>
                    </div>
                </div>
            </template>
            <div ref="chartRef" class="chart-container"></div>
        </el-card>

        <!-- ===== 日志区域 ===== -->
        <el-card shadow="hover" class="log-card">
            <template #header>
                <div class="log-header">
                    <span>运行日志</span>
                    <div class="log-actions">
                        <el-button size="small" @click="clearLogs">清空</el-button>
                        <el-button size="small" type="primary" @click="toggleLogAutoScroll">
                            {{ logAutoScroll ? '暂停滚动' : '自动滚动' }}
                        </el-button>
                        <el-button v-if="isCompleted || progress > 0" size="small" type="warning"
                            :loading="isRestarting" @click="handleRestartSimulation">
                            <el-icon>
                                <Refresh />
                            </el-icon> 重新仿真
                        </el-button>
                    </div>
                </div>
            </template>
            <div ref="logContainerRef" class="log-container">
                <div v-for="(log, index) in logs" :key="index" class="log-item">
                    <span class="log-time">{{ log.time }}</span>
                    <span class="log-message" :class="log.type">
                        {{ log.message }}
                    </span>
                </div>
                <div v-if="logs.length === 0" class="log-empty">
                    <el-empty description="暂无日志" :image-size="60" />
                </div>
            </div>
        </el-card>

        <!-- ===== 仿真结果区域 ===== -->
        <el-card v-if="isCompleted" shadow="hover" class="result-card">
            <template #header>
                <div class="result-header">
                    <span>📊 仿真结果汇总</span>
                    <div class="result-actions">
                        <el-button type="primary" size="small" :loading="generating"
                            @click="handleGenerateReport">
                            生成报告
                        </el-button>
                    </div>
                </div>
            </template>

            <!-- ===== 六个冷源站关键指标 ===== -->
            <el-row :gutter="20">
                <el-col :span="4" v-for="item in resultMetrics" :key="item.label">
                    <div class="result-item">
                        <div class="result-label">{{ item.label }}</div>
                        <div class="result-value" :style="{ color: item.color }">
                            {{ item.value }}
                        </div>
                        <div class="result-unit">{{ item.unit }}</div>
                    </div>
                </el-col>
            </el-row>

            <!-- 雷达图 -->
            <div ref="radarChartRef" class="radar-chart-container"></div>

            <!-- 五维评分明细：位置（分数）与原始值、评价基准对照 -->
            <el-table v-if="radarMetrics.length" :data="radarMetrics" size="small" border
                class="radar-benchmark-table">
                <el-table-column prop="name" label="维度" width="150" />
                <el-table-column prop="display" label="当前值" width="160" />
                <el-table-column label="得分" width="80" align="center">
                    <template #default="{ row }">{{ row.available ? row.score : '—' }}</template>
                </el-table-column>
                <el-table-column label="评价" width="95" align="center">
                    <template #default="{ row }">
                        <el-tag :type="levelTagType(row.level)" size="small">{{ row.level }}</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="评价基准" min-width="260">
                    <template #default="{ row }">
                        <el-tooltip :content="row.source" placement="top">
                            <span>{{ row.benchmark }}</span>
                        </el-tooltip>
                    </template>
                </el-table-column>
            </el-table>
            <div v-if="radarMetrics.length" class="radar-benchmark-note">
                雷达图为 0–100 分归一化评分，越靠外表示该维度表现越好；评价基准依据
                GB 50189-2015、GB 55015-2021、GB 19577-2024、GB/T 51161-2016、GB/T 51366-2019，
                单位面积指标为冷源站口径（按建筑总量约 35% 折算）。悬停“评价基准”可查看具体来源。
                分数按当前基准折算：基准或阈值更新后，历史结果的分数与等级会随之变化，结果数值本身不变。
            </div>
            <el-alert v-if="radarMissing.length" class="radar-missing-note" type="info"
                :closable="false" show-icon
                :title="'部分维度缺失（旧结果），未参与雷达绘制：' + radarMissing.join('、') + '；请重新仿真以补齐指标。'" />
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
    DataBoard, TrendCharts, Sunny, Finished,
    Timer, Check, Loading
} from '@element-plus/icons-vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { formatNumber } from '@/utils/format'
import { buildRadarMetrics, type MetricLevel, type RadarMetric } from '@/utils/radarMetrics'
import { getSimulationResults, getSimulationStatus, restartSimulation } from '@/api/simulation'
import { generateReport } from '@/api/reports'

// ===== 路由 =====
const router = useRouter()
const route = useRoute()
const taskId = route.params.taskId as string

// ===== 状态 =====
const progress = ref(0)
const currentWeek = ref(0)
const receivedWeeks = ref(0)
const elapsedTime = ref('00:00:00')
const estimatedRemaining = ref('')
const logAutoScroll = ref(true)
const isCompleted = ref(false)
const isRestarting = ref(false)
const chartRef = ref<HTMLDivElement | null>(null)
const radarChartRef = ref<HTMLDivElement | null>(null)
const logContainerRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let radarChartInstance: echarts.ECharts | null = null
let timer: ReturnType<typeof setInterval> | null = null
let startTime: Date | null = null

// ===== 结果数据 =====
const resultData = ref<any>(null)

// ===== 指标数据（监控过程中显示） =====
const metrics = ref([
    {
        label: '本周累计能耗',
        value: '0 kWh',
        icon: 'DataBoard',
        color: '#409EFF',
        bgColor: 'rgba(64, 158, 255, 0.1)'
    },
    {
        label: '平均COP',
        value: '0.00',
        icon: 'TrendCharts',
        color: '#67C23A',
        bgColor: 'rgba(103, 194, 58, 0.1)'
    },
    {
        label: '平均室外温度',
        value: '0 °C',
        icon: 'Sunny',
        color: '#E6A23C',
        bgColor: 'rgba(230, 162, 60, 0.1)'
    },
    {
        label: '已推送周数',
        value: '0/52',
        icon: 'Finished',
        color: '#F56C6C',
        bgColor: 'rgba(245, 108, 108, 0.1)'
    }
])

// ===== 六个冷源站关键指标（结果汇总） =====
const resultMetrics = computed(() => {
    if (!resultData.value) return []

    const summary = resultData.value.summary || {}

    // ===== 尖峰逐时冷负荷：优先取结果中的 peak_context =====
    const peak = (resultData.value as any).peak_context
    const peakCoolingLoad = peak?.load ?? summary.peakCoolingLoad ?? 0

    // ===== 冷源站综合平均能效 EERa = 总供冷量 / 总耗电量 =====
    const totalQStation = summary.totalQStation || 0
    const totalEnergy = summary.totalEnergy || 0
    const eera = summary.systemEER ?? (totalEnergy > 0 ? totalQStation / totalEnergy : 0)

    return [
        {
            label: '建筑总冷负荷',
            value: formatNumber(summary.totalCoolingLoad || 0),
            unit: 'kWh',
            color: '#409EFF'
        },
        {
            label: '建筑尖峰冷负荷',
            value: formatNumber(peakCoolingLoad),
            unit: 'kW',
            color: '#E6A23C'
        },
        {
            label: '冷源站总供冷量',
            value: formatNumber(summary.totalQStation || 0),
            unit: 'kWh',
            color: '#67C23A'
        },
        {
            label: '冷源站总耗电量',
            value: formatNumber(summary.totalEnergy || 0),
            unit: 'kWh',
            color: '#F56C6C'
        },
        {
            label: '冷源站综合平均能效',
            value: eera.toFixed(2),
            unit: '-',
            color: '#9B59B6'
        },
        {
            label: '冷源站空调运行碳排放量',
            value: formatNumber(summary.carbonEmission || 0),
            unit: 'kg CO₂',
            color: '#909399'
        }
    ]
})

// ===== 日志 =====
interface LogEntry {
    time: string
    message: string
    type: 'info' | 'success' | 'warning' | 'error'
}

const logs = ref<LogEntry[]>([])

// ===== 图表数据 =====
const chartData = ref({
    weeks: [] as string[],
    coolingLoad: [] as number[],
    energyConsumption: [] as number[],
    totalQStation: [] as number[],
    peakCoolingLoad: [] as number[]
})

// ===== 计算属性 =====
const statusText = computed(() => {
    if (progress.value === 100) return '仿真完成 ✅'
    if (progress.value > 0) return '运行中'
    return '等待开始'
})

const statusType = computed(() => {
    if (progress.value === 100) return 'success'
    if (progress.value > 0) return 'warning'
    return 'info'
})

const statusIcon = computed(() => {
    if (progress.value === 100) return 'Check'
    if (progress.value > 0) return 'Loading'
    return 'Timer'
})

const progressStatus = computed(() => {
    if (progress.value === 100) return 'success'
    return ''
})

// ===== WebSocket =====
const wsUrl = `ws://localhost:8000/ws/simulate/${taskId}`
console.log('🌐 WebSocket URL:', wsUrl)

const { isConnected, onMessage, onError, sendMessage, disconnect } = useWebSocket(wsUrl)

// ===== WebSocket 消息处理 =====
const handleWebSocketMessage = (message: any) => {
    console.log('📨 处理 WebSocket 消息:', message)

    switch (message.type) {
        case 'connected':
            addLog('✅ WebSocket 连接成功', 'success')
            sendMessage('ping')
            break

        case 'pong':
            break

        case 'started':
            addLog('🚀 仿真开始计算...', 'info')
            break

        case 'progress':
            if (message.data) {
                const data = message.data
                progress.value = data.progressPercentage
                currentWeek.value = data.weekNumber
                receivedWeeks.value++

                metrics.value = [
                    {
                        label: '本周累计能耗',
                        value: formatNumber(data.totalEnergyConsumption) + ' kWh',
                        icon: 'DataBoard',
                        color: '#409EFF',
                        bgColor: 'rgba(64, 158, 255, 0.1)'
                    },
                    {
                        label: '平均COP',
                        value: data.avgSystemCop ? data.avgSystemCop.toFixed(2) : '0.00',
                        icon: 'TrendCharts',
                        color: '#67C23A',
                        bgColor: 'rgba(103, 194, 58, 0.1)'
                    },
                    {
                        label: '平均室外温度',
                        value: data.avgOutdoorTemp ? data.avgOutdoorTemp.toFixed(1) + ' °C' : '0 °C',
                        icon: 'Sunny',
                        color: '#E6A23C',
                        bgColor: 'rgba(230, 162, 60, 0.1)'
                    },
                    {
                        label: '已推送周数',
                        value: `${receivedWeeks.value}/52`,
                        icon: 'Finished',
                        color: '#F56C6C',
                        bgColor: 'rgba(245, 108, 108, 0.1)'
                    }
                ]

                // ===== 更新图表数据 =====
                chartData.value.weeks.push(`第${data.weekNumber}周`)
                chartData.value.coolingLoad.push(data.totalCoolingLoad || 0)
                chartData.value.totalQStation.push(data.totalQStation || 0)
                chartData.value.energyConsumption.push(data.totalEnergyConsumption || 0)
                chartData.value.peakCoolingLoad.push(data.peakCoolingLoad || 0)

                addLog(`📊 第${data.weekNumber}周数据已接收`, 'info')
                updateChart()
            }
            break

        case 'completed':
            progress.value = 100
            isCompleted.value = true
            resultData.value = { summary: message.summary, weekly: [], monthly: [], meta: {} }
            addLog('✅ 仿真计算完成！', 'success')
            ElMessage.success('仿真计算完成！')
            // 拉取七区块结果：指标与图表一律以结果契约字段为准，不用推送数据拼装
            void loadFullResult()

            if (message.summary) {
                addLog(`📈 总能耗: ${formatNumber(message.summary.totalEnergy)} kWh`, 'info')
            }

            nextTick(() => {
                initRadarChart()
            })
            break

        case 'failed':
            addLog(`❌ 仿真失败: ${message.error || '未知错误'}`, 'error')
            ElMessage.error(`仿真失败: ${message.error || '未知错误'}`)
            break

        case 'cancelled':
            addLog('⏹️ 仿真已取消', 'warning')
            ElMessage.warning('仿真已取消')
            break

        default:
            console.log('未知消息类型:', message)
    }
}

// ===== 拉取完整结果（七区块）=====
const loadFullResult = async () => {
    try {
        const res = await getSimulationResults(taskId)
        resultData.value = res as any
        addLog(
            `📦 结果已加载：${res.meta.totalHours} 小时 / ${res.weekly.length} 周 / ${res.monthly.length} 月`,
            'info'
        )
        nextTick(() => initRadarChart())
    } catch (e: any) {
        addLog('⚠️ 完整结果获取失败：' + (e?.message || '未知错误'), 'warning')
    }
}

// ===== 注册 WebSocket 回调 =====
let unregisterMessage: (() => void) | null = null
let unregisterError: (() => void) | null = null

// ===== 日志方法 =====
const addLog = (message: string, type: LogEntry['type'] = 'info') => {
    const time = new Date().toLocaleTimeString()
    logs.value.unshift({ time, message, type })

    if (logs.value.length > 100) {
        logs.value = logs.value.slice(0, 100)
    }

    if (logAutoScroll.value) {
        nextTick(() => {
            if (logContainerRef.value) {
                logContainerRef.value.scrollTop = 0
            }
        })
    }
}

const clearLogs = () => {
    logs.value = []
}

const toggleLogAutoScroll = () => {
    logAutoScroll.value = !logAutoScroll.value
}

// ===== 重置所有数据 =====
const resetAllData = () => {
    progress.value = 0
    currentWeek.value = 0
    receivedWeeks.value = 0
    elapsedTime.value = '00:00:00'
    estimatedRemaining.value = ''
    isCompleted.value = false
    resultData.value = null
    startTime = new Date()

    metrics.value = [
        {
            label: '本周累计能耗',
            value: '0 kWh',
            icon: 'DataBoard',
            color: '#409EFF',
            bgColor: 'rgba(64, 158, 255, 0.1)'
        },
        {
            label: '平均COP',
            value: '0.00',
            icon: 'TrendCharts',
            color: '#67C23A',
            bgColor: 'rgba(103, 194, 58, 0.1)'
        },
        {
            label: '平均室外温度',
            value: '0 °C',
            icon: 'Sunny',
            color: '#E6A23C',
            bgColor: 'rgba(230, 162, 60, 0.1)'
        },
        {
            label: '已推送周数',
            value: '0/52',
            icon: 'Finished',
            color: '#F56C6C',
            bgColor: 'rgba(245, 108, 108, 0.1)'
        }
    ]

    chartData.value = {
        weeks: [],
        coolingLoad: [],
        energyConsumption: [],
        totalQStation: [],
        peakCoolingLoad: []
    }

    logs.value = []

    if (chartInstance) {
        chartInstance.clear()
        initChart()
    }

    if (radarChartInstance) {
        radarChartInstance.clear()
        radarChartInstance = null
    }
}

// ===== 重新仿真 =====
const handleRestartSimulation = async () => {
    if (isRestarting.value) return

    try {
        await ElMessageBox.confirm(
            '重新仿真将清除当前所有数据并重新开始，确定继续吗？',
            '确认重新仿真',
            {
                confirmButtonText: '确定重新仿真',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )
    } catch {
        return
    }

    isRestarting.value = true
    addLog('🔄 开始重新仿真...', 'info')

    try {
        resetAllData()

        const response = await restartSimulation(taskId)
        addLog(`📤 已发送重新仿真请求，任务ID: ${taskId}`, 'info')
        addLog('⏳ 等待新的仿真数据...', 'info')
        ElMessage.success('仿真已重新启动')

        startTime = new Date()
        elapsedTime.value = '00:00:00'
        estimatedRemaining.value = ''

        isRestarting.value = false
    } catch (error: any) {
        isRestarting.value = false
        const errorMsg = error.response?.data?.detail || error.message || '重新仿真失败'
        ElMessage.error(errorMsg)
        addLog(`❌ 重新仿真失败: ${errorMsg}`, 'error')
        console.error('重新仿真错误:', error)
    }
}

// ===== 图表方法 =====
const initChart = () => {
    if (!chartRef.value) return

    chartInstance = echarts.init(chartRef.value)

    const coolingData = chartData.value.coolingLoad.filter(v => v > 0)
    const energyData = chartData.value.energyConsumption.filter(v => v > 0)

    const maxCooling = coolingData.length > 0 ? Math.max(...coolingData) : 100
    const loadMax = maxCooling * 1.2

    const maxEnergy = energyData.length > 0 ? Math.max(...energyData) : 1000
    const energyMax = Math.max(maxEnergy * 1.2, 100)

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function (params: any) {
                let result = `<strong>${params[0].name}</strong><br/>`
                params.forEach((p: any) => {
                    if (p.seriesName === '能耗') {
                        result += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)} kWh<br/>`
                    } else if (p.seriesName === '供冷量') {
                        result += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)} kWh<br/>`
                    } else {
                        result += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)} kW<br/>`
                    }
                })
                return result
            }
        },
        legend: {
            data: ['冷负荷', '供冷量', '能耗'],
            top: 0
        },
        grid: {
            left: '3%',
            right: '6%',
            bottom: '8%',
            top: '12%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: chartData.value.weeks,
            name: '周数',
            nameLocation: 'center',
            nameGap: 30,
            axisLabel: {
                rotate: 45,
                interval: Math.max(1, Math.floor(chartData.value.weeks.length / 20))
            }
        },
        yAxis: [
            {
                type: 'value',
                name: '负荷 / 供冷量 (kWh)',
                nameTextStyle: { align: 'right' },
                max: loadMax,
                min: 0,
                splitLine: {
                    lineStyle: { type: 'dashed' }
                }
            },
            {
                type: 'value',
                name: '能耗 (kWh)',
                nameTextStyle: { align: 'right' },
                max: energyMax,
                min: 0,
                splitLine: {
                    show: false
                }
            }
        ],
        series: [
            {
                name: '冷负荷',
                type: 'bar',
                stack: 'load',
                data: chartData.value.coolingLoad,
                itemStyle: {
                    color: '#409EFF',
                    borderRadius: [2, 2, 0, 0]
                },
                barMaxWidth: 30
            },
            {
                name: '供冷量',
                type: 'bar',
                stack: 'load',
                data: chartData.value.totalQStation,
                itemStyle: {
                    color: '#67C23A',
                    borderRadius: [2, 2, 0, 0]
                },
                barMaxWidth: 30
            },
            {
                name: '能耗',
                type: 'line',
                yAxisIndex: 1,
                data: chartData.value.energyConsumption,
                itemStyle: {
                    color: '#F56C6C'
                },
                lineStyle: {
                    width: 3,
                    shadowBlur: 4,
                    shadowColor: 'rgba(245, 108, 108, 0.3)'
                },
                smooth: true,
                symbol: 'diamond',
                symbolSize: 8,
                areaStyle: {
                    color: 'rgba(245, 108, 108, 0.15)'
                }
            }
        ]
    }

    chartInstance.setOption(option)
    window.addEventListener('resize', handleResize)
}

const updateChart = () => {
    if (!chartInstance) return

    const coolingData = chartData.value.coolingLoad.filter(v => v > 0)
    const energyData = chartData.value.energyConsumption.filter(v => v > 0)
    const qStationData = chartData.value.totalQStation.filter(v => v > 0)

    const maxCooling = coolingData.length > 0 ? Math.max(...coolingData) : 100
    const maxQStation = qStationData.length > 0 ? Math.max(...qStationData) : 100
    const loadMax = Math.max(maxCooling, maxQStation) * 1.2

    const maxEnergy = energyData.length > 0 ? Math.max(...energyData) : 1000
    const energyMax = Math.max(maxEnergy * 1.2, 100)

    const option = {
        xAxis: {
            data: chartData.value.weeks,
            axisLabel: {
                rotate: 45,
                interval: Math.max(1, Math.floor(chartData.value.weeks.length / 20))
            }
        },
        yAxis: [
            { max: loadMax, min: 0 },
            { max: energyMax, min: 0 }
        ],
        series: [
            { data: chartData.value.coolingLoad },
            { data: chartData.value.totalQStation },
            { data: chartData.value.energyConsumption, yAxisIndex: 1 }
        ]
    }

    chartInstance.setOption(option)
}

// ===== 雷达图（五维冷源站指标，0–100 归一化评分） =====
const radarMetrics = computed<RadarMetric[]>(() => {
    const result = resultData.value as any
    if (!result) return []
    return buildRadarMetrics(result.summary || {}, result.meta || {})
})

const radarPlotMetrics = computed<RadarMetric[]>(() =>
    radarMetrics.value.filter((item) => item.available),
)

// 旧结果缺指标的维度只留在明细表里，不参与绘制（不得按 0 分落在圆心）
const radarMissing = computed<string[]>(() =>
    radarMetrics.value.filter((item) => !item.available).map((item) => item.name),
)

const levelTagType = (level: MetricLevel): 'success' | 'primary' | 'warning' | 'danger' | 'info' => {
    if (level === '优秀') return 'success'
    if (level === '良好') return 'primary'
    if (level === '达标') return 'warning'
    if (level === '缺失') return 'info'
    return 'danger'
}

const initRadarChart = () => {
    if (!radarChartRef.value || !resultData.value) return

    // 只用有原始指标的维度绘制：缺指标的旧结果不按 0 分参与评价
    const metrics = radarPlotMetrics.value
    if (metrics.length < 3) return

    // 结果可能先后更新（先收到 completed 的汇总，再拉到完整七区块），
    // 同一 DOM 重复 init 会叠加实例并留下旧数据，必须先把旧实例销毁。
    if (radarChartInstance) {
        radarChartInstance.dispose()
        radarChartInstance = null
    }
    const existing = echarts.getInstanceByDom(radarChartRef.value)
    if (existing) {
        existing.dispose()
    }

    radarChartInstance = echarts.init(radarChartRef.value)

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: () => metrics
                .map((item) =>
                    `<strong>${item.name}</strong>：${item.display}（${item.score} 分 · ${item.level}）`
                    + `<br/><span style="color:#909399">基准：${item.benchmark}</span>`,
                )
                .join('<br/>')
        },
        radar: {
            // 五个维度统一为 0–100 分，位置越靠外代表该维度表现越好
            indicator: metrics.map((item) => ({
                name: `${item.name}\n${item.score} 分 · ${item.level}`,
                max: 100
            })),
            shape: 'circle',
            center: ['50%', '50%'],
            radius: '62%',
            splitNumber: 4,
            axisLabel: { show: false },
            axisTick: { show: false },
            axisName: {
                color: '#333',
                fontSize: 11,
                borderRadius: 4,
                padding: [2, 4]
            },
            splitArea: {
                areaStyle: {
                    color: ['rgba(64, 158, 255, 0.02)', 'rgba(64, 158, 255, 0.06)']
                }
            },
            splitLine: {
                lineStyle: {
                    color: 'rgba(64, 158, 255, 0.15)'
                }
            }
        },
        legend: {
            data: ['当前方案', '60 分达标参考线'],
            bottom: 0,
            itemWidth: 12,
            itemHeight: 8,
            textStyle: { fontSize: 11 }
        },
        series: [
            {
                type: 'radar',
                name: '60 分达标参考线',
                silent: true,
                tooltip: { show: false },
                data: [
                    {
                        value: metrics.map(() => 60),
                        name: '60 分达标参考线',
                        symbol: 'none',
                        lineStyle: {
                            type: 'dashed',
                            color: '#E6A23C',
                            width: 1
                        },
                        areaStyle: { color: 'transparent' },
                        itemStyle: { color: '#E6A23C' },
                        label: { show: false }
                    }
                ]
            },
            {
                type: 'radar',
                name: '当前方案',
                data: [
                    {
                        value: metrics.map((item) => item.score),
                        name: '当前方案',
                        areaStyle: {
                            color: 'rgba(64, 158, 255, 0.3)'
                        },
                        lineStyle: {
                            color: '#409EFF',
                            width: 2
                        },
                        itemStyle: {
                            color: '#409EFF'
                        },
                        label: { show: false }
                    }
                ]
            }
        ]
    }

    radarChartInstance.setOption(option)
    window.addEventListener('resize', handleResize)
}

const handleResize = () => {
    chartInstance?.resize()
    radarChartInstance?.resize()
}

// ===== 计时器 =====
const updateTimer = () => {
    if (!startTime) return
    const diff = Math.floor((Date.now() - startTime.getTime()) / 1000)
    const hours = String(Math.floor(diff / 3600)).padStart(2, '0')
    const minutes = String(Math.floor((diff % 3600) / 60)).padStart(2, '0')
    const seconds = String(diff % 60).padStart(2, '0')
    elapsedTime.value = `${hours}:${minutes}:${seconds}`

    if (progress.value > 0 && progress.value < 100) {
        const totalSeconds = (diff / progress.value) * 100
        const remaining = totalSeconds - diff
        if (remaining > 0 && remaining < 36000) {
            const rh = String(Math.floor(remaining / 3600)).padStart(2, '0')
            const rm = String(Math.floor((remaining % 3600) / 60)).padStart(2, '0')
            const rs = String(Math.floor(remaining % 60)).padStart(2, '0')
            estimatedRemaining.value = `${rh}:${rm}:${rs}`
        }
    }
}

// ===== 报告生成（单一标准模板）=====
const generating = ref(false)

const handleGenerateReport = async () => {
    if (generating.value) return
    generating.value = true
    addLog('📄 开始生成报告…', 'info')
    try {
        const res = await generateReport(taskId)
        addLog(`✅ 报告已生成：${res.reportId}`, 'success')
        ElMessage.success('报告已生成')
        router.push({ path: `/report/${res.reportId}`, query: { taskId } })
    } catch (e: any) {
        // 失败时只展示后端返回的原因，不提供任何下载链接
        const detail = e?.response?.data?.detail || e?.message || '报告生成失败'
        addLog(`❌ 报告生成失败：${detail}`, 'error')
        ElMessage.error(String(detail))
    } finally {
        generating.value = false
    }
}

// ===== 返回 =====
const goBack = () => {
    if (progress.value > 0 && progress.value < 100) {
        ElMessageBox.confirm('仿真尚未完成，确定要退出吗？', '提示', {
            confirmButtonText: '确定退出',
            cancelButtonText: '继续监控',
            type: 'warning'
        }).then(() => {
            cleanup()
            router.push('/')
        }).catch(() => { })
    } else {
        cleanup()
        router.push('/')
    }
}

const cleanup = () => {
    if (timer) {
        clearInterval(timer)
        timer = null
    }
    if (unregisterMessage) unregisterMessage()
    if (unregisterError) unregisterError()
    disconnect()
    if (chartInstance) {
        chartInstance.dispose()
        chartInstance = null
    }
    if (radarChartInstance) {
        radarChartInstance.dispose()
        radarChartInstance = null
    }
    window.removeEventListener('resize', handleResize)
}

// ===== 打开已完成任务时主动加载状态/结果（不一定有 WebSocket 推送）=====
const loadTaskState = async () => {
    try {
        const status = await getSimulationStatus(taskId)
        progress.value = status.progress ?? 0
        if (status.status === 'completed') {
            isCompleted.value = true
            progress.value = 100
            addLog('✅ 任务已完成，加载结果…', 'success')
            await loadFullResult()
        } else if (status.status === 'failed') {
            addLog(`❌ 仿真失败: ${status.message || '未知错误'}`, 'error')
        } else if (status.status === 'cancelled') {
            addLog('⏹️ 仿真已取消', 'warning')
        } else {
            addLog(`⏳ 任务状态: ${status.status}（${status.progress}%）`, 'info')
        }
    } catch (error) {
        // 任务不存在时不打断页面（例如旧链接）
        console.warn('加载任务状态失败:', error)
    }
}

// ===== 生命周期 =====
onMounted(() => {
    console.log('🔄 SimulationView mounted, taskId:', taskId)

    startTime = new Date()

    unregisterMessage = onMessage((message) => {
        console.log('📨 onMessage 回调触发:', message)
        handleWebSocketMessage(message)
    })

    unregisterError = onError((error) => {
        console.error('❌ WebSocket 错误:', error)
        addLog('❌ WebSocket 连接错误', 'error')
    })

    timer = setInterval(updateTimer, 1000)

    nextTick(() => {
        initChart()
    })

    addLog('📡 仿真监控已启动', 'info')
    addLog(`🔑 任务ID: ${taskId}`, 'info')
    addLog('⏳ 等待数据推送...', 'info')

    // 重新打开已完成的任务时，WebSocket 不会重放 completed 消息，必须主动拉一次
    void loadTaskState()

    setTimeout(() => {
        console.log('🔗 当前连接状态:', isConnected.value)
    }, 1000)
})

onUnmounted(() => {
    cleanup()
})

// ===== 监听结果数据变化 =====
watch(resultData, () => {
    if (resultData.value) {
        nextTick(() => {
            initRadarChart()
        })
    }
})
</script>

<style scoped>
.simulation-view {
    padding: 0;
}

.simulation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 20px;
}

.header-status {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}

.task-id {
    font-size: 12px;
    color: #909399;
    font-family: monospace;
}

.connection-status {
    font-size: 12px;
    color: #f56c6c;
}

.connection-status.connected {
    color: #67c23a;
}

.monitor-row {
    margin-top: 0;
}

.status-card {
    height: 100%;
}

.progress-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px 0;
}

.progress-text {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.percentage {
    font-size: 28px;
    font-weight: bold;
    color: #409EFF;
    line-height: 1.2;
}

.sub-text {
    font-size: 12px;
    color: #909399;
}

.progress-info {
    margin-top: 20px;
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 20px;
}

.info-item {
    display: flex;
    justify-content: space-between;
    font-size: 14px;
}

.info-item .label {
    color: #909399;
}

.info-item .value {
    color: #303133;
    font-weight: 500;
}

.metric-card {
    height: 100%;
}

.metric-content {
    display: flex;
    align-items: center;
    padding: 8px 0;
}

.metric-icon {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.metric-info {
    margin-left: 14px;
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
}

.metric-label {
    font-size: 13px;
    color: #909399;
}

.metric-value {
    font-size: 18px;
    font-weight: bold;
    color: #303133;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.chart-card {
    margin-top: 20px;
}

.chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
}

.chart-container {
    width: 100%;
    height: 380px;
}

.log-card {
    margin-top: 20px;
}

.log-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.log-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
}

.log-container {
    max-height: 200px;
    overflow-y: auto;
    background: #f5f7fa;
    padding: 10px 16px;
    border-radius: 4px;
}

.log-item {
    padding: 4px 0;
    font-size: 13px;
    font-family: 'Consolas', 'Courier New', monospace;
    border-bottom: 1px solid #e4e7ed;
    display: flex;
    gap: 16px;
}

.log-item:last-child {
    border-bottom: none;
}

.log-time {
    color: #909399;
    flex-shrink: 0;
}

.log-message {
    color: #303133;
    word-break: break-all;
}

.log-message.info {
    color: #409EFF;
}

.log-message.success {
    color: #67C23A;
}

.log-message.warning {
    color: #E6A23C;
}

.log-message.error {
    color: #F56C6C;
}

.log-empty {
    padding: 20px 0;
}

.result-card {
    margin-top: 20px;
}

.result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}

.result-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.result-item {
    text-align: center;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;
}

.result-label {
    font-size: 14px;
    color: #909399;
    margin-bottom: 8px;
}

.result-value {
    font-size: 22px;
    font-weight: bold;
    line-height: 1.2;
}

.result-unit {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
}

.radar-chart-container {
    width: 100%;
    height: 340px;
    margin-top: 16px;
}

.radar-benchmark-table {
    margin-top: 16px;
}

.radar-benchmark-note {
    margin-top: 10px;
    color: #909399;
    font-size: 12px;
    line-height: 1.6;
}

.radar-missing-note {
    margin-top: 10px;
}

@media (max-width: 768px) {
    .simulation-header {
        flex-direction: column;
        align-items: flex-start;
    }

    .header-status {
        flex-wrap: wrap;
    }

    .progress-info {
        grid-template-columns: 1fr;
    }

    .chart-container {
        height: 280px;
    }

    .result-header {
        flex-direction: column;
        align-items: flex-start;
    }

    .result-item {
        margin-bottom: 12px;
    }
}
</style>