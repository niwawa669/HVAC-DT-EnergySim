<template>
    <div class="project-new">
        <el-card shadow="hover">
            <template #header>
                <div class="card-header">
                    <span>新建仿真项目</span>
                    <el-button size="small" @click="$router.push('/')">返回</el-button>
                </div>
            </template>

            <!-- 步骤条 -->
            <el-steps :active="activeStep" finish-status="success" style="margin-bottom: 30px;">
                <el-step title="上传数据" description="上传负荷和气象数据" />
                <el-step title="冷源站设计方案" description="设备选型与群控参数" />
                <el-step title="启动仿真" description="确认并开始仿真" />
            </el-steps>

            <!-- ===== Step 1: 上传数据 ===== -->
            <div v-show="activeStep === 0" class="step-content">
                <el-form :model="projectForm" label-width="120px">
                    <el-form-item label="项目名称" required>
                        <el-input v-model="projectForm.name" placeholder="请输入项目名称" maxlength="50" show-word-limit />
                    </el-form-item>

                    <el-form-item label="建筑类型" required>
                        <el-select v-model="projectForm.buildingType" placeholder="请选择建筑类型" style="width: 100%;">
                            <el-option label="办公建筑" value="office" />
                            <el-option label="商业建筑" value="commercial" />
                            <el-option label="住宅建筑" value="residential" />
                            <el-option label="医院建筑" value="hospital" />
                            <el-option label="工业建筑" value="industrial" />
                        </el-select>
                    </el-form-item>

                    <el-form-item label="建筑空调面积 (m²)">
                        <el-input-number v-model="projectForm.area" :min="100" :max="1000000" :step="100"
                            controls-position="right" style="width: 100%;" />
                    </el-form-item>

                    <el-form-item label="数据文件" required>
                        <DataUploader @data-confirmed="handleDataConfirmed" />
                    </el-form-item>

                    <el-form-item v-if="dataConfirmed">
                        <el-alert title="✅ 数据已确认" type="success" :closable="false" show-icon>
                            <template #default>
                                <div style="font-size: 13px; margin-top: 4px;">
                                    共 {{ parsedData?.data?.length || 0 }} 行数据，
                                    {{ parsedData?.headers?.length || 0 }} 列
                                </div>
                            </template>
                        </el-alert>
                    </el-form-item>

                    <el-form-item>
                        <el-button type="primary" @click="nextStep" :disabled="!canProceed">
                            下一步
                            <el-icon>
                                <ArrowRight />
                            </el-icon>
                        </el-button>
                    </el-form-item>
                </el-form>
            </div>

            <!-- ===== Step 2: 冷源站设计方案 ===== -->
            <div v-show="activeStep === 1" class="step-content">
                <el-tabs v-model="activeTab" type="border-card">

                    <!-- ===== 设备选型参数 ===== -->
                    <el-tab-pane label="设备选型参数" name="equipment">
                        <el-form :model="equipmentForm" label-width="220px" class="config-form">

                            <!-- 建筑负荷 -->
                            <el-divider content-position="left">建筑负荷</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="建筑负荷 (kW)">
                                        <el-input-number v-model="equipmentForm.load_building_r" :min="0" :step="100"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="量纲换算系数 (W→kW)">
                                        <el-input-number v-model="equipmentForm.load_coe" :min="0" :step="0.001"
                                            :precision="4" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <!-- 冷机参数 -->
                            <el-divider content-position="left">冷机参数</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机额定制冷量 (kW)">
                                        <el-input-number v-model="equipmentForm.Qr_chiller_BCH" :min="0" :step="10"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="大机台数">
                                        <el-input-number v-model="equipmentForm.n_design_BCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机COP（仅展示，不参与计算）">
                                        <el-input-number v-model="equipmentForm.COP_chiller_BCH" :min="0" :max="10"
                                            :step="0.1" :precision="2" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机额定制冷量 (kW)">
                                        <el-input-number v-model="equipmentForm.Qr_chiller_SCH" :min="0" :step="10"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="小机台数">
                                        <el-input-number v-model="equipmentForm.n_design_SCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机COP（仅展示，不参与计算）">
                                        <el-input-number v-model="equipmentForm.COP_chiller_SCH" :min="0" :max="10"
                                            :step="0.1" :precision="2" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷机冷冻水供水温度 (°C)">
                                        <el-input-number v-model="equipmentForm.ts_chw_design" :min="0" :max="20"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷机冷冻水回水温度 (°C)">
                                        <el-input-number v-model="equipmentForm.tr_chw_design" :min="0" :max="25"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷机冷却水进水温度 (°C)">
                                        <el-input-number v-model="equipmentForm.tr_cw_design" :min="0" :max="50"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷机冷却水出水温度 (°C)">
                                        <el-input-number v-model="equipmentForm.ts_cw_design" :min="0" :max="50"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <!-- 冷冻泵参数 -->
                            <el-divider content-position="left">冷冻泵参数</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷冻泵设计流量 (L/s)">
                                        <el-input-number v-model="equipmentForm.Gr_pump_chw_BCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="大机冷冻泵设计扬程 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_pump_chw_BCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷冻泵台数">
                                        <el-input-number v-model="equipmentForm.n_pump_chw_BCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷冻泵设计流量 (L/s)">
                                        <el-input-number v-model="equipmentForm.Gr_pump_chw_SCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="小机冷冻泵设计扬程 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_pump_chw_SCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷冻泵台数">
                                        <el-input-number v-model="equipmentForm.n_pump_chw_SCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                            <!-- 冷却泵参数 -->
                            <el-divider content-position="left">冷却泵参数</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷却泵设计流量 (L/s)">
                                        <el-input-number v-model="equipmentForm.Gr_pump_cw_BCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="大机冷却泵设计扬程 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_pump_cw_BCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷却泵台数">
                                        <el-input-number v-model="equipmentForm.n_pump_cw_BCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷却泵设计流量 (L/s)">
                                        <el-input-number v-model="equipmentForm.Gr_pump_cw_SCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="小机冷却泵设计扬程 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_pump_cw_SCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷却泵台数">
                                        <el-input-number v-model="equipmentForm.n_pump_cw_SCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                            <!-- 冷却塔参数 -->
                            <el-divider content-position="left">冷却塔参数</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷却塔设计流量 (L/s)">
                                        <el-input-number v-model="equipmentForm.Gr_tower_BCH" :min="0" :step="10"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="大机冷却塔设计功率 (kW)（仅展示）">
                                        <el-input-number v-model="equipmentForm.Pr_tower_BCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷却塔设计压降 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hs_tower_BCH" :min="0" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="大机冷却塔台数">
                                        <el-input-number v-model="equipmentForm.n_tower_BCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷却塔设计流量 (L/s)">
                                        <el-input-number v-model="equipmentForm.Gr_tower_SCH" :min="0" :step="10"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="小机冷却塔设计功率 (kW)（仅展示）">
                                        <el-input-number v-model="equipmentForm.Pr_tower_SCH" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷却塔设计压降 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hs_tower_SCH" :min="0" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="小机冷却塔台数">
                                        <el-input-number v-model="equipmentForm.n_tower_SCH" :min="1" :max="10"
                                            :step="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <!-- 管道压降 -->
                            <el-divider content-position="left">管道压降</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷冻供回水总管扬程 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_pt" :min="0" :step="1"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="大机冷机冷冻水侧设计压降 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_chiller_chw_BCH" :min="0" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="大机冷机冷却水侧设计压降 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_chiller_cw_BCH" :min="0" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="小机冷机冷冻水侧设计压降 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_chiller_chw_SCH" :min="0" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="小机冷机冷却水侧设计压降 (mH2O)">
                                        <el-input-number v-model="equipmentForm.Hr_chiller_cw_SCH" :min="0" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <!-- 空位 -->
                                </el-col>
                            </el-row>

                        </el-form>
                    </el-tab-pane>

                    <!-- ===== 群控控制参数 ===== -->
                    <el-tab-pane label="群控控制参数" name="control">
                        <el-form :model="controlForm" label-width="220px" class="config-form">

                            <!-- 温度控制 -->
                            <el-divider content-position="left">温度控制</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="室外干球温度设计值 (°C)">
                                        <el-input-number v-model="controlForm.ta_dry_r" :min="0" :max="50" :step="0.1"
                                            :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="室外湿球温度设计值 (°C)">
                                        <el-input-number v-model="controlForm.ta_wet_r" :min="0" :max="50" :step="0.1"
                                            :precision="2" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷冻水供水温度设置值 (°C)">
                                        <el-input-number v-model="controlForm.ts_chw_set" :min="0" :max="20" :step="0.5"
                                            :precision="1" controls-position="right" style="width: 100%;" />
                                        <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                                            默认与冷机参数中的冷冻水供水温度一致，可手动修改
                                        </div>
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷冻水供回水温差设置值 (°C)">
                                        <el-input-number v-model="controlForm.delta_t_chw" :min="0" :max="15"
                                            :step="0.5" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷却水供回水温差设置值 (°C)">
                                        <el-input-number v-model="controlForm.delta_t_cw" :min="0" :max="15" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷却回水温度最小值设置 (°C)">
                                        <el-input-number v-model="controlForm.tr_cw_min" :min="0" :max="50" :step="0.5"
                                            controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷却塔逼近度设置值 (°C)">
                                        <el-input-number v-model="controlForm.approach_set" :min="0" :max="20"
                                            :step="0.5" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <!-- 负荷控制 -->
                            <el-divider content-position="left">负荷控制</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="加机负荷率设置值">
                                        <el-input-number v-model="controlForm.load_up" :min="0" :max="1" :step="0.05"
                                            :precision="2" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷机最小负荷率设置值">
                                        <el-input-number v-model="controlForm.load_min" :min="0" :max="1" :step="0.05"
                                            :precision="2" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <!-- 冷机加机优先级 -->
                            <el-divider content-position="left">冷机加机优先级</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷机加机优先级设置 (Qr_list)">
                                        <el-input v-model="controlForm.Qr_list_str" placeholder="例如: 39.7404, 79.4808"
                                            style="width: 100%;" />
                                        <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                                            按优先级顺序填写冷机额定冷量，用逗号分隔
                                        </div>
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="对应Qr_list的冷机设计台数">
                                        <el-input v-model="controlForm.n_design_list_str" placeholder="例如: 1, 3"
                                            style="width: 100%;" />
                                        <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                                            按优先级顺序填写台数，用逗号分隔
                                        </div>
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <!-- 频率控制 -->
                            <el-divider content-position="left">频率控制</el-divider>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷冻/冷却泵最大频率 (Hz)">
                                        <el-input-number v-model="controlForm.freq_pump_max" :min="0" :max="50"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷冻/冷却泵最小频率 (Hz)">
                                        <el-input-number v-model="controlForm.freq_pump_min" :min="0" :max="50"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                            <el-row :gutter="20">
                                <el-col :span="12">
                                    <el-form-item label="冷却塔风机最大频率 (Hz)">
                                        <el-input-number v-model="controlForm.freq_tower_max" :min="0" :max="50"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                                <el-col :span="12">
                                    <el-form-item label="冷却塔风机最小频率 (Hz)">
                                        <el-input-number v-model="controlForm.freq_tower_min" :min="0" :max="50"
                                            :step="0.5" :precision="1" controls-position="right" style="width: 100%;" />
                                    </el-form-item>
                                </el-col>
                            </el-row>

                        </el-form>
                    </el-tab-pane>
                </el-tabs>

                <div class="step-actions">
                    <el-button @click="prevStep">
                        <el-icon>
                            <ArrowLeft />
                        </el-icon> 上一步
                    </el-button>
                    <el-button type="primary" @click="nextStep">
                        下一步
                        <el-icon>
                            <ArrowRight />
                        </el-icon>
                    </el-button>
                </div>
            </div>

            <!-- ===== Step 3: 启动仿真 ===== -->
            <div v-show="activeStep === 2" class="step-content">
                <div class="config-confirm-container">
                    <div class="config-confirm-header">
                        <el-icon color="#67C23A" :size="20">
                            <CircleCheck />
                        </el-icon>
                        <span>配置确认</span>
                    </div>

                    <div class="config-summary">

                        <!-- ===== 1. 项目信息 ===== -->
                        <el-divider content-position="left">项目信息</el-divider>
                        <el-descriptions :column="3" border size="small" style="width: 100%;">
                            <el-descriptions-item label="项目名称">{{ projectForm.name || '未命名' }}</el-descriptions-item>
                            <el-descriptions-item label="建筑类型">{{ getBuildingTypeLabel(projectForm.buildingType)
                            }}</el-descriptions-item>
                            <el-descriptions-item label="建筑空调面积">{{ projectForm.area || 0 }} m²</el-descriptions-item>
                            <el-descriptions-item label="最大建筑负荷">{{ equipmentForm.load_building_r }}
                                kW</el-descriptions-item>
                            <el-descriptions-item label="单位面积冷负荷">{{ unitLoad }} W/m²</el-descriptions-item>
                            <el-descriptions-item label="仿真周期">{{ parsedData?.data?.length || 0 }}
                                小时</el-descriptions-item>
                        </el-descriptions>

                        <!-- ===== 2. 设备选型 ===== -->
                        <el-divider content-position="left">设备选型</el-divider>

                        <!-- 冷机 -->
                        <div class="sub-title">冷机</div>
                        <el-table :data="chillerTableData" border size="small" style="width: 100%; margin-bottom: 16px;"
                            :header-cell-style="{ textAlign: 'center', background: '#f5f7fa' }"
                            :cell-style="{ textAlign: 'center' }">
                            <el-table-column prop="name" label="设备" width="180" />
                            <el-table-column prop="ratedCapacity" label="额定制冷量 (kW)" min-width="200" />
                            <el-table-column prop="cop" label="COP" min-width="200" />
                            <el-table-column prop="count" label="台数" min-width="200" />
                        </el-table>

                        <!-- 冷冻泵 -->
                        <div class="sub-title">冷冻泵</div>
                        <el-table :data="pumpChwTableData" border size="small" style="width: 100%; margin-bottom: 16px;"
                            :header-cell-style="{ textAlign: 'center', background: '#f5f7fa' }"
                            :cell-style="{ textAlign: 'center' }">
                            <el-table-column prop="name" label="设备" width="180" />
                            <el-table-column prop="head" label="设计扬程 (mH2O)" min-width="200" />
                            <el-table-column prop="flow" label="设计流量 (L/s)" min-width="200" />
                            <el-table-column prop="count" label="台数" min-width="200" />
                        </el-table>

                        <!-- 冷却泵 -->
                        <div class="sub-title">冷却泵</div>
                        <el-table :data="pumpCwTableData" border size="small" style="width: 100%; margin-bottom: 16px;"
                            :header-cell-style="{ textAlign: 'center', background: '#f5f7fa' }"
                            :cell-style="{ textAlign: 'center' }">
                            <el-table-column prop="name" label="设备" width="180" />
                            <el-table-column prop="head" label="设计扬程 (mH2O)" min-width="200" />
                            <el-table-column prop="flow" label="设计流量 (L/s)" min-width="200" />
                            <el-table-column prop="count" label="台数" min-width="200" />
                        </el-table>

                        <!-- 冷却塔 -->
                        <div class="sub-title">冷却塔</div>
                        <el-table :data="towerTableData" border size="small" style="width: 100%; margin-bottom: 16px;"
                            :header-cell-style="{ textAlign: 'center', background: '#f5f7fa' }"
                            :cell-style="{ textAlign: 'center' }">
                            <el-table-column prop="name" label="设备" width="180" />
                            <el-table-column prop="flow" label="设计水流量 (L/s)" min-width="150" />
                            <el-table-column prop="power" label="风机功率 (kW)" min-width="150" />
                            <el-table-column prop="pressure" label="水压降 (mH2O)" min-width="150" />
                            <el-table-column prop="count" label="台数" min-width="150" />
                        </el-table>

                        <!-- ===== 3. 群控参数 ===== -->
                        <el-divider content-position="left">群控参数</el-divider>
                        <el-descriptions :column="3" border size="small" style="width: 100%;">
                            <el-descriptions-item label="冷冻供水温度设定值">{{ controlForm.ts_chw_set }}
                                °C</el-descriptions-item>
                            <el-descriptions-item label="冷冻供回水温差设定值">{{ controlForm.delta_t_chw }}
                                °C</el-descriptions-item>
                            <el-descriptions-item label="冷却供回水温差设定值">{{ controlForm.delta_t_cw }}
                                °C</el-descriptions-item>
                            <el-descriptions-item label="冷机加机负荷率设定值">{{ controlForm.load_up }}</el-descriptions-item>
                            <el-descriptions-item label="冷却塔逼近度设定值">{{ controlForm.approach_set }}
                                °C</el-descriptions-item>
                            <el-descriptions-item label=""></el-descriptions-item>
                        </el-descriptions>

                    </div>
                </div>

                <div class="action-buttons">
                    <el-button @click="prevStep">
                        <el-icon>
                            <ArrowLeft />
                        </el-icon> 上一步
                    </el-button>
                    <el-button type="primary" size="large" @click="startSimulation" :loading="simulating"
                        :disabled="!canStartSimulation">
                        <el-icon>
                            <VideoPlay />
                        </el-icon>
                        {{ simulating ? '仿真启动中...' : '启动仿真' }}
                    </el-button>
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, ArrowLeft, VideoPlay, CircleCheck } from '@element-plus/icons-vue'
import DataUploader from '@/components/data/DataUploader.vue'
import { startSimulation as startSimulationAPI } from '@/api/simulation'

