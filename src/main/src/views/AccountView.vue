<template>
    <div class="account">
        <el-row :gutter="20">
            <el-col :span="12">
                <el-card shadow="hover">
                    <template #header>
                        <span>基本信息</span>
                    </template>
                    <el-form label-width="90px" v-loading="loading">
                        <el-form-item label="用户名">
                            <el-input :model-value="profile.username" disabled />
                        </el-form-item>
                        <el-form-item label="角色">
                            <el-tag :type="profile.role === 'admin' ? 'danger' : 'info'">
                                {{ roleLabel }}
                            </el-tag>
                        </el-form-item>
                        <el-form-item label="邮箱">
                            <el-input v-model="profileForm.email" placeholder="用于接收通知，可留空" clearable />
                        </el-form-item>
                        <el-form-item>
                            <el-button type="primary" :loading="savingProfile" @click="saveProfile">
                                保存资料
                            </el-button>
                        </el-form-item>
                    </el-form>
                </el-card>
            </el-col>

            <el-col :span="12">
                <el-card shadow="hover">
                    <template #header>
                        <span>修改密码</span>
                    </template>
                    <el-form label-width="90px">
                        <el-form-item label="当前密码">
                            <el-input v-model="passwordForm.currentPassword" type="password" show-password
                                placeholder="请输入当前密码" />
                        </el-form-item>
                        <el-form-item label="新密码">
                            <el-input v-model="passwordForm.newPassword" type="password" show-password
                                placeholder="至少 6 位" />
                        </el-form-item>
                        <el-form-item label="确认新密码">
                            <el-input v-model="passwordForm.confirmPassword" type="password" show-password
                                placeholder="再次输入新密码" @keyup.enter="savePassword" />
                        </el-form-item>
                        <el-form-item>
                            <el-button type="primary" :loading="savingPassword" @click="savePassword">
                                更新密码
                            </el-button>
                        </el-form-item>
                    </el-form>
                    <div class="hint">
                        密码至少 6 位，且不能与当前密码相同。修改成功后当前登录仍然有效；若在其他设备登录，需要重新登录。
                    </div>
                </el-card>
            </el-col>
        </el-row>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { changePassword, getCurrentUser, updateProfile } from '@/api/auth'
import { useUserStore } from '@/stores/userStore'

const userStore = useUserStore()

const profile = reactive({
    username: '',
    role: '',
    email: '',
})
const profileForm = reactive({ email: '' })
const passwordForm = reactive({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
})

const loading = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)

const roleLabel = computed(() => (profile.role === 'admin' ? '管理员' : '工程师'))

const loadProfile = async () => {
    loading.value = true
    try {
        const me = await getCurrentUser()
        profile.username = me.username
        profile.role = me.role
        profile.email = me.email || ''
        profileForm.email = me.email || ''
        userStore.updateUser({ email: me.email ?? null })
    } catch (error) {
        console.error('加载账户信息失败:', error)
    } finally {
        loading.value = false
    }
}

onMounted(loadProfile)

const saveProfile = async () => {
    savingProfile.value = true
    try {
        const updated = await updateProfile({ email: profileForm.email.trim() || null })
        profile.email = updated.email || ''
        profileForm.email = updated.email || ''
        userStore.updateUser({ email: updated.email ?? null })
        ElMessage.success('资料已保存')
    } catch (error) {
        console.error('保存资料失败:', error)
    } finally {
        savingProfile.value = false
    }
}

const savePassword = async () => {
    if (!passwordForm.currentPassword) {
        ElMessage.warning('请输入当前密码')
        return
    }
    if (passwordForm.newPassword.length < 6) {
        ElMessage.warning('新密码至少 6 位')
        return
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
        ElMessage.warning('两次输入的新密码不一致')
        return
    }

    savingPassword.value = true
    try {
        const result = await changePassword({
            currentPassword: passwordForm.currentPassword,
            newPassword: passwordForm.newPassword,
        })
        ElMessage.success(result.message || '密码已更新')
        passwordForm.currentPassword = ''
        passwordForm.newPassword = ''
        passwordForm.confirmPassword = ''
    } catch (error) {
        console.error('修改密码失败:', error)
    } finally {
        savingPassword.value = false
    }
}
</script>

<style scoped>
.account {
    padding: 0;
}

.hint {
    color: #909399;
    font-size: 12px;
    line-height: 1.6;
    padding: 0 10px;
}
</style>
