<template>
    <div class="project-new">
        <el-card shadow="hover">
            <template #header>
                <div class="card-header">
                    <span>新建仿真项目</span>
                    <el-button size="small" @click="$router.push('/')">返回</el-button>
                </div>
            </template>

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

                    <el-form-item label="数据文件" required>
                        <DataUploader @data-confirmed="handleDataConfirmed" />
                    </el-form-item>

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

                    <el-form-item>
                        <el-button type="primary" @click="nextStep" :disabled="!canProceed">
                            下一步
                            <el-icon>
                                <ArrowRight />
                            </el-icon>
                        </el-button>
                    </el-form-item>
                </el-form>
            </div>

            <!-- Step 2: 参数配置 -->
            <div v-show="activeStep === 1" class="step-content">
                <!-- ... 参数配置内容不变 ... -->
            </div>

            <!-- Step 3: 启动仿真 -->
            <div v-show="activeStep === 2" class="step-content">
                <!-- ... 确认内容不变 ... -->
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
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, ArrowLeft, VideoPlay } from '@element-plus/icons-vue'
import DataUploader from '@/components/data/DataUploader.vue'
// ===== 修复：重命名导入的 API 函数 =====
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
    return !!projectForm.name &&
        !!projectForm.buildingType &&
        dataConfirmed.value === true &&
        parsedData.value !== null &&
        parsedData.value?.data?.length > 0
})

const canStartSimulation = computed(() => {
    return !simulating.value && parsedData.value !== null
})

// ===== 监听 =====
watch(dataConfirmed, (newVal) => {
    console.log('dataConfirmed changed:', newVal)
})

// ===== 数据确认处理 =====
const handleDataConfirmed = (data: any) => {
    console.log('Data confirmed callback received:', data)
    parsedData.value = data
    dataConfirmed.value = true
    ElMessage.success(`数据确认完成，共 ${data.data.length} 行，${data.headers.length} 列`)
}

// ===== 步骤导航 =====
const nextStep = () => {
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

// ===== 启动仿真（使用重命名后的 API） =====
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
        // 使用重命名后的 API 函数 startSimulationAPI
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

/* 上传组件样式 */
:deep(.el-upload-dragger) {
    width: 100%;
    padding: 30px 20px;
}

:deep(.el-upload-dragger .el-icon--upload) {
    font-size: 48px;
    color: #409EFF;
}

/* 表单样式 */
:deep(.el-form-item) {
    margin-bottom: 22px;
}

:deep(.el-divider) {
    margin: 24px 0 20px 0;
}

:deep(.el-descriptions) {
    margin-top: 8px;
}

/* 响应式 */
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