const router = useRouter()

// ===== 状态 =====
const activeStep = ref(0)
const activeTab = ref('equipment')
const simulating = ref(false)
const parsedData = ref<any>(null)
const dataConfirmed = ref(false)

// ===== 项目表单 =====
const projectForm = reactive({
    name: '',
    buildingType: '',
    area: 10000
})

// ===== 设备选型参数 =====
const equipmentForm = reactive({
    // 建筑负荷
    load_building_r: 196572.0,
    load_coe: 0.001,          // 量纲换算 W -> kW（口径 v1）

    // 冷机参数（默认值 ÷26.58 重标定，见 docs/data-contract.md）
    Qr_chiller_BCH: 79.4808,
    n_design_BCH: 3,
    COP_chiller_BCH: 5.5,     // 仅展示：标称值 vs 模型值校核
    Qr_chiller_SCH: 39.7404,
    n_design_SCH: 1,
    COP_chiller_SCH: 5.0,     // 仅展示
    ts_chw_design: 7.0,
    tr_chw_design: 12.0,
    tr_cw_design: 30.0,
    ts_cw_design: 35.0,

    // 冷冻泵参数
    Gr_pump_chw_BCH: 3.7961,
    Hr_pump_chw_BCH: 32.0,
    n_pump_chw_BCH: 3,
    Gr_pump_chw_SCH: 1.9007,
    Hr_pump_chw_SCH: 32.0,
    n_pump_chw_SCH: 1,

    // 冷却泵参数
    Gr_pump_cw_BCH: 4.7442,
    Hr_pump_cw_BCH: 30.0,
    n_pump_cw_BCH: 3,
    Gr_pump_cw_SCH: 2.4078,
    Hr_pump_cw_SCH: 30.0,
    n_pump_cw_SCH: 1,

    // 冷却塔参数
    Gr_tower_BCH: 7.5245,
    Pr_tower_BCH: 0.8277,     // 仅展示
    Hs_tower_BCH: 4.0,
    n_tower_BCH: 3,
    Gr_tower_SCH: 3.7622,
    Pr_tower_SCH: 0.4515,     // 仅展示
    Hs_tower_SCH: 3.8,
    n_tower_SCH: 1,

    // 管道压降
    Hr_pt: 20.0,
    Hr_chiller_chw_BCH: 6.0,
    Hr_chiller_cw_BCH: 7.0,
    Hr_chiller_chw_SCH: 5.0,
    Hr_chiller_cw_SCH: 6.0
})

