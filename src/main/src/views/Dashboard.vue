<template>
    <div class="dashboard">
        <!-- 统计卡片 -->
        <el-row :gutter="20">
            <el-col :span="6" v-for="stat in stats" :key="stat.label">
                <el-card shadow="hover" class="stat-card">
                    <div class="stat-content">
                        <div class="stat-icon" :style="{ backgroundColor: stat.bgColor }">
                            <!-- 显式设置 size="28" -->
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
                            <!-- 显式设置 size="16" -->
                            <el-icon :size="16">
                                <Plus />
                            </el-icon> 新建项目
                        </el-button>
                        <el-button @click="goToProjects">
                            <el-icon :size="16">
                                <Folder />
                            </el-icon> 项目列表
                        </el-button>
                        <el-button @click="goToSimulation">
                            <el-icon :size="16">
                                <VideoPlay />
                            </el-icon> 仿真监控
                        </el-button>
                        <el-button @click="goToResults">
                            <el-icon :size="16">
                                <DataAnalysis />
                            </el-icon> 查看结果
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
                        <span>最近项目</span>
                    </template>
                    <el-table :data="recentProjects" style="width: 100%">
                        <el-table-column prop="name" label="项目名称" />
                        <el-table-column prop="buildingType" label="建筑类型" width="120" />
                        <el-table-column prop="status" label="状态" width="100">
                            <template #default="{ row }">
                                <el-tag :type="getStatusType(row.status)" size="small">
                                    {{ row.status }}
                                </el-tag>
                            </template>
                        </el-table-column>
                        <el-table-column prop="createdAt" label="创建时间" width="180" />
                        <el-table-column label="操作" width="200">
                            <template #default="{ row }">
                                <el-button size="small" @click="viewProject(row)">查看</el-button>
                                <el-button v-if="row.status === '待处理'" type="primary" size="small"
                                    @click="startSimulation(row)">
                                    运行
                                </el-button>
                            </template>
                        </el-table-column>
                    </el-table>
                </el-card>
            </el-col>
        </el-row>
    </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
    Plus, Folder, VideoPlay, DataAnalysis,
    Document, Check, Timer, DataBoard
} from '@element-plus/icons-vue'

export default {
    name: 'Dashboard',
    components: {
        Plus,
        Folder,
        VideoPlay,
        DataAnalysis,
        Document,
        Check,
        Timer,
        DataBoard
    },
    setup() {
        const router = useRouter()

        const stats = ref([
            {
                label: '总项目数',
                value: 12,
                icon: 'Document',
                color: '#409EFF',
                bgColor: 'rgba(64, 158, 255, 0.1)'
            },
            {
                label: '已完成',
                value: 5,
                icon: 'Check',
                color: '#67C23A',
                bgColor: 'rgba(103, 194, 58, 0.1)'
            },
            {
                label: '运行中',
                value: 2,
                icon: 'Timer',
                color: '#E6A23C',
                bgColor: 'rgba(230, 162, 60, 0.1)'
            },
            {
                label: '待处理',
                value: 5,
                icon: 'DataBoard',
                color: '#F56C6C',
                bgColor: 'rgba(245, 108, 108, 0.1)'
            }
        ])

        const recentProjects = ref([
            {
                id: 1,
                name: '办公楼能耗仿真项目',
                buildingType: '办公',
                status: '已完成',
                createdAt: '2026-07-28 14:30'
            },
            {
                id: 2,
                name: '商业综合体能耗分析',
                buildingType: '商业',
                status: '运行中',
                createdAt: '2026-07-29 09:15'
            },
            {
                id: 3,
                name: '住宅小区暖通仿真',
                buildingType: '住宅',
                status: '待处理',
                createdAt: '2026-07-30 16:45'
            }
        ])

        const getStatusType = (status) => {
            const map = {
                '已完成': 'success',
                '运行中': 'warning',
                '待处理': 'info',
                '失败': 'danger'
            }
            return map[status] || 'info'
        }

        const goToNewProject = () => {
            router.push('/project/new')
        }

        const goToProjects = () => {
            router.push('/projects')
        }

        const goToSimulation = () => {
            router.push('/simulation/mock-001')
        }

        const goToResults = () => {
            router.push('/results/1')
        }

        const viewProject = (row) => {
            ElMessage.info(`查看项目: ${row.name}`)
        }

        const startSimulation = (row) => {
            ElMessage.success(`启动仿真: ${row.name}`)
            router.push(`/simulation/mock-${row.id}`)
        }

        return {
            stats,
            recentProjects,
            getStatusType,
            goToNewProject,
            goToProjects,
            goToSimulation,
            goToResults,
            viewProject,
            startSimulation
        }
    }
}
</script>

<style scoped>
.dashboard {
    padding: 0;
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

/* 保险：强制覆盖图标大小 */
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

/* 强制按钮中的图标大小 */
:deep(.el-button .el-icon) {
    font-size: 16px !important;
    width: 16px !important;
    height: 16px !important;
}
</style>