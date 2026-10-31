# Design

## Context

动机见 `proposal.md`，行为契约见 `specs/simulation-report/spec.md` 与 `specs/simulation-result/spec.md`（MODIFIED）。本文只记录实现层的约束与取舍。

**当前状态**

- 报告能力为空：`api/routes/reports.py` 返回固定常量，`services/report_service.py` 是 0 字节文件，界面三个按钮只弹提示。
- **仿真结果无持久化**：任务与结果驻留 `simulation_service.tasks` 内存字典，进程重启即失。这一条直接决定报告的存储方案。
- 上游契约已归档：`openspec/specs/simulation-result`（七区块 + `unmet_hours_detail`）、`data-ingestion`、`equipment-config`。
- 唯一已知缺口：`load_rate_histogram` 由引擎计算但未随接口返回，本 change 补（见 MODIFIED delta）。

**约束**

- 后端环境 `github_HVAC`（Python 3.12 + fastapi 0.115 + torch 2.7.1）的实测：`weasyprint` 导入即抛 `OSError`（缺系统级依赖，不可用）；`reportlab` 4.2.2 与 `jinja2` 3.1.6 可用；`matplotlib` 缺失。
- 前端已有 ECharts，但 ECharts 是浏览器端库，服务端无法直接出图。
- 报告要交付给甲方并留档，因此"可重复下载且内容一致"是硬要求（见 spec 的三条相关需求）。

## Goals / Non-Goals

**Goals**

- 报告数据在生成时**冻结**，与生成后仿真任务是否还在内存无关
- 同一报告多次下载字节一致（不依赖浏览器重绘的结果）
- 零新增运行时依赖

**Non-Goals**

- 服务端渲染 PDF（不做）
- 报告页面与监控页视觉一致（不追求）
- 报告的在线编辑、批注、多模板

## Decisions

### D1 生成与渲染分离：后端只产出「自包含 HTML 快照」

**决策**：`POST /api/reports/generate/{task_id}` 在后端一次性生成一个**自包含的 HTML 文件**（内嵌样式与 SVG 图表，无外部请求、无 JavaScript），落盘存档；`GET /api/reports/download/{report_id}` 原样返回该文件。

**理由**：spec 要求"重复下载的内容完全相同"，只有服务端产出固定文件才能满足。若由前端 ECharts 重新绘制再打印，两次打印的分页与字体渲染都会不同，无法承诺一致。

**替代方案**：

- 服务端 weasyprint 出 PDF：否决。该库在本机导入即失败（OSError），且中文字体仍需额外配置。
- 服务端 reportlab 出 PDF：可行但否决。reportlab 可用（含中文 CID 字体），但报告版面与图表都要用画布指令逐个摆放——三张图要手写坐标，改一次版式就重排一次，而 HTML + SVG 用声明式布局表达同样的内容，改版成本低一个量级。留作后续若要"服务端直接产出 PDF 文件"时的路线。
- 前端渲染 + 浏览器打印：否决。无法满足字节一致。
- 让前端直接读 `/results` 自行组装：否决。章节口径会漂移到前端，spec 的"报告数据仅来自结果契约"无法在服务端校验。

### D2 目录即索引，不引入数据库

**决策**：每条报告一个目录：

```
data/reports/<report_id>/
├── report.html      # 自包含报告（字节稳定）
├── result.json      # 生成时的七区块结果快照
└── meta.json        # 任务标识、生成时间、口径版本、碳排因子、章节清单
```

**理由**：项目当前无持久化层，为报告引入数据库是过度设计；目录天然满足"稳定标识 + 重启后可取回"，且便于人工归档与拷贝。

**替代方案**：SQLite（需引入 ORM 与迁移）；复用内存任务字典（重启即失，违反 spec）。

### D3 图表用服务端生成的 SVG，不用 ECharts

**决策**：报告内三张图为服务端用字符串模板生成的 SVG：月度能耗柱状图、月度能效折线图、能耗构成堆叠条。

**理由**：SVG 是文本，写入 HTML 后字节稳定；浏览器打印与另存 PDF 时不需要执行 JS，最可靠；无需内嵌 ~1MB 的 echarts。

