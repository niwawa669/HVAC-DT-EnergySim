# 提案：项目可见性、新建项目表单与雷达图评价口径

## Why

最近三处使用问题已经能在界面上直接观察到：

1. **仿真完成后找不到项目**：仪表板与项目列表曾使用写死的演示数据；后端启动仿真时也不创建项目记录（`project_id` 为空），所以"完成一个项目"在列表里没有任何可查对象。
2. **新建项目表单口径不一致**：项目名称/建筑类型/面积没有业务默认值；建筑负荷与冷机容量放大系数没有必填校验；上传拖拽区被 Element Plus 固定为 360px，与其他输入框右端对不齐。
3. **雷达图看不出好坏**：五个维度直接按原始数值绘制，量纲不同导致半径没有可比性；且标签曾统一取第一个维度（五个都显示 5.0）；"全年平均负荷率"用的是按 8760 h 的容量因子，不是冷机实际在线时的负荷率。

本次把这三块统一收口，并新增"全年冷机平均负荷率"结果字段。

## What Changes

- **项目生命周期**
  - 启动仿真未传 `projectId` 时，按（用户, 项目名）自动创建/复用项目，并把任务挂到项目上
  - 任务状态（pending/running/completed/failed/cancelled、重启中断）同步到项目状态
  - 项目列表/详情返回最近一次任务与结果摘要（总耗电量、EUI、碳排、峰值负荷等）
  - 历史任务的项目关联改为结构升级时一次性回填（migration v2），不再随每次启动执行：删除掉的项目不会因重启而复活
  - 删除项目只解除任务关联，仿真任务、结果与报告保留
- **新建项目表单**
  - 默认值：项目名"测试项目"、建筑类型"办公建筑"、面积 100000 m²；建筑负荷 0、容量放大系数 1.0；大小机/泵/塔台数均为 1；大/小冷却塔设计功率 22 / 12 kW；冷却泵设计扬程 30 mH₂O
  - 必填：项目名称、建筑类型、面积、建筑负荷、冷机容量放大系数；面积/负荷/系数必须 > 0
  - 上传区与输入框统一占满内容宽度，右端与项目名称输入框对齐
- **雷达图评价**
  - 五维统一折算为 0–100 分，点位越靠外越好；增加 60 分达标参考线
  - 评价基准引用 GB 50189-2015、GB 55015-2021、GB 19577-2024、GB/T 51161-2016、GB/T 51366-2019；单位面积指标按冷源站约 35% 折算
  - 图下增加明细表（原始值 / 得分 / 等级 / 基准），悬停展示来源
  - "全年平均负荷率"改为"全年冷机平均负荷率"：Σ逐时供冷量 ÷ Σ(在线冷机额定制冷量 × 1h) × 100%
- **结果契约**：`summary` 新增 `avgChillerLoadRate`，随 `GET /api/simulate/results` 返回；旧结果无该字段时界面显示"—（旧结果）"并提示重新仿真

## Capabilities

### New Capabilities

- `project-lifecycle`：仿真启动时项目自动创建/复用、状态同步、列表/详情聚合摘要、历史回填、删除语义与归属隔离。
- `project-setup`：新建项目表单的默认值、必填校验与控件布局一致性。
- `result-evaluation`：五维雷达图的 0–100 归一化评价、评价基准披露、明细展示与旧结果兼容。

### Modified Capabilities

- `simulation-result`：汇总指标新增"全年冷机平均负荷率"及其计算口径。

## 非目标

- **项目不持有参数**：`Project.config` 保持空置，本期不支持"载入上次参数再算一遍"，也不把项目做成可保存的方案容器；参数真相仍只在 `task.config`（提交原值）与 `result.meta.parameters`（生效值）里
- **不引入软删除**：不加 `deleted_at`、`unlinked_at` 或任何"已删除"状态位，删除就是删行
- **不做孤儿结果入口**：删项目后解绑的任务不提供界面列表，只能按任务标识查询接口
- **不调整评价基准**：雷达图的阈值与"冷源站占建筑总量 35%"的折算假设沿用现状，本次只记录其口径
- **不做留存清理策略**：任务、结果、报告何时清理不做，沿用 `persistence-framework` 的 Open Question

## Impact

**后端**
- `repositories/projects.py`、`repositories/tasks.py`、`repositories/results.py`、`api/routes/projects.py`、`api/routes/simulate.py`、`main.py`
- `services/algorithm_wrapper.py`：逐时记录在线容量，年度聚合 `avgChillerLoadRate`
- `models/schemas.py`：响应模型新增字段
- `db/migrations/v2_backfill_project_links.py`（新增）：一次性回填历史任务的项目关联；`main.py` 启动序列不再调用回填

**前端**
- `views/Dashboard.vue`、`views/Projects.vue`、`views/ProjectNew.vue`、`views/SimulationView.vue`、`components/data/DataUploader.vue`
- `api/projects.ts`、`api/users.ts`（无）、`utils/projectDisplay.ts`、`utils/radarMetrics.ts`、`router/index.ts`、`components/layout/AppLayout.vue`
- 说明：账户管理相关改动已由 `account-management` change 归档，不在本次范围内

**文档与验证**
- `docs/radar-benchmark.md`、README、`scripts/verify_persistence.py`
- 新增一条数据迁移（v2：一次性回填历史任务的项目关联）；无表结构变更，项目/结果字段沿用现有表与 JSON
