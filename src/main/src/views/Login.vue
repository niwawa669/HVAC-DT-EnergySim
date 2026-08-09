<template>
    <div class="login-container">
        <el-card class="login-card">
            <div class="login-header">
                <h2>暖通空调能耗仿真系统</h2>
                <p class="subtitle">HVAC Energy Simulation System</p>
            </div>

            <el-form ref="loginFormRef" :model="loginForm" :rules="rules" @submit.prevent="handleLogin">
                <el-form-item prop="username">
                    <el-input v-model="loginForm.username" placeholder="请输入用户名" clearable size="large">
                        <template #prefix>
                            <el-icon>
                                <User />
                            </el-icon>
                        </template>
                    </el-input>
                </el-form-item>

                <el-form-item prop="password">
                    <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password
                        size="large" @keyup.enter="handleLogin">
                        <template #prefix>
                            <el-icon>
                                <Lock />
                            </el-icon>
                        </template>
                    </el-input>
                </el-form-item>

                <el-form-item>
                    <el-button type="primary" size="large" :loading="loading" @click="handleLogin" style="width: 100%">
                        {{ loading ? '登录中...' : '登 录' }}
                    </el-button>
                </el-form-item>

                <div class="login-tips">
                    <span>演示账号: admin</span>
                    <span>密码: 123456</span>
                </div>
            </el-form>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/userStore'
import { login } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const loginFormRef = ref()

const loginForm = reactive({
    username: 'admin',
    password: '123456'
})

const rules = {
    username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
    ],
    password: [
        { required: true, message: '请输入密码', trigger: 'blur' }
    ]
}

const handleLogin = async () => {
    if (!loginFormRef.value) return

    await loginFormRef.value.validate(async (valid: boolean) => {
        if (!valid) return

        loading.value = true
        try {
            const response = await login({
                username: loginForm.username,
                password: loginForm.password
            })

            userStore.setAuth({
                access_token: response.access_token,
                user: response.user
            })

            ElMessage.success('登录成功！欢迎回来 👋')
            router.push('/')
        } catch (error: any) {
            ElMessage.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
        } finally {
            loading.value = false
        }
    })
}
</script>

<style scoped>
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
}

.login-card {
    width: 420px;
    max-width: 100%;
    padding: 35px 30px 25px;
    border-radius: 12px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    background: #ffffff;
}

.login-header {
    text-align: center;
    margin-bottom: 32px;
}

.login-header h2 {
    color: #303133;
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 4px 0;
}

.login-header .subtitle {
    color: #909399;
    font-size: 14px;
    margin: 0;
    letter-spacing: 1px;
}

.login-tips {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 14px;
    color: #909399;
    font-size: 13px;
}

.login-tips span {
    background: #f5f7fa;
    padding: 2px 14px;
    border-radius: 4px;
}

/* 输入框样式 */
:deep(.el-input__wrapper) {
    height: 44px !important;
    border-radius: 8px;
    padding: 0 16px;
    box-shadow: 0 0 0 1px #dcdfe6 !important;
}

:deep(.el-input__wrapper:hover) {
    box-shadow: 0 0 0 1px #c0c4cc !important;
}

:deep(.el-input__wrapper.is-focus) {
    box-shadow: 0 0 0 1px #409EFF !important;
}

:deep(.el-input__inner) {
    height: 44px !important;
    line-height: 44px !important;
    font-size: 15px !important;
}

:deep(.el-input__prefix .el-icon) {
    font-size: 18px !important;
}

:deep(.el-button) {
    height: 44px !important;
    border-radius: 8px;
    font-size: 16px !important;
    font-weight: 500;
}
</style>