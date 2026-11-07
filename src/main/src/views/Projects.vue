<template>
    <div class="projects">
        <el-card>
            <template #header>
                <div class="card-header">
                    <span>项目列表</span>
                    <div>
                        <el-button size="small" @click="loadProjects" :loading="loading">刷新</el-button>
                        <el-button type="primary" size="small" @click="goToNewProject">新建项目</el-button>
                    </div>
                </div>
            </template>

            <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false"
                style="margin-bottom: 16px;" />

            <el-input v-model="searchKeyword" placeholder="搜索项目名称或建筑类型..." style="width: 280px; margin-bottom: 16px;"
                clearable />

            <el-table :data="filteredProjects" v-loading="loading" style="width: 100%"
                empty-text="暂无项目：新建项目并发起一次仿真后，项目会自动出现在这里">
                <el-table-column prop="name" label="项目名称" min-width="200" />
                <el-table-column label="建筑类型" width="120">
                    <template #default="{ row }">{{ buildingTypeLabel(row.buildingType) }}</template>
                </el-table-column>
                <el-table-column label="空调面积" width="140">
                    <template #default="{ row }">{{ formatArea(row.area) }}</template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                    <template #default="{ row }">
                        <el-tag :type="projectStatusTagType(row.status)" size="small">
                            {{ projectStatusLabel(row.status) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="最近仿真" width="140">
                    <template #default="{ row }">
                        <span v-if="row.latestTask">
                            {{ projectStatusLabel(row.latestTask.status) }} {{ row.latestTask.progress }}%
                        </span>
                        <span v-else>—</span>
                    </template>
                </el-table-column>
                <el-table-column label="总耗电量" width="150">
                    <template #default="{ row }">
                        <span v-if="row.latestSummary?.totalEnergy !== null && row.latestSummary?.totalEnergy !== undefined">
                            {{ formatEnergyValue(row.latestSummary.totalEnergy) }}
                        </span>
                        <span v-else>—</span>
                    </template>
                </el-table-column>
                <el-table-column label="更新时间" width="170">
                    <template #default="{ row }">{{ formatDateTime(row.updatedAt || row.createdAt) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="240" fixed="right">
                    <template #default="{ row }">
                        <el-button size="small" @click="viewProject(row)">查看</el-button>
                        <el-button v-if="row.latestTask" size="small" type="primary" @click="openSimulation(row)">
                            仿真
                        </el-button>
                        <el-button size="small" type="danger" @click="removeProject(row)">删除</el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>

        <!-- 项目详情 -->
        <el-dialog v-model="detailVisible" title="项目详情" width="720px" destroy-on-close>
            <div v-loading="detailLoading">
                <template v-if="detail">
                    <el-descriptions :column="2" border>
                        <el-descriptions-item label="项目名称">{{ detail.name }}</el-descriptions-item>
                        <el-descriptions-item label="建筑类型">{{ buildingTypeLabel(detail.buildingType) }}</el-descriptions-item>
                        <el-descriptions-item label="空调面积">{{ formatArea(detail.area) }}</el-descriptions-item>
                        <el-descriptions-item label="项目状态">
                            <el-tag :type="projectStatusTagType(detail.status)" size="small">
                                {{ projectStatusLabel(detail.status) }}
                            </el-tag>
                        </el-descriptions-item>
                        <el-descriptions-item label="创建时间">{{ formatDateTime(detail.createdAt) }}</el-descriptions-item>
                        <el-descriptions-item label="更新时间">{{ formatDateTime(detail.updatedAt) }}</el-descriptions-item>
                    </el-descriptions>

                    <el-divider content-position="left">最近一次仿真</el-divider>
                    <el-descriptions v-if="detail.latestTask" :column="2" border>
                        <el-descriptions-item label="任务 ID">
                            <span class="mono">{{ detail.latestTask.taskId }}</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="任务状态">
                            <el-tag :type="projectStatusTagType(detail.latestTask.status)" size="small">
                                {{ projectStatusLabel(detail.latestTask.status) }}
                            </el-tag>
                        </el-descriptions-item>
                        <el-descriptions-item label="进度">{{ detail.latestTask.progress }}%</el-descriptions-item>
                        <el-descriptions-item label="最后更新">{{ formatDateTime(detail.latestTask.updatedAt) }}</el-descriptions-item>
                    </el-descriptions>
                    <el-empty v-else description="该项目还没有仿真任务" :image-size="60" />

                    <el-divider content-position="left">结果摘要</el-divider>
                    <el-descriptions v-if="detail.latestSummary" :column="2" border>
                        <el-descriptions-item label="总耗电量">
                            {{ formatEnergyValue(detail.latestSummary.totalEnergy) }}
                        </el-descriptions-item>
                        <el-descriptions-item label="单位面积耗电量">
                            {{ formatMetric(detail.latestSummary.eui, 'kWh/m²') }}
                        </el-descriptions-item>
                        <el-descriptions-item label="碳排放量">
                            {{ formatMetric(detail.latestSummary.carbonEmission, 'kgCO₂') }}
                        </el-descriptions-item>
                        <el-descriptions-item label="峰值冷负荷">
                            {{ formatMetric(detail.latestSummary.peakLoad, 'kW') }}
                        </el-descriptions-item>
                        <el-descriptions-item label="建筑总冷负荷">
                            {{ formatMetric(detail.latestSummary.totalCoolingLoad, 'kWh') }}
                        </el-descriptions-item>
                        <el-descriptions-item label="结果生成时间">
                            {{ formatDateTime(detail.latestSummary.createdAt) }}
                        </el-descriptions-item>
                    </el-descriptions>
                    <el-empty v-else description="暂无结果：仿真完成后这里会显示汇总指标" :image-size="60" />
                </template>
            </div>

            <template #footer>
                <el-button @click="detailVisible = false">关闭</el-button>
                <el-button v-if="detail?.latestTask" type="primary" @click="openSimulation(detail)">
                    查看仿真
                </el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { deleteProject, getProject, getProjects, type Project } from '@/api/projects'
import {
    buildingTypeLabel,
    formatArea,
    formatDateTime,
    formatNumberFixed,
    projectStatusLabel,
    projectStatusTagType,
} from '@/utils/projectDisplay'

const route = useRoute()
const router = useRouter()

const projects = ref<Project[]>([])
const loading = ref(false)
const loadError = ref('')
const searchKeyword = ref('')

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<Project | null>(null)

const filteredProjects = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) return projects.value
    return projects.value.filter((item) =>
        item.name.toLowerCase().includes(keyword) ||
        buildingTypeLabel(item.buildingType).toLowerCase().includes(keyword),
    )
})

