<template>
    <el-container class="app-layout">
        <el-aside :width="isCollapse ? '64px' : '220px'" class="app-sidebar">
            <div class="logo-container">
                <img src="/vite.svg" alt="Logo" class="logo" />
                <span v-if="!isCollapse" class="logo-text">HVAC仿真</span>
            </div>

            <el-menu :default-active="activeMenu" :collapse="isCollapse" router class="sidebar-menu">
                <el-menu-item index="/">
                    <el-icon>
                        <DataBoard />
                    </el-icon>
                    <span>仪表板</span>
                </el-menu-item>
                <el-menu-item index="/project/new">
                    <el-icon>
                        <Plus />
                    </el-icon>
                    <span>新建项目</span>
                </el-menu-item>
                <el-menu-item index="/projects">
                    <el-icon>
                        <Folder />
                    </el-icon>
                    <span>项目列表</span>
                </el-menu-item>
                <el-menu-item v-if="isAdmin" index="/admin/users">
                    <el-icon>
                        <Setting />
                    </el-icon>
                    <span>用户管理</span>
                </el-menu-item>
            </el-menu>

            <div class="sidebar-footer">
                <el-button :icon="isCollapse ? 'Expand' : 'Fold'" @click="toggleCollapse" text />
            </div>
        </el-aside>

        <el-container>
            <el-header class="app-header">
                <div class="header-left">
                    <h3 style="margin: 0;">{{ currentPageTitle || 'HVAC仿真系统' }}</h3>
                </div>
                <div class="header-right">
                    <el-button @click="handleLogout" text>退出登录</el-button>
                </div>
            </el-header>

            <el-main class="app-main">
                <router-view />
            </el-main>
        </el-container>
    </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataBoard, Plus, Folder, Setting } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/userStore'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const isAdmin = computed(() => userStore.isAdmin)

const activeMenu = computed(() => route.path)

const currentPageTitle = computed(() => {
    const titles: Record<string, string> = {
        '/': '仪表板',
        '/project/new': '新建项目',
        '/projects': '项目列表',
        '/admin/users': '用户管理'
    }
    return titles[route.path] || ''
})

const toggleCollapse = () => {
    isCollapse.value = !isCollapse.value
}

const handleLogout = () => {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
}
</script>

<style scoped>
.app-layout {
    height: 100vh;
}

.app-sidebar {
    background-color: #304156;
    transition: width 0.3s;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.logo-container {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid #1f2d3d;
}

.logo {
    width: 32px;
    height: 32px;
}

.logo-text {
    color: #ffffff;
    font-size: 18px;
    font-weight: bold;
    margin-left: 10px;
}

.sidebar-menu {
    flex: 1;
    border-right: none;
    background-color: #304156;
}

.sidebar-menu :deep(.el-menu-item) {
    color: #bfcbd9;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
    color: #409EFF;
    background-color: #1f2d3d;
}

.sidebar-footer {
    padding: 10px 0;
    border-top: 1px solid #1f2d3d;
    display: flex;
    justify-content: center;
}

.app-header {
    background-color: #ffffff;
    border-bottom: 1px solid #e4e7ed;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 20px;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 16px;
}

.app-main {
    background-color: #f0f2f5;
    padding: 20px;
    overflow-y: auto;
}
</style>