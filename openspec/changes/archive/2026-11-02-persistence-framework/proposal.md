# 提案：把进程内存态改为可迁移、可恢复的关系型持久化框架

## Why

当前后端把业务状态全部放在进程内存里：登录用户是 `fake_users_db`，项目是 `fake_projects`，仿真任务与七区块结果是 `SimulationService.tasks` 字典。由此产生四个已经能观察到的问题：

1. **重启即失联**：服务一旦重启，任务状态、结果、项目全部消失；只有报告还能靠 `data/reports/` 目录"碰巧"读到。用户点击"重新仿真"会得到 404。
2. **输入数据不可复现**：逐时数据只存在任务字典里，进程结束就没有了；报告的 `result.json` 是结果快照，不能反推输入。
3. **并发任务会串结果**：`algorithm_wrapper` 用一组 `self._last_*` 全局字段交付结果，两个任务并行时后完成者的结果可能被先完成者读走，且没有任何报错。
4. **报告无法按用户/任务检索**：目录即索引，只能全目录扫描后逐份读 `meta.json`；索引与产物不一致时没有判定依据。

框架设计文档早已规划 MySQL 关系库与迁移工具，但 `models/database.py` 至今是空文件。本次把这条缺失的链路补齐，并为后续"多用户、可审计、可复现"打好底座。

## What Changes

- **新增持久化层**：SQLAlchemy 2.0 async（默认 SQLite，`DATABASE_URL` 可切 MySQL），统一 engine / session / 事务边界；新增七张表：`users`、`projects`、`datasets`、`simulation_tasks`、`simulation_results`、`reports`、`schema_migrations`
- **版本化迁移**：`schema_migrations` 记录已执行版本，启动时自动升级（可关）；提供 `python -m app.db.migrate` 的 upgrade / status 命令；重复执行幂等
- **仓储层**：用户、项目、数据集、任务、结果、报告各自一个仓储，路由与业务服务不再直接改内存字典
- **任务状态机落库**：状态、进度、配置、数据引用、错误信息写入 `simulation_tasks`；重启时把 `pending/running` 任务标记为失败并写明"服务重启中断"；`completed` 与结果写入同一事务
- **输入数据留存**：逐时数据落 `data/datasets/<dataset_id>.json`，`datasets` 表存文件名、行数、列数、时间列、sha256；任务引用 `dataset_id`，"重新仿真"从文件回读而不是从内存
- **结果持久化**：七区块结果整体存 JSON 文档（SQLite TEXT / MySQL JSON），另存少量派生列供列表查询；同一任务重复读取返回同一份内容
- **报告索引**：报告文件仍是唯一产物，`reports` 表作索引；启动时扫描 `data/reports/` 回填历史报告（现有 11 份可直接被索引），索引与产物不一致时按"产物优先"修复并显式记录
- **消除全局结果串号**：`run_simulation_streaming` 增加结果接收器，结果归属到发起它的任务，不再依赖 `_last_*` 全局字段
- **配置化存储位置**：`DATABASE_URL`、`DB_AUTO_MIGRATE`、`DATA_DIR`、`DATASETS_DIR`、`REPORTS_DIR`；`data/hvac.db*` 与 `data/datasets/` 加入 `.gitignore`
- **BREAKING（业务可见口径）**：项目列表不再返回 3 条内置演示数据，改为真实数据（首次启动为空列表）；默认账户首次启动写入数据库，已有 token 仍可用（沿用 uid=1/2）；`GET /api/simulate/results` 的 `projectId` 改为实际关联项目，未关联时为 `0`

**明确不在范围内**：Redis / Celery 异步队列与任务调度、对象存储（S3/OSS）、多实例部署与连接池调优、鉴权重构（刷新 token、权限体系）、前端改造、既有报告 HTML 模板改动。

## Capabilities

### New Capabilities

- `persistence`：定义业务状态的耐久性、重启恢复、输入数据留存、结果原子提交与幂等读取、报告索引与产物对账、迁移幂等、初始化幂等、并发隔离、存储位置与后端可配置。

### Modified Capabilities

（无。既有 `data-ingestion`、`simulation-result`、`simulation-report` 的既有要求全部继续成立；本次新增的是"留存与恢复"这一组此前未曾声明的新行为，因此单列 `persistence` 能力。）

## Impact

**后端（`src/apiserver/app/`）**
- 新增 `db/`（engine、session、base、migrations、seed、reconcile）、`repositories/`、`models/orm.py`；`models/database.py` 由空文件变为引擎入口
- 改写 `api/routes/{auth,projects,simulate,reports}.py`、`services/simulation_service.py`、`services/algorithm_wrapper.py`（结果接收器）、`api/deps.py`、`main.py`（lifespan 启动/关闭）
- `core/security.py` 增加 seed 需要的密码哈希复用；`config.py` 增加存储配置

**依赖**
- 已锁定 `sqlalchemy==2.0.34`、`aiosqlite==0.20.0`，无需安装新包即可跑 SQLite；MySQL 部署时另装 `aiomysql`（写入 requirements 注释，不强行引入）

**数据与运维**
- 新增 `data/hvac.db`（SQLite）与 `data/datasets/`；既有 `data/reports/` 保持不变并被索引
- 首次启动写入两个默认账户（与现有演示账号同 id、同密码），不覆盖已修改的密码

**接口**
- 路径与响应结构保持不变（前端无需改动即可运行）；仅 `projectId` 缺省值与项目列表内容变化
