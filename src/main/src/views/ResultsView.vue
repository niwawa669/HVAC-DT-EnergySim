<template>
    <div>
        <h2>仿真结果</h2>
        <el-card style="margin-top: 20px;">
            <el-row :gutter="20">
                <el-col :span="6" v-for="item in results" :key="item.label">
                    <div style="text-align: center; padding: 10px;">
                        <div style="color: #909399;">{{ item.label }}</div>
                        <div style="font-size: 24px; font-weight: bold; color: #409EFF;">{{ item.value }}</div>
                    </div>
                </el-col>
            </el-row>
        </el-card>
        <el-button style="margin-top: 20px;" @click="goBack">返回</el-button>
    </div>
</template>

<script>
export default {
    name: 'ResultsView',
    data() {
        return {
            results: [
                { label: '总能耗', value: '125,000 kWh' },
                { label: '平均COP', value: '3.2' },
                { label: '峰值负荷', value: '450 kW' },
                { label: 'EUI', value: '85.6 kWh/m²' }
            ]
        }
    },
    methods: {
        goBack() {
            this.$router.push('/')
        }
    }
}
</script>