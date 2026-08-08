<template>
    <div class="projects">
        <el-card>
            <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>项目列表</span>
                    <el-button type="primary" size="small" @click="goToNewProject">新建项目</el-button>
                </div>
            </template>

            <el-input v-model="searchKeyword" placeholder="搜索项目..." style="width: 200px; margin-bottom: 16px;"
                clearable />

            <el-table :data="filteredProjects" style="width: 100%">
                <el-table-column prop="name" label="项目名称" />
                <el-table-column prop="buildingType" label="建筑类型" />
                <el-table-column prop="systemType" label="系统类型" />
                <el-table-column prop="status" label="状态" />
                <el-table-column label="操作" width="200">
                    <template #default="scope">
                        <el-button size="small" @click="viewProject(scope.row)">查看</el-button>
                        <el-button size="small" type="danger" @click="deleteProject(scope.row)">删除</el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-card>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const searchKeyword = ref('')

const projects = ref([
    { name: '办公楼能耗仿真', buildingType: '办公', systemType: 'VAV', status: '已完成' },
    { name: '商业综合体能耗分析', buildingType: '商业', systemType: 'CAV', status: '运行中' },
    { name: '住宅小区暖通仿真', buildingType: '住宅', systemType: 'FCU', status: '待处理' },
    { name: '医院空调系统优化', buildingType: '医院', systemType: 'VAV', status: '待处理' }
])

const filteredProjects = computed(() => {
    if (!searchKeyword.value) return projects.value
    const keyword = searchKeyword.value.toLowerCase()
    return projects.value.filter(p =>
        p.name.toLowerCase().includes(keyword) ||
        p.buildingType.includes(keyword)
    )
})

const goToNewProject = () => {
    router.push('/project/new')
}

const viewProject = (row) => {
    ElMessage.info(`查看: ${row.name}`)
}

const deleteProject = (row) => {
    ElMessageBox.confirm(`确定删除 "${row.name}" 吗？`, '提示', {
        type: 'warning'
    }).then(() => {
        const index = projects.value.indexOf(row)
        if (index > -1) {
            projects.value.splice(index, 1)
            ElMessage.success('删除成功')
        }
    }).catch(() => { })
}
</script>

<style scoped>
.projects {
    padding: 0;
}
</style>