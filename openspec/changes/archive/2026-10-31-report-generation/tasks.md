# Tasks

> 决策依据见 `design.md`，行为契约见 `specs/simulation-report/spec.md` 与 `specs/simulation-result/spec.md`（MODIFIED）。
> 项目无自动化测试框架，验证方式统一采用「可观察行为 + 可复现命令」。后端验证使用 `github_HVAC` 环境（Python 3.12，已装 fastapi）；前端类型检查用 `npx vue-tsc --noEmit -p tsconfig.app.json`。

## 1. 补齐负荷率分布字段（D8，阻塞第 2/3 组）

- [x] 1.1 在结果顶层新增 `load_rate_histogram: List[int]`，并由 `simulate.py` 从 `summary["loadRateHistogram"]` 映射；验证：`GET /api/simulate/results/{task_id}` 响应含该字段，长度恒为 10，且**各元素之和等于"任一冷机运行的逐时记录数"**（注意：不可与 `operating_stats` 求和直接比较——后者按设备类型分别计数，双机同开的时段会被重复计入）
- [x] 1.2 无投运场景下返回 10 个 0 而非缺失；验证：以构造的全零负荷序列运行（冬季真实数据仍会有高于启动阈值的时段，不能用来验证本条），响应中该字段存在、长度为 10 且全为 0
- [x] 1.3 同步前端类型 `api/simulation.ts`；验证：`npx vue-tsc --noEmit -p tsconfig.app.json` 零错误

## 2. 报告数据组装与前置校验（D4）

- [x] 2.1 定义报告视图模型：把七区块与 `unmet_hours_detail`、`load_rate_histogram` 映射为 7 章所需的结构化对象（不在此处做任何结果之外的统计，仅做取字段与排版所需的分组）；验证：以一次真实仿真结果构造，7 章所需字段全部非空，且每个字段都能在结果 JSON 中定位到来源键
- [x] 2.2 实现前置校验：`meta.projectName` / `meta.area` / `meta.carbonFactor.value` / `meta.caliberVersion` / `summary` / `breakdown` 任一缺失即失败并指名字段；验证：构造逐项缺失的样本，每次均返回失败且错误信息含具体字段名
- [x] 2.3 校验报告参数快照与结果快照逐项一致，不一致即失败；验证：手工篡改视图模型中的一项参数，生成立即失败并报出该参数

## 3. 服务端 SVG 图表（D3）

- [x] 3.1 月度能耗柱状图：以 `monthly` 的 `totalEnergyConsumption` 为纵值；验证：输出为合法 SVG 片段，柱数等于 `monthly` 条数，文本中不含 `<script>`
- [x] 3.2 月度能效折线图：以 `monthly` 的 `systemEER` 为纵值；验证：折线点数等于 `monthly` 条数，缺失值为 0 的月份仍占一个点
- [x] 3.3 能耗构成堆叠条：以 `breakdown` 四分项绘制，标注占比；验证：四段之和与 `summary.totalEnergy` 一致（容差 1e-6），占比标注合计 100%
- [x] 3.4 三张图在只有 1 个月数据时不产生除零或非法坐标；验证：以单月数据构造视图模型，SVG 中不出现 NaN 或 Infinity

## 4. HTML 快照渲染与原子落盘（D1/D2/D5）

- [x] 4.1 渲染自包含 HTML：7 章齐全、内嵌样式与 SVG、`@page { size: A4 }` 分页样式、表格跨页重复表头；验证：生成的 HTML 中不含 `http://`/`https://` 外链，不含 `<script>`，且 7 个章节标题按序出现
- [x] 4.2 原子写入：先写 `data/reports/<id>.tmp/`，三份文件齐全后 `rename` 为正式目录，任一步失败删除临时目录；验证：人为让模板渲染抛错，确认 `data/reports/` 下不产生任何新目录
- [x] 4.3 落盘 `result.json`（七区块快照）与 `meta.json`（任务标识、报告标识、生成时间、口径版本、碳排因子、章节清单）；验证：三份文件齐全，`meta.json` 中的口径版本与结果快照一致
- [x] 4.4 `data/reports/` 加入 `.gitignore`；验证：`git status`（或文件检查）不把报告产物列为待提交

