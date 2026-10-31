<template>
    <div class="report-view">
        <el-card shadow="never" class="toolbar-card">
            <div class="toolbar">
                <div class="left">
                    <el-button @click="goBack">返回监控</el-button>
                    <el-button type="primary" :disabled="!html" @click="printReport">
                        打印 / 另存为 PDF
                    </el-button>
                    <el-button :disabled="!html" @click="reload">重新加载</el-button>
                </div>
                <div class="right">
                    <span v-if="meta" class="meta">
                        报告 {{ meta.reportId }} · 生成于 {{ meta.generatedAt }} · 口径 {{ meta.caliberVersion }}
                    </span>
                </div>
            </div>
        </el-card>

        <el-alert v-if="error" :title="error" type="error" :closable="false" class="error-alert" />
        <el-alert v-if="loading" title="报告加载中…" type="info" :closable="false" class="error-alert" />

        <!-- 报告为后端生成的自包含 HTML：用 Blob URL 内嵌，打印即为 A4 版式 -->
        <iframe
            v-if="objectUrl"
            ref="frameRef"
            :src="objectUrl"
            class="report-frame"
            title="全年冷源站能耗仿真报告"
        />
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReportMeta, getReportHtml } from '@/api/reports'
import type { ReportMeta } from '@/api/reports'

const route = useRoute()
const router = useRouter()
const reportId = String(route.params.reportId || '')

const html = ref('')
const objectUrl = ref('')
const meta = ref<ReportMeta | null>(null)
const error = ref('')
const loading = ref(false)
const frameRef = ref<HTMLIFrameElement | null>(null)

function revoke() {
    if (objectUrl.value) {
        URL.revokeObjectURL(objectUrl.value)
        objectUrl.value = ''
    }
}

async function load() {
    error.value = ''
    loading.value = true
    revoke()
    try {
        // 元信息与正文都要能取到；任一失败即视为报告不可用
        meta.value = await getReportMeta(reportId)
        const text = await getReportHtml(reportId)
        if (!text || !text.trim()) {
            throw new Error('报告内容为空')
        }
        html.value = text
        objectUrl.value = URL.createObjectURL(new Blob([text], { type: 'text/html;charset=utf-8' }))
        await nextTick()
    } catch (e: any) {
        const detail = e?.response?.data?.detail || e?.message || '报告加载失败'
        error.value = String(detail)
        html.value = ''
    } finally {
        loading.value = false
    }
}

function reload() {
    void load()
}

function printReport() {
    const win = frameRef.value?.contentWindow
    if (!win) {
        ElMessage.warning('报告尚未就绪，请稍后重试')
        return
    }
    // 报告 HTML 自带 @page A4 样式，这里直接触发浏览器打印即可
    win.focus()
    win.print()
}

function goBack() {
    const taskId = meta.value?.taskId || String(route.query.taskId || '')
    router.push(taskId ? `/simulation/${taskId}` : '/')
}

onMounted(() => {
    if (!reportId) {
        error.value = '缺少报告标识'
        return
    }
    void load()
})

onUnmounted(revoke)
</script>

<style scoped>
.report-view {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
}

.toolbar-card :deep(.el-card__body) {
    padding: 10px 14px;
}

.toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.meta {
    color: #909399;
    font-size: 12px;
}

.report-frame {
    flex: 1;
    width: 100%;
    min-height: 720px;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    background: #ffffff;
}
</style>
