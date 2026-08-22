<template>
    <div class="project-new">
        <el-card shadow="hover">
            <template #header>
                <div class="card-header">
                    <span>新建仿真项目</span>
                    <el-button size="small" @click="$router.push('/')">返回</el-button>
                </div>
            </template>

            <!-- 步骤条 -->
            <el-steps :active="activeStep" finish-status="success" style="margin-bottom: 30px;">
                <el-step title="上传数据" description="上传负荷和气象数据" />
                <el-step title="参数配置" description="设置系统参数" />
                <el-step title="启动仿真" description="确认并开始仿真" />
            </el-steps>

            <!-- Step 1: 上传数据 -->
            <div v-show="activeStep === 0" class="step-content">
                <el-form :model="projectForm" label-width="120px">
                    <el-form-item label="项目名称" required>
                        <el-input v-model="projectForm.name" placeholder="请输入项目名称" maxlength="50" show-word-limit />
                    </el-form-item>

                    <el-form-item label="建筑类型" required>
                        <el-select v-model="projectForm.buildingType" placeholder="请选择建筑类型" style="width: 100%;">
                            <el-option label="办公建筑" value="office" />
                            <el-option label="商业建筑" value="commercial" />
                            <el-option label="住宅建筑" value="residential" />
                            <el-option label="医院建筑" value="hospital" />
                            <el-option label="工业建筑" value="industrial" />
                        </el-select>
                    </el-form-item>

                    <el-form-item label="建筑面积 (m²)">
                        <el-input-number v-model="projectForm.area" :min="100" :max="100000" :step="100"
                            controls-position="right" style="width: 100%;" />
                    </el-form-item>

                    <!-- 数据预处理组件 -->
                    <el-form-item label="数据文件" required>
                        <DataUploader @data-confirmed="handleDataConfirmed" />
                    </el-form-item>

                    <!-- 数据确认状态 -->
                    <el-form-item v-if="dataConfirmed">
                        <el-alert title="✅ 数据已确认" type="success" :closable="false" show-icon>
                            <template #default>
                                <div style="font-size: 13px; margin-top: 4px;">
                                    共 {{ parsedData?.data?.length || 0 }} 行数据，
                                    {{ parsedData?.headers?.length || 0 }} 列
                                    <span v-if="parsedData?.outliers && Object.keys(parsedData.outliers).length > 0">
                                        ，⚠️ {{ Object.keys(parsedData.outliers).length }} 列存在异常值
                                    </span>
                                </div>
                            </template>
                        </el-alert>
                    </el-form-item>

                    <!-- 调试信息 -->
                    <el-form-item v-if="!dataConfirmed">
                        <el-alert title="请确认数据" type="info" :closable="false" show-icon
                            description='上传数据文件后，点击数据预览区域下方的"确认数据"按钮继续' />
                    </el-form-item>

                    <el-form-item>
                        <el-button type="primary" @click="nextStep" :disabled="!canProceed">
                            下一步
                            <el-icon>
                                <ArrowRight />
                            </el-icon>
                        </el-button>
                        <!-- 调试信息 -->
                        <span style="margin-left: 10px; font-size: 12px; color: #909399;">
                            条件: 名称{{ !!projectForm.name ? '✅' : '❌' }} |
                            建筑{{ !!projectForm.buildingType ? '✅' : '❌' }} |
                            确认{{ dataConfirmed ? '✅' : '❌' }} |
                            数据行数: {{ parsedData?.data?.length || 0 }}
                        </span>
                    </el-form-item>
                </el-form>
            </div>

            <!-- Step 2: 参数配置 -->
            <div v-show="activeStep === 1" class="step-content">
                <el-form :model="configForm" label-width="180px">
                    <el-divider content-position="left">空调系统</el-divider>

                    <el-form-item label="系统类型" required>
                        <el-select v-model="configForm.systemType" placeholder="请选择系统类型" style="width: 100%;">
                            <el-option label="变风量系统 (VAV)" value="vav" />
                            <el-option label="定风量系统 (CAV)" value="cav" />
                            <el-option label="风机盘管系统 (FCU)" value="fcu" />
                            <el-option label="多联机系统 (VRV)" value="vrv" />
                        </el-select>
                    </el-form-item>

                    <el-form-item label="运行策略" required>
                        <el-radio-group v-model="configForm.operationSchedule">
                            <el-radio value="continuous">连续运行 (24/7)</el-radio>
                            <el-radio value="intermittent">间歇运行 (8:00-18:00)</el-radio>
                            <el-radio value="custom">自定义时间表</el-radio>
                        </el-radio-group>
                    </el-form-item>

                    <el-form-item v-if="configForm.operationSchedule === 'custom'" label="运行时间">
                        <el-time-picker v-model="configForm.startTime" placeholder="开始时间" format="HH:mm"
                            value-format="HH:mm" />
                        <el-time-picker v-model="configForm.endTime" placeholder="结束时间" format="HH:mm"
                            value-format="HH:mm" style="margin-left: 10px;" />
                    </el-form-item>

                    <el-divider content-position="left">室内参数</el-divider>

                    <el-form-item label="夏季设定温度 (°C)">
                        <el-input-number v-model="configForm.coolingSetpoint" :min="20" :max="28" :step="0.5"
                            controls-position="right" />
                        <span style="margin-left: 10px; color: #909399;">推荐: 26°C</span>
                    </el-form-item>

                    <el-form-item label="冬季设定温度 (°C)">
                        <el-input-number v-model="configForm.heatingSetpoint" :min="16" :max="24" :step="0.5"
                            controls-position="right" />
                        <span style="margin-left: 10px; color: #909399;">推荐: 20°C</span>
                    </el-form-item>

                    <el-divider content-position="left">建筑参数</el-divider>

                    <el-form-item label="人员密度 (人/m²)">
                        <el-input-number v-model="configForm.occupancyDensity" :min="0.05" :max="0.5" :step="0.05"
                            controls-position="right" />
                        <span style="margin-left: 10px; color: #909399;">办公: 0.1</span>
                    </el-form-item>

                    <el-form-item label="照明功率密度 (W/m²)">
                        <el-input-number v-model="configForm.lightingPowerDensity" :min="5" :max="20"
                            controls-position="right" />
                        <span style="margin-left: 10px; color: #909399;">办公: 10</span>
                    </el-form-item>

                    <el-form-item label="设备功率密度 (W/m²)">
                        <el-input-number v-model="configForm.equipmentPowerDensity" :min="5" :max="50"
                            controls-position="right" />
                        <span style="margin-left: 10px; color: #909399;">办公: 15</span>
                    </el-form-item>

                    <el-form-item>
                        <el-button @click="prevStep">
                            <el-icon>
                                <ArrowLeft />
                            </el-icon> 上一步
                        </el-button>
                        <el-button type="primary" @click="nextStep">
                            下一步
                            <el-icon>
                                <ArrowRight />
                            </el-icon>
                        </el-button>
                    </el-form-item>
                </el-form>
            </div>

            <!-- Step 3: 启动仿真 -->
            <div v-show="activeStep === 2" class="step-content">
                <el-alert title="配置确认" type="success" :closable="false" style="margin-bottom: 20px;">
                    <template #default>
                        <div class="config-summary">
                            <el-descriptions :column="2" border>
                                <el-descriptions-item label="项目名称">{{ projectForm.name || '未命名'
                                    }}</el-descriptions-item>
                                <el-descriptions-item label="建筑类型">{{ getBuildingTypeLabel(projectForm.buildingType)
                                    }}</el-descriptions-item>
                                <el-descriptions-item label="建筑面积">{{ projectForm.area || 0 }} m²</el-descriptions-item>
                                <el-descriptions-item label="系统类型">{{ getSystemTypeLabel(configForm.systemType)
                                    }}</el-descriptions-item>
                                <el-descriptions-item label="运行策略">{{ getScheduleLabel(configForm.operationSchedule)
                                    }}</el-descriptions-item>
                                <el-descriptions-item label="夏季设定温度">{{ configForm.coolingSetpoint
                                    }}°C</el-descriptions-item>
                                <el-descriptions-item label="冬季设定温度">{{ configForm.heatingSetpoint
                                    }}°C</el-descriptions-item>
                                <el-descriptions-item label="人员密度">{{ configForm.occupancyDensity }}
                                    人/m²</el-descriptions-item>
                                <el-descriptions-item label="照明功率密度">{{ configForm.lightingPowerDensity }}
                                    W/m²</el-descriptions-item>
                                <el-descriptions-item label="设备功率密度">{{ configForm.equipmentPowerDensity }}
                                    W/m²</el-descriptions-item>
                                <el-descriptions-item label="数据行数">{{ parsedData?.data?.length || 0
                                    }}</el-descriptions-item>
                                <el-descriptions-item label="数据列数">{{ parsedData?.headers?.length || 0
                                    }}</el-descriptions-item>
                            </el-descriptions>
                        </div>
                    </template>
                </el-alert>

                <div class="action-buttons">
                    <el-button @click="prevStep">
                        <el-icon>
                            <ArrowLeft />
                        </el-icon> 上一步
                    </el-button>
                    <el-button type="primary" size="large" @click="startSimulation" :loading="simulating"
                        :disabled="!canStartSimulation">
                        <el-icon>
                            <VideoPlay />
                        </el-icon>
                        {{ simulating ? '仿真启动中...' : '启动仿真' }}
                    </el-button>
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, ArrowLeft, VideoPlay } from '@element-plus/icons-vue'
import DataUploader from '@/components/data/DataUploader.vue'
import { startSimulation as startSimulationAPI } from '@/api/simulation'