// ===== 群控控制参数 =====
const controlForm = reactive({
    // 温度控制
    ta_dry_r: 31.7,
    ta_wet_r: 23.47,
    ts_chw_set: 7.0,
    delta_t_chw: 5.0,
    delta_t_cw: 5.0,
    tr_cw_min: 20.0,
    approach_set: 3.0,

    // 负荷控制
    load_up: 0.9,
    load_min: 0.3,

    // 冷机加机优先级
    Qr_list_str: '39.7404, 79.4808',
    n_design_list_str: '1, 3',

    // 频率控制
    freq_pump_max: 50.0,
    freq_pump_min: 30.0,
    freq_tower_max: 50.0,
    freq_tower_min: 25.0
})

// ===== 计算属性 =====
const canProceed = computed(() => {
    return !!projectForm.name &&
        !!projectForm.buildingType &&
        dataConfirmed.value === true &&
        parsedData.value !== null &&
        parsedData.value?.data?.length > 0
})

const canStartSimulation = computed(() => {
    return !simulating.value && parsedData.value !== null
})

// ===== 单位面积冷负荷 (W/m²) =====
const unitLoad = computed(() => {
    if (!projectForm.area || projectForm.area <= 0) return 0
    return ((equipmentForm.load_building_r / projectForm.area) * 1000).toFixed(2)
})

