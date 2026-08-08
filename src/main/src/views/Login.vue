<template>
    <div class="login-container">
        <div class="login-card">
            <div class="login-header">
                <h2>暖通空调能耗仿真系统</h2>
                <p class="subtitle">HVAC Energy Simulation System</p>
            </div>

            <!-- 登录表单 -->
            <div class="login-form">
                <!-- 用户名 -->
                <div class="input-group">
                    <div class="input-wrapper">
                        <span class="input-icon">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                                <circle cx="12" cy="7" r="4" />
                            </svg>
                        </span>
                        <input v-model="loginForm.username" type="text" class="login-input" placeholder="请输入用户名"
                            @keyup.enter="handleLogin" />
                        <!-- 清除按钮（×） -->
                        <span v-if="loginForm.username" class="input-suffix clear-btn" @click="loginForm.username = ''">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="15" y1="9" x2="9" y2="15" />
                                <line x1="9" y1="9" x2="15" y2="15" />
                            </svg>
                        </span>
                    </div>
                </div>

                <!-- 密码 -->
                <div class="input-group">
                    <div class="input-wrapper">
                        <span class="input-icon">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                            </svg>
                        </span>
                        <input v-model="loginForm.password" :type="showPassword ? 'text' : 'password'"
                            class="login-input" placeholder="请输入密码" @keyup.enter="handleLogin" />
                        <!-- 密码可见切换 -->
                        <span class="input-suffix" @click="togglePasswordVisibility">
                            <!-- 眼睛打开（可见） -->
                            <svg v-if="showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                            </svg>
                            <!-- 眼睛关闭（不可见） -->
                            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path
                                    d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                                <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                        </span>
                    </div>
                </div>

                <!-- 登录按钮 -->
                <button class="login-button" :disabled="loading" @click="handleLogin">
                    {{ loading ? '登录中...' : '登 录' }}
                </button>

                <div class="login-tips">
                    <span>演示账号: admin</span>
                    <span>密码: 123456</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/userStore'

export default {
    name: 'Login',
    data() {
        return {
            loginForm: {
                username: 'admin',
                password: '123456'
            },
            showPassword: false,
            loading: false
        }
    },
    methods: {
        togglePasswordVisibility() {
            this.showPassword = !this.showPassword
        },

        validateForm() {
            if (!this.loginForm.username.trim()) {
                ElMessage.warning('请输入用户名')
                return false
            }
            if (!this.loginForm.password.trim()) {
                ElMessage.warning('请输入密码')
                return false
            }
            return true
        },

        handleLogin() {
            if (!this.validateForm()) return

            this.loading = true
            this.mockLogin()
        },

        mockLogin() {
            const { username, password } = this.loginForm

            setTimeout(() => {
                if (username === 'admin' && password === '123456') {
                    const userStore = useUserStore()
                    userStore.setAuth({
                        access_token: 'mock-token-' + Date.now(),
                        user: {
                            id: 1,
                            username: 'admin',
                            role: 'admin',
                            email: 'admin@example.com'
                        }
                    })

                    ElMessage.success('登录成功！欢迎回来 👋')
                    this.loading = false
                    this.$router.push('/')
                } else {
                    ElMessage.error('用户名或密码错误，请重试')
                    this.loading = false
                }
            }, 800)
        }
    }
}
</script>

<style scoped>
/* ===== 全局重置 ===== */
* {
    box-sizing: border-box;
}

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
    padding: 40px 35px 30px;
    border-radius: 12px;
    background: #ffffff;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
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

/* ===== 表单 ===== */
.login-form {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

/* ===== 输入框 ===== */
.input-group {
    width: 100%;
}

.input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    border: 1px solid #dcdfe6;
    border-radius: 8px;
    background: #ffffff;
    transition: border-color 0.2s;
}

.input-wrapper:focus-within {
    border-color: #409EFF;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.input-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 0 0 14px;
    color: #909399;
    flex-shrink: 0;
}

.login-input {
    flex: 1;
    height: 44px;
    padding: 0 12px;
    border: none;
    outline: none;
    font-size: 15px;
    color: #303133;
    background: transparent;
    min-width: 0;
}

.login-input::placeholder {
    color: #c0c4cc;
    font-size: 14px;
}

/* ===== 后缀图标（清除按钮 + 密码切换） ===== */
.input-suffix {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 14px 0 0;
    color: #909399;
    cursor: pointer;
    flex-shrink: 0;
}

.input-suffix:hover {
    color: #409EFF;
}

/* 清除按钮特殊样式 */
.clear-btn {
    color: #c0c4cc;
}

.clear-btn:hover {
    color: #f56c6c;
}

/* ===== 登录按钮 ===== */
.login-button {
    height: 44px;
    width: 100%;
    border: none;
    border-radius: 8px;
    background: #409EFF;
    color: #ffffff;
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 2px;
    cursor: pointer;
    transition: background 0.2s;
    margin-top: 2px;
}

.login-button:hover {
    background: #66b1ff;
}

.login-button:active {
    background: #3a8ee6;
}

.login-button:disabled {
    background: #a0cfff;
    cursor: not-allowed;
}

/* ===== 提示 ===== */
.login-tips {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 6px;
    color: #909399;
    font-size: 13px;
}

.login-tips span {
    background: #f5f7fa;
    padding: 2px 14px;
    border-radius: 4px;
}

/* ===== 响应式 ===== */
@media (max-width: 480px) {
    .login-card {
        padding: 30px 20px 25px;
    }
}
</style>