const formatEnergyValue = (value?: number | null) =>
    value === null || value === undefined ? '—' : `${formatNumberFixed(value, 0)} kWh`

const formatMetric = (value: number | null | undefined, unit: string) =>
    value === null || value === undefined ? '—' : `${formatNumberFixed(value, 2)} ${unit}`

const loadProjects = async () => {
    loading.value = true
    loadError.value = ''
    try {
        projects.value = await getProjects()
    } catch (error: any) {
        loadError.value =
            error?.response?.data?.detail || '项目列表加载失败，请确认后端服务已启动'
        console.error('加载项目列表失败:', error)
    } finally {
        loading.value = false
    }
}

const openDetail = async (row: Project) => {
    detail.value = row
    detailVisible.value = true
    detailLoading.value = true
    try {
        detail.value = await getProject(row.id)
    } catch (error: any) {
        ElMessage.error(error?.response?.data?.detail || '项目详情加载失败')
    } finally {
        detailLoading.value = false
    }
}

const viewProject = (row: Project) => {
    void openDetail(row)
}

const openSimulation = (row: Project) => {
    if (row.latestTask?.taskId) {
        router.push(`/simulation/${row.latestTask.taskId}`)
    }
}

const removeProject = (row: Project) => {
    ElMessageBox.confirm(
        `确定删除项目 "${row.name}" 吗？仿真任务与结果会保留（任务变为未关联）。`,
        '提示',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
        .then(async () => {
            try {
                await deleteProject(row.id)
                ElMessage.success('项目已删除')
                await loadProjects()
            } catch (error: any) {
                ElMessage.error(error?.response?.data?.detail || '删除失败')
            }
        })
        .catch(() => { })
}

const goToNewProject = () => {
    router.push('/project/new')
}

onMounted(async () => {
    await loadProjects()
    const targetId = route.query.id
    if (targetId) {
        const target = projects.value.find((item) => String(item.id) === String(targetId))
        if (target) void openDetail(target)
    }
})
</script>

<style scoped>
.projects {
    padding: 0;
}

.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.mono {
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12px;
}
</style>