// ===== 冷机表格数据 =====
const chillerTableData = computed(() => [
    {
        name: '大冷机',
        ratedCapacity: equipmentForm.Qr_chiller_BCH,
        cop: equipmentForm.COP_chiller_BCH,
        count: equipmentForm.n_design_BCH
    },
    {
        name: '小冷机',
        ratedCapacity: equipmentForm.Qr_chiller_SCH,
        cop: equipmentForm.COP_chiller_SCH,
        count: equipmentForm.n_design_SCH
    }
])

// ===== 冷冻泵表格数据 =====
const pumpChwTableData = computed(() => [
    {
        name: '大冷冻泵',
        head: equipmentForm.Hr_pump_chw_BCH,
        flow: equipmentForm.Gr_pump_chw_BCH,
        count: equipmentForm.n_pump_chw_BCH
    },
    {
        name: '小冷冻泵',
        head: equipmentForm.Hr_pump_chw_SCH,
        flow: equipmentForm.Gr_pump_chw_SCH,
        count: equipmentForm.n_pump_chw_SCH
    }
])

// ===== 冷却泵表格数据 =====
const pumpCwTableData = computed(() => [
    {
        name: '大冷却泵',
        head: equipmentForm.Hr_pump_cw_BCH,
        flow: equipmentForm.Gr_pump_cw_BCH,
        count: equipmentForm.n_pump_cw_BCH
    },
    {
        name: '小冷却泵',
        head: equipmentForm.Hr_pump_cw_SCH,
        flow: equipmentForm.Gr_pump_cw_SCH,
        count: equipmentForm.n_pump_cw_SCH
    }
])

