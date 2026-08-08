<template>
    <div class="simulation-view">
        <el-page-header @back="goBack" content="仿真运行监控" />

        <el-row :gutter="20" style="margin-top: 20px;">
            <el-col :span="8">
                <el-card>
                    <div style="text-align: center; padding: 20px;">
                        <el-progress type="circle" :percentage="progress" :width="150" />
                        <p style="margin-top: 10px;">进度: {{ progress }}%</p>
                        <p>当前周数: {{ currentWeek }}/52</p>
                    </div>
                </el-card>
            </el-col>
            <el-col :span="16">
                <el-row :gutter="20">
                    <!-- 修复：使用 v-for 循环渲染指标卡片 -->
                    <el-col v-for="item in metrics" :key="item.label" :span="12">
                        <el-card>
                            <div style="text-align: center;">
                                <div style="color: #909399; font-size: 14px;">{{ item.label }}</div>
                                <div style="font-size: 22px; font-weight: bold; margin-top: 5px;">{{ item.value }}</div>
                            </div>
                        </el-card>
                    </el-col>
                </el-row>
            </el-col>
        </el-row>

        <el-card style="margin-top: 20px;">
            <template #header>
                <span>运行日志</span>
            </template>
            <div style="max-height: 200px; overflow-y: auto; background: #f5f7fa; padding: 10px; border-radius: 4px;">
                <!-- 修复：使用 v-for 渲染日志 -->
                <div v-for="log in logs" :key="log.time + log.message"
                    style="padding: 4px 0; font-size: 13px; border-bottom: 1px solid #e4e7ed;">
                    <span style="color: #909399; margin-right: 15px;">{{ log.time }}</span>
                    <span>{{ log.message }}</span>
                </div>
                <div v-if="logs.length === 0" style="text-align: center; color: #909399; padding: 20px;">
                    暂无日志
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()

// 响应式数据
const progress = ref(0)
const currentWeek = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

// 指标数据 - 使用数组，不再使用 v-for 的循环依赖
const metrics = ref([
    { label: '本周能耗', value: '0 kWh' },
    { label: '平均COP', value: '0.00' },
    { label: '室外温度', value: '0 °C' },
    { label: '已推送周数', value: '0/52' }
])

// 日志数据
const logs = ref < { time: string; message: string }[] > ([])

// 添加日志
const addLog = (message: string) => {
    const time = new Date().toLocaleTimeString()
    logs.value.unshift({ time, message })
    // 最多保留50条
    if (logs.value.length > 50) {
        logs.value = logs.value.slice(0, 50)
    }
}

// 模拟仿真进度
const startSimulation = () => {
    timer = setInterval(() => {
        currentWeek.value++

        if (currentWeek.value > 52) {
            if (timer) {
                clearInterval(timer)
                timer = null
            }
            progress.value = 100
            addLog('仿真完成！')
            ElMessage.success('仿真完成！')
            return
        }

        // 更新进度
        progress.value = Math.round((currentWeek.value / 52) * 100)

        // 生成模拟数据
        const energy = (2000 + Math.random() * 1500).toFixed(0)
        const cop = (3.0 + Math.random() * 0.5).toFixed(2)
        const temp = (15 + Math.random() * 10).toFixed(1)

        // 更新指标
        metrics.value = [
            { label: '本周能耗', value: energy + ' kWh' },
            { label: '平均COP', value: cop },
            { label: '室外温度', value: temp + ' °C' },
            { label: '已推送周数', value: currentWeek.value + '/52' }
        ]

        addLog(`第${currentWeek.value}周数据已接收`)
    }, 1000)
}

// 返回上一页
const goBack = () => {
    if (progress.value > 0 && progress.value < 100) {
        ElMessage.warning('仿真尚未完成')
    } else {
        router.push('/')
    }
}

// 生命周期
onMounted(() => {
    startSimulation()
})

onBeforeUnmount(() => {
    if (timer) {
        clearInterval(timer)
        timer = null
    }
})
</script>

<style scoped>
.simulation-view {
    padding: 0;
}
</style>