## 5. 报告端点与权限（D1/D6）

- [x] 5.1 `POST /api/reports/generate/{task_id}`：仅接受已完成任务，生成并返回 `report_id`；验证：对未完成/失败任务返回 400 并说明原因
- [x] 5.2 `GET /api/reports/{report_id}`：返回 `meta.json` 内容（含章节清单与生成时间）；验证：能列出该任务的全部历史报告（同一任务第二次生成后可见两条）
- [x] 5.3 `GET /api/reports/download/{report_id}`：原样返回 `report.html`，`Content-Type: text/html; charset=utf-8`，文件名含报告标识；验证：连续两次下载的响应体字节完全相同
- [x] 5.4 权限：仅任务所属用户或 `admin` 可生成与下载；验证：用另一账号请求返回 403
- [x] 5.5 下载与查询在服务重启后仍可用（不依赖内存任务字典）；验证：生成报告 → 重启后端 → 直接按 `report_id` 下载成功

## 6. 前端报告入口与页面（spec: 单一标准模板）

> **验证边界**：本机沙箱禁止 esbuild 派生服务进程（`npm run build` 报 `spawn EPERM`），
> 因此"页面渲染 + 打印预览为 A4"无法在此环境自动验证。已完成的替代验证：
> `vue-tsc --noEmit` 零错误（含 SFC 模板类型检查）、路由与组件引用可解析、
> 报告 HTML 自身含 `@page { size: A4 }`（见 4.1），以及下载端点返回的 HTML 可正常取回（见 5.3）。
> **仍需人工确认**：在浏览器中打开 `/report/{reportId}`，检查渲染与打印预览的分页。

- [x] 6.1 新增报告页路由，内嵌 `/api/reports/download/{report_id}` 并暴露「打印 / 另存为 PDF」动作；验证：页面可正常渲染报告且打印预览为 A4 版式
- [x] 6.2 `SimulationView.vue` 的三个报告按钮收敛为一个「生成报告」；验证：页面只出现一个报告入口，且请求携带当前 `taskId`
- [x] 6.3 生成失败时展示后端返回的原因，不提供任何下载链接；验证：对未完成任务点击生成，提示具体原因且无下载按钮
- [x] 6.4 前端类型与调用同步；验证：`npx vue-tsc --noEmit -p tsconfig.app.json` 零错误

## 7. 集成验收

- [x] 7.1 端到端：登录 → 跑一次全年仿真 → 生成报告 → 下载；验证：下载的 HTML 中 7 章齐全，且 `summary` 的六项指标与 `GET /results` 返回的数值逐项一致
- [x] 7.2 一致性：同一 `report_id` 连续下载两次字节相同；重启后端后再次下载仍字节相同
- [x] 7.3 缺章节检查：报告正文中不存在"无数据"占位与被截断的表格；验证：人工核对 7 章，确认每章有实际内容或显式的无内容说明
- [x] 7.4 更新 `README.md`：补报告章节构成、生成与下载用法、以及"内容一致指下载文件字节一致"的口径说明；验证：按文档步骤可复现一次生成与下载

## 8. 展示格式统一（验收反馈追加）

- [x] 8.1 实现展示层格式化：枚举代码值转中文（建筑类型、碳排地理层级）、时间统一为 `YYYY-MM-DD HH:MM:SS`、浮点四舍五入保留两位、系数类（|v|<1 且非零）保留有效小数；验证：报告正文中不含 `BuildingType`/`office`/`provincial`，无 ISO `T` 时间，超过两位小数的数字仅为量纲换算系数、碳排放因子与塔设计功率
- [x] 8.2 格式化只作用于正文，不动快照；验证：`result.json` 中 `meta.loadCoe` 仍为 `0.001`、`startTime` 仍为 ISO 格式、`totalEnergy` 仍为 `26244.1441999574`，`meta.json` 的 `generatedAt` 仍带时区

## Workflow follow-up

- 报告能力落地后，可评估把 `data/reports/` 的清理与归档策略单独立项（当前不做自动删除）。
- 若后续需要"服务端直接产出 PDF 文件"，按 `design.md` D1 记录的 reportlab 路线另开 change。
- 在项目评审确认报告内容可交付后再归档本 change。