// ===== 冷却塔表格数据 =====
const towerTableData = computed(() => [
    {
        name: '大冷却塔',
        flow: equipmentForm.Gr_tower_BCH,
        power: equipmentForm.Pr_tower_BCH,
        pressure: equipmentForm.Hs_tower_BCH,
        count: equipmentForm.n_tower_BCH
    },
    {
        name: '小冷却塔',
        flow: equipmentForm.Gr_tower_SCH,
        power: equipmentForm.Pr_tower_SCH,
        pressure: equipmentForm.Hs_tower_SCH,
        count: equipmentForm.n_tower_SCH
    }
])

// ===== 监听：冷机冷冻水供水温度变化时，同步更新群控参数 =====
watch(() => equipmentForm.ts_chw_design, (newVal) => {
    if (newVal !== undefined && newVal !== null) {
        controlForm.ts_chw_set = newVal
        console.log('🔄 同步冷冻水供水温度:', newVal)
    }
})

// ===== 数据确认处理 =====
const handleDataConfirmed = (data: any) => {
    console.log('📦 DataUploader 确认数据回调:', data)

    if (!data || !data.data || data.data.length === 0) {
        ElMessage.error('数据无效，请重新上传')
        return
    }

    parsedData.value = data
    dataConfirmed.value = true

    ElMessage.success(`数据确认完成，共 ${data.data.length} 行，${data.headers.length} 列`)
}

