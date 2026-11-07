<template>
    <div class="admin-users">
        <el-card shadow="hover">
            <template #header>
                <div class="card-header">
                    <span>账户管理</span>
                    <div>
                        <el-button size="small" :loading="loading" @click="load">刷新</el-button>
                        <el-button type="primary" size="small" @click="openCreate">新建账户</el-button>
                    </div>
                </div>
            </template>

            <div class="toolbar">
                <el-input v-model="search" placeholder="按用户名或邮箱搜索" clearable style="width: 260px;"
                    @keyup.enter="reload" />
                <el-button type="primary" @click="reload">搜索</el-button>
                <el-button @click="resetSearch">重置</el-button>
            </div>

            <el-table :data="items" v-loading="loading" style="width: 100%"
                empty-text="没有匹配的账户">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="username" label="用户名" min-width="140" />
                <el-table-column label="邮箱" min-width="200">
                    <template #default="{ row }">{{ row.email || '—' }}</template>
                </el-table-column>
                <el-table-column label="角色" width="110">
                    <template #default="{ row }">
                        <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                            {{ roleLabel(row.role) }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                    <template #default="{ row }">
                        <el-tag :type="row.isActive ? 'success' : 'info'" size="small">
                            {{ row.isActive ? '启用' : '停用' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="创建时间" width="170">
                    <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="240" fixed="right">
                    <template #default="{ row }">
                        <el-button size="small" @click="openEdit(row)">编辑</el-button>
                        <el-button size="small" @click="openReset(row)">重置密码</el-button>
                        <el-button size="small" type="danger" :disabled="row.id === currentUserId"
                            @click="removeAccount(row)">
                            删除
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>

            <div class="pagination">
                <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
                    layout="total, prev, pager, next" @current-change="load" />
            </div>
        </el-card>

        <!-- 新建账户 -->
        <el-dialog v-model="createVisible" title="新建账户" width="480px" destroy-on-close>
            <el-form label-width="80px">
                <el-form-item label="用户名" required>
                    <el-input v-model="createForm.username" placeholder="3-64 位字母、数字、下划线或点" />
                </el-form-item>
                <el-form-item label="初始密码" required>
                    <el-input v-model="createForm.password" type="password" show-password placeholder="至少 6 位" />
                </el-form-item>
                <el-form-item label="邮箱">
                    <el-input v-model="createForm.email" placeholder="可留空" />
                </el-form-item>
                <el-form-item label="角色">
                    <el-select v-model="createForm.role" style="width: 100%;">
                        <el-option label="工程师（普通用户）" value="engineer" />
                        <el-option label="管理员" value="admin" />
                    </el-select>
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="createVisible = false">取消</el-button>
                <el-button type="primary" :loading="creating" @click="createAccount">创建</el-button>
            </template>
        </el-dialog>

        <!-- 编辑账户 -->
        <el-dialog v-model="editVisible" title="编辑账户" width="480px" destroy-on-close>
            <el-form label-width="80px">
                <el-form-item label="用户名">
                    <el-input :model-value="editTarget?.username" disabled />
                </el-form-item>
                <el-form-item label="邮箱">
                    <el-input v-model="editForm.email" placeholder="可留空" />
                </el-form-item>
                <el-form-item label="角色">
                    <el-select v-model="editForm.role" :disabled="editingSelf" style="width: 100%;">
                        <el-option label="工程师（普通用户）" value="engineer" />
                        <el-option label="管理员" value="admin" />
                    </el-select>
                </el-form-item>
                <el-form-item label="启用">
                    <el-switch v-model="editForm.isActive" :disabled="editingSelf" />
                    <span class="form-hint">{{ editingSelf ? '不能修改自己的角色或停用自己' : '停用后该账户无法登录' }}</span>
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="editVisible = false">取消</el-button>
                <el-button type="primary" :loading="savingEdit" @click="saveEdit">保存</el-button>
            </template>
        </el-dialog>

        <!-- 重置密码 -->
        <el-dialog v-model="resetVisible" title="重置密码" width="440px" destroy-on-close>
            <el-form label-width="90px">
                <el-form-item label="账户">
                    <el-input :model-value="resetTarget?.username" disabled />
                </el-form-item>
                <el-form-item label="新密码" required>
                    <el-input v-model="resetForm.newPassword" type="password" show-password placeholder="至少 6 位" />
                </el-form-item>
                <el-form-item label="确认新密码" required>
                    <el-input v-model="resetForm.confirmPassword" type="password" show-password placeholder="再次输入" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="resetVisible = false">取消</el-button>
                <el-button type="primary" :loading="resetting" @click="saveReset">重置</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
    createUser,
    deleteUser,
    listUsers,
    resetUserPassword,
    updateUser,
    type AccountItem,
    type UpdateUserParams,
    type UserRole,
} from '@/api/users'
import { useUserStore } from '@/stores/userStore'
import { formatDateTime } from '@/utils/projectDisplay'

const userStore = useUserStore()
const currentUserId = computed(() => userStore.user?.id ?? -1)

const items = ref<AccountItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const search = ref('')
const loading = ref(false)

const roleLabel = (role: string) => (role === 'admin' ? '管理员' : '工程师')

const load = async () => {
    loading.value = true
    try {
        const result = await listUsers({
            search: search.value.trim() || undefined,
            page: page.value,
            pageSize,
        })
        items.value = result.items
        total.value = result.total
    } catch (error) {
        console.error('加载账户列表失败:', error)
    } finally {
        loading.value = false
    }
}

const reload = () => {
    page.value = 1
    void load()
}

const resetSearch = () => {
    search.value = ''
    reload()
}

onMounted(load)

// ===== 新建 =====
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
    username: '',
    password: '',
    email: '',
    role: 'engineer' as UserRole,
})