const router = useRouter()

// ===== 状态 =====
const activeStep = ref(0)
const simulating = ref(false)
const parsedData = ref<any>(null)
const dataConfirmed = ref(false)

// ===== 项目表单 =====
const projectForm = reactive({
    name: '',
    buildingType: '',
    area: 10000
})

// ===== 配置表单 =====
const configForm = reactive({
    systemType: 'vav',
    operationSchedule: 'continuous',
    startTime: '08:00',
    endTime: '18:00',
    coolingSetpoint: 26,
    heatingSetpoint: 20,
    occupancyDensity: 0.1,
    lightingPowerDensity: 10,
    equipmentPowerDensity: 15
})

// ===== 计算属性 =====
const canProceed = computed(() => {
    const result = !!projectForm.name &&
        !!projectForm.buildingType &&
        dataConfirmed.value === true &&
        parsedData.value !== null &&
        parsedData.value?.data?.length > 0
    console.log('canProceed 计算:', {
        name: !!projectForm.name,
        building: !!projectForm.buildingType,
        confirmed: dataConfirmed.value,
        hasData: parsedData.value !== null,
        dataLength: parsedData.value?.data?.length || 0,
        result
    })
    return result
})

const canStartSimulation = computed(() => {
    return !simulating.value && parsedData.value !== null
})