// ===== 下一步 =====
const nextStep = () => {
    if (activeStep.value === 0) {
        if (!projectForm.name) {
            ElMessage.warning('请输入项目名称')
            return
        }
        if (!projectForm.buildingType) {
            ElMessage.warning('请选择建筑类型')
            return
        }
        if (!dataConfirmed.value) {
            ElMessage.warning('请先上传并确认数据文件')
            return
        }
    }
    activeStep.value++
}

const prevStep = () => {
    activeStep.value--
}

// ===== 启动仿真 =====
const startSimulation = async () => {
    if (!parsedData.value) {
        ElMessage.warning('请先上传数据')
        return
    }

    try {
        await ElMessageBox.confirm(
            '确认启动仿真计算？这可能需要一些时间。',
            '确认启动',
            {
                confirmButtonText: '确认启动',
                cancelButtonText: '取消',
                type: 'info'
            }
        )
    } catch {
        return
    }

    // ===== 台数一致性校验（equipment-config：泵/塔可用台数不得少于同时投运的冷机台数）=====
    const consistencyErrors: string[] = []
    const pairs: Array<[string, number, number]> = [
        ['大机冷冻泵台数', equipmentForm.n_pump_chw_BCH, equipmentForm.n_design_BCH],
        ['小机冷冻泵台数', equipmentForm.n_pump_chw_SCH, equipmentForm.n_design_SCH],
        ['大机冷却泵台数', equipmentForm.n_pump_cw_BCH, equipmentForm.n_design_BCH],
        ['小机冷却泵台数', equipmentForm.n_pump_cw_SCH, equipmentForm.n_design_SCH],
        ['大机冷却塔台数', equipmentForm.n_tower_BCH, equipmentForm.n_design_BCH],
        ['小机冷却塔台数', equipmentForm.n_tower_SCH, equipmentForm.n_design_SCH],
    ]
    for (const [label, deviceCount, chillerCount] of pairs) {
        if (Number(deviceCount) < Number(chillerCount)) {
            consistencyErrors.push(`${label}(${deviceCount}) 少于对应冷机台数(${chillerCount})`)
        }
    }
    if (consistencyErrors.length > 0) {
        ElMessage.error('台数配置不一致：' + consistencyErrors.join('；'))
        return
    }

    simulating.value = true

    try {
        // 解析 Qr_list 和 n_design_list
        const Qr_list = controlForm.Qr_list_str
            .split(',')
            .map(s => parseFloat(s.trim()))
            .filter(n => !isNaN(n))

        const n_design_list = controlForm.n_design_list_str
            .split(',')
            .map(s => parseInt(s.trim()))
            .filter(n => !isNaN(n))

        // ===== 构建完整配置 =====
        const config = {
            // 设备选型参数
            load_building_r: equipmentForm.load_building_r,
            load_coe: equipmentForm.load_coe,

            // 冷机参数
            Qr_chiller_BCH: equipmentForm.Qr_chiller_BCH,
            n_design_BCH: equipmentForm.n_design_BCH,
            COP_chiller_BCH: equipmentForm.COP_chiller_BCH,
            Qr_chiller_SCH: equipmentForm.Qr_chiller_SCH,
            n_design_SCH: equipmentForm.n_design_SCH,
            COP_chiller_SCH: equipmentForm.COP_chiller_SCH,
            ts_chw_design: equipmentForm.ts_chw_design,
            tr_chw_design: equipmentForm.tr_chw_design,
            tr_cw_design: equipmentForm.tr_cw_design,
            ts_cw_design: equipmentForm.ts_cw_design,

            // 冷冻泵参数
            Gr_pump_chw_BCH: equipmentForm.Gr_pump_chw_BCH,
            Hr_pump_chw_BCH: equipmentForm.Hr_pump_chw_BCH,
            n_pump_chw_BCH: equipmentForm.n_pump_chw_BCH,
            Gr_pump_chw_SCH: equipmentForm.Gr_pump_chw_SCH,
            Hr_pump_chw_SCH: equipmentForm.Hr_pump_chw_SCH,
            n_pump_chw_SCH: equipmentForm.n_pump_chw_SCH,

            // 冷却泵参数
            Gr_pump_cw_BCH: equipmentForm.Gr_pump_cw_BCH,
            Hr_pump_cw_BCH: equipmentForm.Hr_pump_cw_BCH,
            n_pump_cw_BCH: equipmentForm.n_pump_cw_BCH,
            Gr_pump_cw_SCH: equipmentForm.Gr_pump_cw_SCH,
            Hr_pump_cw_SCH: equipmentForm.Hr_pump_cw_SCH,
            n_pump_cw_SCH: equipmentForm.n_pump_cw_SCH,

            // 冷却塔参数
            Gr_tower_BCH: equipmentForm.Gr_tower_BCH,
            Pr_tower_BCH: equipmentForm.Pr_tower_BCH,
            Hs_tower_BCH: equipmentForm.Hs_tower_BCH,
            n_tower_BCH: equipmentForm.n_tower_BCH,
            Gr_tower_SCH: equipmentForm.Gr_tower_SCH,
            Pr_tower_SCH: equipmentForm.Pr_tower_SCH,
            Hs_tower_SCH: equipmentForm.Hs_tower_SCH,
            n_tower_SCH: equipmentForm.n_tower_SCH,

            // 管道压降
            Hr_pt: equipmentForm.Hr_pt,
            Hr_chiller_chw_BCH: equipmentForm.Hr_chiller_chw_BCH,
            Hr_chiller_cw_BCH: equipmentForm.Hr_chiller_cw_BCH,
            Hr_chiller_chw_SCH: equipmentForm.Hr_chiller_chw_SCH,
            Hr_chiller_cw_SCH: equipmentForm.Hr_chiller_cw_SCH,

            // 群控控制参数
            ta_dry_r: controlForm.ta_dry_r,
            ta_wet_r: controlForm.ta_wet_r,
            ts_chw_set: controlForm.ts_chw_set,
            delta_t_chw: controlForm.delta_t_chw,
            delta_t_cw: controlForm.delta_t_cw,
            tr_cw_min: controlForm.tr_cw_min,
            approach_set: controlForm.approach_set,
            load_up: controlForm.load_up,
            load_min: controlForm.load_min,
            Qr_list: Qr_list,
            n_design_list: n_design_list,
            // 模型适用范围（D11）：本期由用户配置，报告须声明其非真实训练域
            applicable_range: {
                t_dry_min: -20, t_dry_max: 40, d_min: 0, d_max: 0.03
            },
            freq_pump_max: controlForm.freq_pump_max,
            freq_pump_min: controlForm.freq_pump_min,
            freq_tower_max: controlForm.freq_tower_max,
            freq_tower_min: controlForm.freq_tower_min
        }

        // ===== 构建项目数据 =====
        const projectData = {
            projectName: projectForm.name,
            buildingType: projectForm.buildingType,
            area: projectForm.area,
            config: config,
            data: {
                headers: parsedData.value.headers,
                rows: parsedData.value.data
            },
            // 数据溯源（4.3）：随请求上报，写入结果 meta
            dataMeta: {
                fileName: parsedData.value.fileName || 'uploaded.csv',
                totalRows: parsedData.value.data.length,
                confirmedRange: `${parsedData.value.data[0]?.[parsedData.value.headers[0]] || ''} ~ ${parsedData.value.data[parsedData.value.data.length - 1]?.[parsedData.value.headers[0]] || ''}`,
                correctedOutliers: parsedData.value.correctedOutliers || 0
            }
        }

        // 保存到 sessionStorage
        sessionStorage.setItem('currentProjectData', JSON.stringify(projectData))
        console.log('📦 项目数据已保存到 sessionStorage')

        // 调用 API
        const response = await startSimulationAPI(projectData)

        simulating.value = false
        ElMessage.success(`仿真任务已启动！任务ID: ${response.taskId}`)

        router.push(`/simulation/${response.taskId}`)

    } catch (error: any) {
        simulating.value = false
        const errorMsg = error.response?.data?.detail || error.message || '启动仿真失败，请检查后端服务'
        ElMessage.error(errorMsg)
        console.error('启动仿真错误:', error)
    }
}