**替代方案**：内嵌 echarts.min.js（文件膨胀且依赖 JS 执行）、Canvas 截图（需浏览器）。

### D4 生成前置校验：缺关键字段直接失败

**决策**：生成前校验 `meta.projectName` / `meta.area` / `meta.carbonFactor.value` / `meta.caliberVersion` / `summary` / `breakdown` 是否就绪；缺失即返回失败并指名字段，**不写任何文件**。

**理由**：对应 spec 的两条要求——"参数与快照不符时生成失败" 与 "失败不留半成品"。

### D5 原子写入，避免半成品

**决策**：先写 `<report_id>.tmp/` 目录，三份文件全部写成功后再 `rename` 为正式目录；任一步失败则删除临时目录。

**理由**：目录一旦可见就代表报告可用，杜绝"有下载链接但文件不全"。

### D6 report_id 独立于 task_id，一个任务可有多份历史报告

**决策**：`report_id = <task_id 前 8 位>-<生成时间戳 YYYYMMDDHHMMSS>`。

**理由**：同一方案可能在不同口径或不同章节细节下重复出报告，历史版本应并存；同时保留与任务的绑定关系，满足 spec 的"报告与仿真结果及口径版本绑定"。

**替代方案**：一任务一报告、覆盖写。否决：无法追溯上一版。

### D7 「内容一致」的边界写清楚

**决策**：spec 中的"各次下载内容完全相同"由 **下载文件的字节一致** 保证（同一 `report.html`）。用户"打印为 PDF"是浏览器行为，两次打印的 PDF 字节不承诺一致（分页可能随打印驱动变化）。

**理由**：这是唯一诚实的口径。若不写清，验收时会拿两份 PDF 比对字节而失败。

### D8 负荷率分布的落地位置

**决策**：`GET /api/simulate/results/{task_id}` 响应新增顶层字段 `load_rate_histogram: List[int]`（长度 10），与 `summary`、`breakdown` 同级；不改动 `operating_stats`（仍为"设备类型 → 投运小时数"）。

**理由**：`operating_stats` 是 `Dict[str, int]`，混入数组会破坏其类型语义；顶层新增字段与 `unmet_hours_detail` 的做法一致。

**替代方案**：塞进 `operating_stats.loadRateHistogram`。否决：类型不一致，前端消费易出错。

## Risks / Trade-offs

- [报告与监控页视觉不一致] 监控页用 ECharts 交互图，报告用静态 SVG → 缓解：报告以可打印为目标，在 meta 中记录图表类型，不承诺与屏幕一致。
- [结果仍无持久化] 报告目录冻结了结果快照，但**未生成报告的任务重启后仍丢失结果** → 缓解：文档明示；后续可单开 change 做结果归档。
- [HTML 体积] 8760 点若直接画折线会很大 → 缓解：图表只用月度（12 点）与年度构成，不用逐时序列；逐时明细只出现在缺口清单（通常个位数）。
- [中文字体] 服务端不渲染 PDF，字体由浏览器提供 → 缓解：CSS 指定常见中文字体族，不内嵌字体。
- [并发生成同一任务] 两个请求同时生成 → 缓解：report_id 含秒级时间戳且写入用临时目录 + 原子 rename，冲突时后写者失败并提示重试。
- [报表目录无限增长] 无自动清理 → 缓解：文档说明由运维定期归档；不引入自动删除（避免误删交付物）。

## Migration Plan

无数据库、无 schema 迁移。

1. 先补 `load_rate_histogram`（D8）：schemas → 路由 → 前端类型，验证响应含该字段
2. 新增报告服务与端点（D1–D5）
3. 新增前端报告页与打印样式，报告入口由三个收敛为一个
4. 首次运行会创建 `data/reports/`；该目录应加入 `.gitignore`
5. 回滚：删除 `data/reports/` 并回退代码，无残留状态

## Open Questions

- **报告的下载权限范围**：当前沿用 JWT，仅任务所属用户可下载。若后续需要把报告发给甲方（外部分享链接），需要单独的签名链接机制——那属于新增能力，不影响本期设计。
