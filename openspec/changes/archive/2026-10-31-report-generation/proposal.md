# 提案：全年冷源站能耗仿真报告（单一标准模板）

## Why

项目验收场景已确定为「工程师算一个方案、出一份报告」，而报告能力目前完全不存在：`/api/reports/*` 端点返回固定常量 `"generating"`，报告服务是空文件，界面上的三个报告按钮只弹一句成功提示。仿真监控页给出的只有屏幕上的数字与曲线，无法交付给甲方，也无法留档。

同时，报告会强制暴露结果契约的缺口：报告要印出的每一项都必须能追溯到结果中的具体字段。把报告章节先钉死，可以反过来裁剪结果契约的范围——只保留报告真正要用的统计量，避免按猜测堆砌。

## What Changes

- **新增报告能力**：一次仿真对应一份可交付的《全年冷源站能耗仿真报告》，固定 7 个章节
- **单一标准模板**：v1 只提供一套标准模板。界面上现有「标准/简化/专家」三个入口收敛为一个，另外两个移除
- **报告内容只取自结果契约**：报告不得引入结果之外的二次计算；确有必要做的聚合必须可由结果字段复算
- **如实反映参数**：选型与群控参数章节输出实际生效的参数快照，并标注"仅展示"类参数
- **披露不确定性与缺口**：报告必须说明仿真周期与实际覆盖小时数、供冷缺口（若有）、以及模型超出设计工况外推的小时数
- **导出与留档**：报告支持打印为 A4/PDF；生成后的报告可通过稳定标识重复下载，不因服务重启而丢失
- **失败不留半成品**：生成失败时不得产出缺章节或含占位值的报告

**明确不在本次范围内**：多方案对比、经济性与碳排经济分析、报告模板分档（简化/专家）、Word/Excel 导出、报告在线批注。

## 报告章节与数据来源

| # | 章节 | 数据来源（结果契约的真实字段） |
|---|---|---|
| 1 | 封面与方案概览 | `meta.projectName` / `meta.buildingType` / `meta.area` / `meta.startTime` / `meta.endTime` / `meta.totalHours`，加报告生成时间与版本 |
| 2 | 输入数据与数据质量 | `meta.fileName` / `meta.totalRows` / `meta.confirmedRange` / `meta.correctedOutliers` / `meta.tDryMin·Max` / `meta.humidMin·Max` / `meta.loadCoe` / `meta.caliberVersion` |
| 3 | 设备选型与群控参数 | `meta.parameters`（生效快照）+ `meta.displayOnly`（仅展示清单）+ `meta.displayOnlyDeviations`（标称 vs 模型偏差） |
| 4 | 全年能耗与能效结果 | `summary`（`totalEnergy` / `totalCoolingLoad` / `totalQStation` / `peakCoolingLoad` / `eui` / `avgCop` / `systemEER` / `carbonEmission`）+ `breakdown`（四分项加和守恒） |
| 5 | 时间维度分析 | `monthly` + `weekly`（均带起止时间与实际小时数、分项能耗；季节分布由 `monthly` 聚合得出） |
| 6 | 运行工况分析 | `operating_stats` + `peak_context` + **负荷率分布**（见下"已知差距"） |
| 7 | 结论与口径说明 | `summary.totalUnmet` / `unmetHours` / `totalUnservedOff`；`meta.carbonFactor`（值/层级/年度/来源）；`meta.extrapolation`（外推小时数、占比、耗电量）；`unmet_hours_detail`（逐时缺口明细） |

### 已知差距（本 change 需一并修复）

`simulation-result` 主 spec 的「运行统计」要求*"结果 SHALL 给出按负荷率区间划分的逐时计数"*，引擎也确实计算了 `loadRateHistogram`，但**该字段未出现在 `GET /api/simulate/results/{task_id}` 的响应中**（`SimulationSummary` 未定义该字段，路由也未映射）。这是归档后才暴露的实现缺口：spec 有要求、引擎有数据、接口没暴露。

因此本 change 把 `simulation-result` 列为 Modified Capability，在「运行统计」中补明该分布须随结果返回、字段名为 `load_rate_histogram`（长度恒为 10，区间 `[i/10, (i+1)/10)`，末区间含 1.0），使第 6 章可如实填写。

## Capabilities

### New Capabilities

- `simulation-report`：全年冷源站能耗仿真报告的内容契约与交付方式——章节构成、数据来源约束、参数与结果的如实表达、不确定性与缺口的披露义务、失败处理，以及打印/下载的可重复获取行为

### Modified Capabilities

- `simulation-result`：修改「运行统计」——按负荷率区间划分的逐时计数须以 `load_rate_histogram` 字段随结果接口返回（当前主 spec 已要求该统计，但接口未暴露）。报告第 6 章依赖它，因此在本 change 内一并补齐，避免为单个字段另开一个 change。对应 delta：`specs/simulation-result/spec.md`（MODIFIED，保留原有 2 个场景并新增 2 个）。

## Impact

**新增/改动的代码**

- `src/main/src/views/` 新增报告视图与路由；`SimulationView.vue` 的报告入口由三个收敛为一个
- `src/apiserver/app/api/routes/reports.py` 由常量桩改为真实端点（生成、查询状态、下载）
- `src/apiserver/app/services/report_service.py` 由空文件实现为报告装配与渲染
- 报告需要可重复下载，因此需要最小的结果与报告归档能力（存储形态在 design 阶段决定）

**对既有能力的依赖（已满足）**

- 报告的全部数据来源由已归档的三份主 spec 定义：`openspec/specs/simulation-result/`、`openspec/specs/data-ingestion/`、`openspec/specs/equipment-config/`
- 提案阶段曾提出"第 7 章需要模型外推小时数"——该要求已在 `simulation-result-contract` 落地，现由 `simulation-result` 的「模型适用范围与外推披露」承担，字段为 `meta.extrapolation`
- 提案阶段曾提出"第 7 章需要可定位的缺口"——同样已落地，字段为 `unmet_hours_detail`
- **唯一残留缺口**是负荷率分布未随接口返回，已列入上面的 Modified Capabilities

**依赖与兼容性**

- 无新增第三方依赖的必要（打印导出可复用浏览器能力；服务端 PDF 渲染留待后续评估）
- 报告端点为新增，不破坏既有接口

## 实施顺序约束

前置条件已满足：`simulation-result-contract` 已归档（36/36 任务完成，三份主 spec 通过 `openspec validate --specs`），报告的数据来源不再变动。

因此本 change 可按本提案直接产出 `design.md` 与 `tasks.md`，无需再次等待。实现顺序上须先补齐负荷率分布字段（Modified Capability），再实现报告渲染——否则第 6 章会缺数据。