// ===== 辅助方法 =====
const getBuildingTypeLabel = (type: string) => {
    const map: Record<string, string> = {
        office: '办公建筑',
        commercial: '商业建筑',
        residential: '住宅建筑',
        hospital: '医院建筑',
        industrial: '工业建筑'
    }
    return map[type] || type
}
</script>

<style scoped>
.project-new {
    padding: 0;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.card-header span {
    font-size: 16px;
    font-weight: 600;
}

.step-content {
    padding: 20px 0;
    min-height: 500px;
    width: 100%;
}

.config-form {
    max-height: 600px;
    overflow-y: auto;
    padding-right: 10px;
    width: 100%;
}

.step-actions {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 30px;
}

/* ===== 配置确认容器 ===== */
.config-confirm-container {
    width: 100%;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    background: #f0f9eb;
    padding: 20px;
    box-sizing: border-box;
}

.config-confirm-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: #67C23A;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #e1f3d8;
}

/* ===== 配置汇总 ===== */
.config-summary {
    width: 100%;
    max-height: 600px;
    overflow-y: auto;
    padding-right: 10px;
    box-sizing: border-box;
}

/* 确保 el-descriptions 占满宽度 */
.config-summary :deep(.el-descriptions) {
    width: 100%;
}

/* 确保 el-table 占满宽度 */
.config-summary :deep(.el-table) {
    width: 100% !important;
    font-size: 13px;
}

