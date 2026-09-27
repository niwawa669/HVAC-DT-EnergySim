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
                        <el-button type="primary" size="small" @click="generateReport('standard')">
                            生成标准报告
                        </el-button>
                        <el-button size="small" @click="generateReport('simplified')">
                            生成简化报告
                        </el-button>
                        <el-button type="warning" size="small" @click="generateReport('expert')">
                            生成专家报告
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
import { restartSimulation } from '@/api/simulation'

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

    const summary = resultData.value.summary
    const weeklyData = resultData.value.weeklyData || []

    // ===== 计算尖峰逐时冷负荷 =====
    let peakCoolingLoad = 0
    if (weeklyData && weeklyData.length > 0) {
        const peakLoads = weeklyData.map((w: any) => w.peakCoolingLoad || 0)
        peakCoolingLoad = peakLoads.length > 0 ? Math.max(...peakLoads) : 0
    } else {
        peakCoolingLoad = summary.peakCoolingLoad || 0
    }

    // ===== 计算冷源站综合平均能效 EERa =====
    // EERa = 冷源站总供冷量 / 冷源站总耗电量
    const totalQStation = summary.totalQStation || summary.totalCoolingLoad || 0
    const totalEnergy = summary.totalEnergy || 0
    const eera = totalEnergy > 0 ? totalQStation / totalEnergy : 0

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
            resultData.value = {
                summary: message.summary,
                weeklyData: chartData.value
            }
            addLog('✅ 仿真计算完成！', 'success')
            ElMessage.success('仿真计算完成！')

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

// ===== 雷达图（五维冷源站指标） =====
const initRadarChart = () => {
    if (!radarChartRef.value || !resultData.value) return

    radarChartInstance = echarts.init(radarChartRef.value)

    const summary = resultData.value.summary
    const weeklyData = resultData.value.weeklyData || []

    // ===== 五维参数计算 =====

    // 1. 冷源站综合平均能效 EERa
    const totalQStation = summary.totalQStation || summary.totalCoolingLoad || 0
    const totalEnergy = summary.totalEnergy || 0
    const eera = totalEnergy > 0 ? totalQStation / totalEnergy : 0

    // 2. 全年平均负荷率
    const designLoad = 500
    let avgCoolingLoad = 0

    if (weeklyData && weeklyData.length > 0) {
        const totalLoad = weeklyData.reduce((a: number, b: any) => a + (b.coolingLoad || 0), 0)
        const totalHours = weeklyData.length * 168
        avgCoolingLoad = totalHours > 0 ? totalLoad / totalHours : 0
    }

    const avgLoadRate = designLoad > 0 ? Math.min((avgCoolingLoad / designLoad) * 100, 100) : 0

    // 3. 单位面积供冷量 (kWh/m²)
    const area = summary.area || 2931
    const unitQStation = area > 0 ? totalQStation / area : 0

    // 4. 单位面积耗电量 (kWh/m²)
    const unitEnergy = area > 0 ? totalEnergy / area : 0

    // 5. 单位面积碳排放量 (kg CO₂/m²)
    const carbonEmission = summary.carbonEmission || 0
    const unitCarbon = area > 0 ? carbonEmission / area : 0

    // ===== 各维度最大值 =====
    const maxEera = Math.max(eera * 1.5, 5)
    const maxLoadRate = 100
    const maxUnitQStation = Math.max(unitQStation * 1.5, 50)
    const maxUnitEnergy = Math.max(unitEnergy * 1.5, 20)
    const maxUnitCarbon = Math.max(unitCarbon * 1.5, 10)

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: function (params: any) {
                let result = `<strong>${params.name}</strong><br/>`
                const names = ['综合平均能效 EERa', '全年平均负荷率', '单位面积供冷量', '单位面积耗电量', '单位面积碳排放']
                const units = ['', ' %', ' kWh/m²', ' kWh/m²', ' kg CO₂/m²']
                const values = [eera, avgLoadRate, unitQStation, unitEnergy, unitCarbon]
                params.value.forEach((val: number, index: number) => {
                    const displayVal = index === 0 ? values[index].toFixed(2) : values[index].toFixed(1)
                    result += `${names[index]}: ${displayVal}${units[index]}<br/>`
                })
                return result
            }
        },
        radar: {
            indicator: [
                { name: '综合平均能效 EERa', max: maxEera, color: '#9B59B6' },
                { name: '全年平均负荷率', max: maxLoadRate, color: '#67C23A' },
                { name: '单位面积供冷量', max: maxUnitQStation, color: '#409EFF' },
                { name: '单位面积耗电量', max: maxUnitEnergy, color: '#F56C6C' },
                { name: '单位面积碳排放', max: maxUnitCarbon, color: '#909399' }
            ],
            shape: 'circle',
            center: ['50%', '50%'],
            radius: '65%',
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
        series: [
            {
                type: 'radar',
                data: [
                    {
                        value: [eera, avgLoadRate, unitQStation, unitEnergy, unitCarbon],
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
                        label: {
                            show: true,
                            formatter: (params: any) => {
                                const values = [eera, avgLoadRate, unitQStation, unitEnergy, unitCarbon]
                                const val = values[params.dataIndex] || 0
                                return val.toFixed(1)
                            },
                            fontSize: 10,
                            color: '#333'
                        }
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

// ===== 报告生成 =====
const generateReport = (type: string) => {
    const names = { standard: '标准报告', simplified: '简化报告', expert: '专家报告' }
    ElMessage.success(`${names[type]}生成中...`)
    setTimeout(() => {
        ElMessage.success(`${names[type]}生成完成！`)
    }, 1500)
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
    height: 300px;
    margin-top: 16px;
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