// ===== 监听数据确认状态 =====
watch(dataConfirmed, (newVal) => {
    console.log('dataConfirmed 变化:', newVal)
    console.log('parsedData:', parsedData.value)
})

// ===== 数据确认处理 =====
const handleDataConfirmed = (data: any) => {
    console.log('📦 DataUploader 确认数据回调:', data)

    // 确保数据有效
    if (!data || !data.data || data.data.length === 0) {
        ElMessage.error('数据无效，请重新上传')
        return
    }

    // 保存数据
    parsedData.value = data
    dataConfirmed.value = true

    ElMessage.success(`数据确认完成，共 ${data.data.length} 行，${data.headers.length} 列`)

    // 强制更新视图
    nextTick(() => {
        console.log('视图更新后 canProceed:', canProceed.value)
    })
}

// ===== 下一步 =====
const nextStep = () => {
    console.log('点击下一步，canProceed:', canProceed.value)

    if (activeStep.value === 0) {
        if (!projectForm.name) {
            ElMessage.warning('请输入项目名称')
            return
        }
        if (!projectForm.buildingType) {
            ElMessage.warning('请选择建筑类型')
            return
        }
        if (!dataConfirmed.value) {
            ElMessage.warning('请先上传并确认数据文件')
            return
        }
        if (!parsedData.value || parsedData.value.data.length === 0) {
            ElMessage.warning('数据为空，请重新上传')
            return
        }
    }
    activeStep.value++
}