/* el-divider 占满宽度 */
.config-summary :deep(.el-divider) {
    width: 100%;
}

/* 标签和内容样式 */
.config-summary :deep(.el-descriptions__label) {
    min-width: 140px;
    white-space: nowrap;
}

.config-summary :deep(.el-descriptions__content) {
    word-break: break-all;
}

.sub-title {
    font-weight: 500;
    font-size: 14px;
    color: #606266;
    margin: 12px 0 8px 0;
    padding-left: 8px;
    border-left: 3px solid #409EFF;
}

.action-buttons {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 30px;
}

:deep(.el-upload-dragger) {
    width: 100%;
    padding: 30px 20px;
}

:deep(.el-upload-dragger .el-icon--upload) {
    font-size: 48px;
    color: #409EFF;
}

:deep(.el-form-item) {
    margin-bottom: 18px;
}

:deep(.el-divider) {
    margin: 20px 0 16px 0;
}

:deep(.el-tabs__content) {
    padding: 20px;
}

/* 表格样式优化 */
.config-summary :deep(.el-table th) {
    background-color: #f5f7fa;
    font-weight: 500;
}

/* 滚动条美化 */
.config-form::-webkit-scrollbar,
.config-summary::-webkit-scrollbar {
    width: 6px;
}

.config-form::-webkit-scrollbar-track,
.config-summary::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
}

.config-form::-webkit-scrollbar-thumb,
.config-summary::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;
}

.config-form::-webkit-scrollbar-thumb:hover,
.config-summary::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
}

/* ===== 表格样式统一 ===== */
.config-summary :deep(.el-table) {
    width: 100% !important;
    font-size: 13px;
}

.config-summary :deep(.el-table th) {
    background-color: #f5f7fa !important;
    font-weight: 500;
    text-align: center;
    padding: 10px 0;
}

.config-summary :deep(.el-table td) {
    text-align: center;
    padding: 8px 0;
}

.config-summary :deep(.el-table .cell) {
    text-align: center;
    word-break: keep-all;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* 表格头部和单元格对齐 */
.config-summary :deep(.el-table__header-wrapper th .cell) {
    text-align: center;
}

.config-summary :deep(.el-table__body-wrapper td .cell) {
    text-align: center;
}

@media (max-width: 768px) {
    .step-content {
        min-height: 300px;
    }

    .step-actions,
    .action-buttons {
        flex-direction: column;
        align-items: center;
    }

    .config-form,
    .config-summary {
        max-height: none;
    }
}
</style>