const openCreate = () => {
    createForm.username = ''
    createForm.password = ''
    createForm.email = ''
    createForm.role = 'engineer'
    createVisible.value = true
}

const createAccount = async () => {
    const username = createForm.username.trim()
    if (username.length < 3) {
        ElMessage.warning('用户名至少 3 位')
        return
    }
    if (!/^[A-Za-z0-9_.-]+$/.test(username)) {
        ElMessage.warning('用户名只能包含字母、数字、下划线、点和短横线')
        return
    }
    if (createForm.password.length < 6) {
        ElMessage.warning('初始密码至少 6 位')
        return
    }

    creating.value = true
    try {
        await createUser({
            username,
            password: createForm.password,
            email: createForm.email.trim() || null,
            role: createForm.role,
        })
        ElMessage.success('账户已创建')
        createVisible.value = false
        reload()
    } catch (error) {
        console.error('创建账户失败:', error)
    } finally {
        creating.value = false
    }
}

// ===== 编辑 =====
const editVisible = ref(false)
const savingEdit = ref(false)
const editTarget = ref<AccountItem | null>(null)
const editForm = reactive({
    email: '',
    role: 'engineer' as UserRole,
    isActive: true,
})

const editingSelf = computed(() => editTarget.value?.id === currentUserId.value)

const openEdit = (row: AccountItem) => {
    editTarget.value = row
    editForm.email = row.email || ''
    editForm.role = (row.role as UserRole) || 'engineer'
    editForm.isActive = row.isActive
    editVisible.value = true
}

const saveEdit = async () => {
    if (!editTarget.value) return
    const payload: UpdateUserParams = { email: editForm.email.trim() || null }
    if (!editingSelf.value) {
        payload.role = editForm.role
        payload.isActive = editForm.isActive
    }

    savingEdit.value = true
    try {
        await updateUser(editTarget.value.id, payload)
        ElMessage.success('账户已更新')
        editVisible.value = false
        await load()
    } catch (error) {
        console.error('更新账户失败:', error)
    } finally {
        savingEdit.value = false
    }
}

// ===== 重置密码 =====
const resetVisible = ref(false)
const resetting = ref(false)
const resetTarget = ref<AccountItem | null>(null)
const resetForm = reactive({ newPassword: '', confirmPassword: '' })

const openReset = (row: AccountItem) => {
    resetTarget.value = row
    resetForm.newPassword = ''
    resetForm.confirmPassword = ''
    resetVisible.value = true
}

const saveReset = async () => {
    if (!resetTarget.value) return
    if (resetForm.newPassword.length < 6) {
        ElMessage.warning('新密码至少 6 位')
        return
    }
    if (resetForm.newPassword !== resetForm.confirmPassword) {
        ElMessage.warning('两次输入的新密码不一致')
        return
    }

    resetting.value = true
    try {
        await resetUserPassword(resetTarget.value.id, resetForm.newPassword)
        ElMessage.success('密码已重置')
        resetVisible.value = false
    } catch (error) {
        console.error('重置密码失败:', error)
    } finally {
        resetting.value = false
    }
}

// ===== 删除 =====
const removeAccount = (row: AccountItem) => {
    ElMessageBox.confirm(
        `确定删除账户 "${row.username}" 吗？已有项目或仿真任务的账户不允许删除，请改为停用。`,
        '提示',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
        .then(async () => {
            try {
                await deleteUser(row.id)
                ElMessage.success('账户已删除')
                if (items.value.length === 1 && page.value > 1) {
                    page.value -= 1
                }
                await load()
            } catch (error) {
                console.error('删除账户失败:', error)
            }
        })
        .catch(() => { })
}
</script>

<style scoped>
.admin-users {
    padding: 0;
}

.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.toolbar {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;
}

.pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}

.form-hint {
    margin-left: 12px;
    color: #909399;
    font-size: 12px;
}
</style>