const prevStep = () => {
    activeStep.value--
}

// ===== 启动仿真 =====
const startSimulation = async () => {
    if (!parsedData.value) {
        ElMessage.warning('请先上传数据')
        return
    }

    try {
        await ElMessageBox.confirm(
            '确认启动仿真计算？这可能需要一些时间。',
            '确认启动',
            {
                confirmButtonText: '确认启动',
                cancelButtonText: '取消',
                type: 'info'
            }
        )
    } catch {
        return
    }

    simulating.value = true

    try {
        const response = await startSimulationAPI({
            projectName: projectForm.name,
            buildingType: projectForm.buildingType,
            area: projectForm.area,
            config: {
                systemType: configForm.systemType,
                operationSchedule: configForm.operationSchedule,
                startTime: configForm.startTime,
                endTime: configForm.endTime,
                coolingSetpoint: configForm.coolingSetpoint,
                heatingSetpoint: configForm.heatingSetpoint,
                occupancyDensity: configForm.occupancyDensity,
                lightingPowerDensity: configForm.lightingPowerDensity,
                equipmentPowerDensity: configForm.equipmentPowerDensity
            },
            data: {
                headers: parsedData.value.headers,
                rows: parsedData.value.data
            }
        })

        simulating.value = false
        ElMessage.success(`仿真任务已启动！任务ID: ${response.taskId}`)
        router.push(`/simulation/${response.taskId}`)

    } catch (error: any) {
        simulating.value = false
        const errorMsg = error.response?.data?.detail || error.message || '启动仿真失败，请检查后端服务'
        ElMessage.error(errorMsg)
        console.error('启动仿真错误:', error)
    }
}

// ===== 辅助方法 =====
const getBuildingTypeLabel = (type: string) => {
    const map: Record<string, string> = {
        office: '办公建筑',
        commercial: '商业建筑',
        residential: '住宅建筑',
        hospital: '医院建筑',
        industrial: '工业建筑'
    }
    return map[type] || type
}

const getSystemTypeLabel = (type: string) => {
    const map: Record<string, string> = {
        vav: 'VAV 变风量',
        cav: 'CAV 定风量',
        fcu: 'FCU 风机盘管',
        vrv: 'VRV 多联机'
    }
    return map[type] || type
}

const getScheduleLabel = (type: string) => {
    const map: Record<string, string> = {
        continuous: '连续运行',
        intermittent: '间歇运行',
        custom: '自定义时间表'
    }
    return map[type] || type
}
</script>

<style scoped>
.project-new {
    padding: 0;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.card-header span {
    font-size: 16px;
    font-weight: 600;
}

.step-content {
    padding: 20px 0;
    min-height: 420px;
}

.config-summary {
    margin-top: 10px;
}

.action-buttons {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 30px;
}

:deep(.el-upload-dragger) {
    width: 100%;
    padding: 30px 20px;
}

:deep(.el-upload-dragger .el-icon--upload) {
    font-size: 48px;
    color: #409EFF;
}

:deep(.el-form-item) {
    margin-bottom: 22px;
}

:deep(.el-divider) {
    margin: 24px 0 20px 0;
}

:deep(.el-descriptions) {
    margin-top: 8px;
}

@media (max-width: 768px) {
    .step-content {
        min-height: 300px;
    }

    .action-buttons {
        flex-direction: column;
        align-items: center;
    }

    :deep(.el-descriptions .el-descriptions__body .el-descriptions__table .el-descriptions__cell) {
        display: block;
        width: 100%;
    }
}
</style>