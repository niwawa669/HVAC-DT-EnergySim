<template>
    <div class="dashboard">
        <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false"
            style="margin-bottom: 16px;" />

        <!-- 统计卡片 -->
        <el-row :gutter="20">
            <el-col :span="6" v-for="stat in stats" :key="stat.label">
                <el-card shadow="hover" class="stat-card">
                    <div class="stat-content">
                        <div class="stat-icon" :style="{ backgroundColor: stat.bgColor }">
                            <el-icon :size="28" :color="stat.color">
                                <component :is="stat.icon" />
                            </el-icon>
                        </div>
                        <div class="stat-info">
                            <span class="stat-label">{{ stat.label }}</span>
                            <span class="stat-value">{{ stat.value }}</span>
                        </div>
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 快捷操作 -->
        <el-row style="margin-top: 20px;">
            <el-col :span="24">
                <el-card shadow="hover">
                    <template #header>
                        <span>快捷操作</span>
                    </template>
                    <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                        <el-button type="primary" @click="goToNewProject">
                            <el-icon :size="16"><Plus /></el-icon> 新建项目
                        </el-button>
                        <el-button @click="goToProjects">
                            <el-icon :size="16"><Folder /></el-icon> 项目列表
                        </el-button>
                        <el-button @click="goToSimulation">
                            <el-icon :size="16"><VideoPlay /></el-icon> 仿真监控
                        </el-button>
                        <el-button @click="goToResults">
                            <el-icon :size="16"><DataAnalysis /></el-icon> 查看结果
                        </el-button>
                    </div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 最近项目 -->
        <el-row style="margin-top: 20px;">
            <el-col :span="24">
                <el-card shadow="hover">
                    <template #header>
                        <div class="card-header">
                            <span>最近项目</span>
                            <el-button link type="primary" @click="goToProjects">全部项目</el-button>
                        </div>
                    </template>
                    <el-table :data="recentProjects" v-loading="loading" style="width: 100%"
                        empty-text="暂无项目：点击「新建项目」发起一次仿真，完成后会自动出现在这里">
                        <el-table-column prop="name" label="项目名称" min-width="200" />
                        <el-table-column label="建筑类型" width="120">
                            <template #default="{ row }">{{ buildingTypeLabel(row.buildingType) }}</template>
                        </el-table-column>
                        <el-table-column label="状态" width="110">
                            <template #default="{ row }">
                                <el-tag :type="projectStatusTagType(row.status)" size="small">
                                    {{ projectStatusLabel(row.status) }}
                                </el-tag>
                            </template>
                        </el-table-column>
                        <el-table-column label="最近仿真" width="150">
                            <template #default="{ row }">
                                <span v-if="row.latestTask">
                                    {{ projectStatusLabel(row.latestTask.status) }} {{ row.latestTask.progress }}%
                                </span>
                                <span v-else>—</span>
                            </template>
                        </el-table-column>
                        <el-table-column label="更新时间" width="170">
                            <template #default="{ row }">{{ formatDateTime(row.updatedAt || row.createdAt) }}</template>
                        </el-table-column>
                        <el-table-column label="操作" width="180">
                            <template #default="{ row }">
                                <el-button size="small" @click="viewProject(row)">查看</el-button>
                                <el-button v-if="row.latestTask" size="small" type="primary" @click="openSimulation(row)">
                                    仿真
                                </el-button>
                            </template>
                        </el-table-column>
                    </el-table>
                </el-card>
            </el-col>
        </el-row>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
    Plus, Folder, VideoPlay, DataAnalysis,
    Document, Check, Timer, DataBoard,
} from '@element-plus/icons-vue'

import { getProjects, type Project } from '@/api/projects'
import {
    buildingTypeLabel,
    formatDateTime,
    projectStatusLabel,
    projectStatusTagType,
} from '@/utils/projectDisplay'

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)
const loadError = ref('')

const countByStatus = (statuses: string[]) =>
    projects.value.filter((item) => statuses.includes(item.status)).length

const stats = computed(() => [
    {
        label: '总项目数',
        value: projects.value.length,
        icon: Document,
        color: '#409EFF',
        bgColor: 'rgba(64, 158, 255, 0.1)',
    },
    {
        label: '已完成',
        value: countByStatus(['completed']),
        icon: Check,
        color: '#67C23A',
        bgColor: 'rgba(103, 194, 58, 0.1)',
    },
    {
        label: '运行中',
        value: countByStatus(['running']),
        icon: Timer,
        color: '#E6A23C',
        bgColor: 'rgba(230, 162, 60, 0.1)',
    },
    {
        label: '待处理',
        value: countByStatus(['pending', 'draft']),
        icon: DataBoard,
        color: '#F56C6C',
        bgColor: 'rgba(245, 108, 108, 0.1)',
    },
])

const recentProjects = computed(() => projects.value.slice(0, 5))

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

onMounted(loadProjects)

const goToNewProject = () => router.push('/project/new')
const goToProjects = () => router.push('/projects')

const viewProject = (row: Project) =>
    router.push({ path: '/projects', query: { id: String(row.id) } })

const openSimulation = (row: Project) => {
    if (row.latestTask?.taskId) {
        router.push(`/simulation/${row.latestTask.taskId}`)
    }
}

const goToSimulation = () => {
    const running = projects.value.find((item) => item.latestTask?.status === 'running')
    const anyTask = running || projects.value.find((item) => item.latestTask)
    if (anyTask?.latestTask?.taskId) {
        router.push(`/simulation/${anyTask.latestTask.taskId}`)
    } else {
        ElMessage.info('暂无可查看的仿真任务，请先新建项目')
    }
}

const goToResults = () => {
    const done = projects.value.find(
        (item) => item.latestTask?.status === 'completed' && item.latestTask,
    )
    if (done?.latestTask?.taskId) {
        router.push(`/simulation/${done.latestTask.taskId}`)
    } else {
        ElMessage.info('暂无已完成的结果')
    }
}
</script>

<style scoped>
.dashboard {
    padding: 0;
}

.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.stat-card {
    height: 100%;
    transition: transform 0.2s;
}

.stat-card:hover {
    transform: translateY(-4px);
}

.stat-content {
    display: flex;
    align-items: center;
    padding: 10px 0;
}

.stat-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.stat-icon .el-icon {
    font-size: 28px !important;
    width: 28px !important;
    height: 28px !important;
}

.stat-info {
    margin-left: 16px;
    flex: 1;
}

.stat-label {
    font-size: 14px;
    color: #909399;
    display: block;
}

.stat-value {
    font-size: 28px;
    font-weight: bold;
    color: #303133;
    display: block;
    line-height: 1.4;
}

:deep(.el-button .el-icon) {
    font-size: 16px !important;
    width: 16px !important;
    height: 16px !important;
}
</style>
