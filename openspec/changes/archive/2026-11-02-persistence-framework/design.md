# Design

## Context

后端现状与本次设计直接相关的约束：

- `app/models/database.py` 是空文件，`requirements.txt` 已锁定 `sqlalchemy==2.0.34` 与 `aiosqlite==0.20.0`，`config.py` 有 `DATABASE_URL = "sqlite:///./hvac.db"` 但没有任何代码使用它。
- 业务状态分布在三处内存字典：`auth.fake_users_db`、`projects.fake_projects`、`SimulationService.tasks`；报告是唯一已经落盘的产物（`data/reports/<report_id>/`，当前 11 份）。
- `algorithm_wrapper` 用 `self._last_*` 全局字段交付结果；`simulation_service` 在流式循环结束后读取这些字段。
- 后端由 `scripts/dev.ps1` 以 `WorkingDirectory = src/apiserver` 启动，因此任何"相对当前目录"的默认路径都会落到 `src/apiserver/` 而不是仓库根。
- 运行环境：Python 3.12（`github_HVAC` 环境），当前未安装 Alembic / Tortoise / aiomysql，且不保证能联网安装。
- `程序框架设计方案.md` 规划的是 Tortoise ORM + MySQL + Aerich，与代码现状（SQLAlchemy + aiosqlite）不一致。

## Goals / Non-Goals

**Goals:**

- 所有业务状态由关系库承载，服务重启后任务、结果、项目、报告索引、账户仍可读。
- 输入数据可留存、可校验、可复现；重新仿真不依赖内存。
- 结果写入与任务终态原子提交；任务之间的结果物理隔离。
- 报告"文件是产物、库是索引"，启动时自动对账，兼容既有 11 份历史报告。
- 结构变更版本化、幂等；存储位置与后端由配置决定。
- SQLite 单机开箱可用；切 MySQL 只改 `DATABASE_URL`（另装驱动）。
- 对前端接口路径与响应结构保持兼容，前端可不改。

**Non-Goals:**

- 不引入 Redis / Celery / 消息队列，不改变"进程内后台任务"的执行模型。
- 不做多实例部署、分布式锁、读写分离与连接池调优。
- 不引入对象存储；数据文件与报告仍放本地磁盘（目录可配置）。
- 不重构鉴权（无 refresh token、无权限模型调整）；不重写报告模板。
- 不迁移"改动前已消失的内存任务"——它们没有持久化载体，本次无法恢复。

## Decisions

### D1 采用 SQLAlchemy 2.0 async，而不是设计文档里的 Tortoise ORM

**选择**：`create_async_engine` + `async_sessionmaker` + 声明式模型；SQLite 走 `aiosqlite`，MySQL 走 `aiomysql`。

**理由**：依赖已在 `requirements.txt` 锁定且环境可导入；设计文档的 Tortoise/Aerich 既未安装，也没有任何代码铺垫。以代码现状为准可以立刻验证，而换 Tortoise 需要联网安装、重写全部模型与迁移，收益仅是"与旧文档一致"。

**代价**：`程序框架设计方案.md` 需要同步修订（或标注本决策取代之）；迁移工具需要自建（见 D2）。

**备选**：Tortoise + Aerich（放弃：依赖不可用）；同步 SQLAlchemy（放弃：会阻塞事件循环）。

### D2 自建版本化迁移器，而不是 Alembic

**选择**：`app/db/migrations/` 下按序号注册迁移函数，`schema_migrations(version, name, applied_at)` 记录已执行版本；启动时按序补齐（可配置关闭），并提供 `python -m app.db.migrate`（`upgrade` / `status`）。

**理由**：Alembic 未安装且不保证可安装；本次只有一次初始建表 + 少量索引，自建 ~80 行即可满足"版本顺序、只执行一次、可查询、可关闭"。迁移函数拿到底层连接执行，未来要换 Alembic 可把 `version` 当作基线。

**代价**：没有 autogenerate，也没有 downgrade 生态。**缓解**：每个迁移保持"只增不改"，并在设计文档记录；`status` 输出待执行数量。

**注意**：SQLite 的 DDL 可回滚，MySQL 的 DDL 会隐式提交；因此迁移体只允许幂等 DDL（`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX` 前先查存在性），不写"跨表搬迁"的复杂逻辑。

### D3 七区块结果整体存 JSON 文档，另加派生列

**选择**：`simulation_results.payload` 存 `{meta, summary, weekly_data, monthly_data, unmet_hours_detail}` 整体；同表冗余 `total_energy / total_cooling_load / eui / carbon_emission / peak_load / caliber_version` 六个派生列。

**理由**：结果契约是一个整体文档（报告按整体快照消费），拆成 53 行周表 + 12 行月表会引入映射漂移，却几乎没有查询收益；派生列足以支撑列表页与看板。

**代价**：不能对周/月行做 SQL 聚合。**缓解**：契约本来就要求由结果整体复算；如未来需要跨任务对比，再加物化表。

**备选**：全字段规范化（放弃：读路径复杂、迁移成本高）；仅存文件（放弃：失去事务与索引能力）。

### D4 输入数据存文件、库中存元数据与指纹

**选择**：逐时数据规范化为 JSON 数组写入 `data/datasets/<sha256>.json`（先写 `.tmp` 再 rename），`datasets` 表存 `id(=sha256)`、文件名、行数、列数、时间列、表头、`storage_path`、`sha256`；任务存 `dataset_id`。读取时重算文件 sha256，不一致即拒绝复现。

**理由**：8760 行约 1 MB，作为 BLOB 进库会让备份/迁移变重，也不便于人工排查；"文件 + 指纹 + 元数据"是常规做法。以内容哈希作主键天然去重（相同内容重复提交复用同一行），并且指纹就是完整性校验值。

**代价**：备份需要"库 + 数据目录"两份；数据库与文件不是同一事务。**缓解**：启动对账 + 读取时校验；数据文件只增不改。

### D5 报告：文件是唯一产物，库是索引

**选择**：`reports` 表存 `report_id`、`task_id`、`owner_id`、版本、生成时间、章节清单、`meta_payload`（整份 meta.json 内容）、三个产物路径与 `html_sha256/html_size`。写入顺序：先原子落盘目录（沿用 `write_report_snapshot`），再插索引；插索引失败则尽力删除刚落盘的目录并返回 500。

**理由**：HTML 必须字节稳定地原样下载，放文件最稳；索引只负责检索与归属校验。`meta_payload` 让 `GET /api/reports/{id}` 在产物被删后仍能给出可读解释，也保证接口形状与历史 meta.json 一致。

**兼容**：`reports.task_id` **不设外键**——现有 11 份报告的 task 早已不在任何存储中，设外键会导致启动对账失败。归属校验在应用层完成（任务存在时校验 owner；任务不存在时以 `owner_id` 为准）。

**对账**：启动时扫描 `REPORTS_DIR`，对 `meta.json` 可读且索引缺失的目录补插索引；对索引在库、`report.html` 不在盘的记录标记 `artifact_state='missing'`（不改动产物，不删行）。下载时再校验一次文件存在，缺失返回 404 并说明"产物缺失"。

### D6 会话与事务边界

**选择**：`db/session.py` 暴露 `engine`、`SessionLocal`、`get_db()`（请求级依赖）与 `session_scope()`（后台任务用）；`expire_on_commit=False`。仓储方法只接受 `AsyncSession`，不自行提交；提交由"用例"（路由或服务）在语义边界上完成。

**理由**：把事务边界放在用例层，才能实现"结果 + completed 状态"一次提交（D7）。仓储不提交也便于组合与测试。

**事务粒度**：仿真主体**不包在一个长事务里**（一次全年仿真可能数分钟，长事务会锁库）。进度按周独立短事务提交；最终"写结果 + 置 completed"合并为一个短事务。进度可以丢失，状态不得回退。

### D7 任务状态机与中断收敛

**状态转移**：`pending → running → completed | failed | cancelled`；`restart` 允许 `failed/cancelled/completed → pending`（重置进度、清空结果，保留输入）。取消由服务在每周循环检查数据库状态实现（当前实现只改状态、循环仍会跑到完成——顺带修正）。

**启动收敛**：`pending/running` 的任务改为 `failed`，原因写明"服务重启中断（进程退出时任务未完成），可点击重新仿真"。已完成/失败/取消的任务不受影响。

**结果原子性**：`simulation_results` 以 `task_id` 为主键；写结果与置状态在同一事务。查询结果要求状态为 `completed` **且**结果行存在，二者缺一即报错，避免"已完成无结果"。

### D8 消除 `_last_*` 全局结果串号

**选择**：给 `run_simulation_streaming` 增加可选参数 `result_sink: dict`，在生成器结束前把 summary/weekly/monthly/meta/unmet 写入该字典；`simulation_service` 传自己的字典并在循环后读取。`_last_*` 赋值保留，供既有脚本与调试使用。

**理由**：这是并发任务读到别人结果的根因；不修它，持久化只会把错误结果稳定地写进库。

**代价**：生成器参数变多。**缓解**：`result_sink` 缺省为 `None`，旧调用方式行为不变。

### D9 时间戳口径保持本地时间

**选择**：`DateTime` 存本地时间（`datetime.now()`），接口序列化与现状一致。

**理由**：前端目前直接展示接口返回的时间字符串；改为 UTC 会让所有既有页面出现 +8 小时偏移或带时区后缀，属于无关变更。项目是单站点部署，跨时区不是需求。

**代价**：多时区部署需另行改造。**缓解**：在表注释与文档中写明"本地时间"，未来引入 UTC 时统一加迁移。

### D10 配置与默认路径绝对化

**选择**：`config.py` 增加 `DATA_DIR`（默认 `<repo>/data`）、`DATASETS_DIR`、`REPORTS_DIR`、`DB_AUTO_MIGRATE=True`、`DB_ECHO=False`；`DATABASE_URL` 默认 `sqlite+aiosqlite:///<repo>/data/hvac.db`，并接受旧写法 `sqlite:///...`（自动补 `+aiosqlite`）与 `mysql://`（补 `+aiomysql`）。启动时确保目录存在、可写，失败直接抛错退出。

**理由**：`dev.ps1` 的工作目录是 `src/apiserver`，相对路径会把库文件散落到源码目录；绝对化后行为与启动方式无关，也满足"不得静默落盘"的要求。

**代价**：不再支持"在当前目录就地生成 hvac.db"。**缓解**：在 README 写明默认位置与覆盖方式。

### D11 表结构与约束

| 表 | 关键列 | 约束/索引 |
|---|---|---|
| `schema_migrations` | `version` / `name` / `applied_at` | 主键 `version` |
| `users` | `id` / `username` / `hashed_password` / `role` / `is_active` | `username` 唯一；`role` 仅取 `admin/engineer` |
| `projects` | `id` / `owner_id` / `name` / `building_type` / `area` / `status` / `config` | `ix_projects_owner(owner_id, updated_at)` |
| `datasets` | `id`(sha256) / `filename` / `row_count` / `headers` / `storage_path` | 主键 `id`；`sha256` 唯一 |
| `simulation_tasks` | `id` / `user_id` / `project_id` / `dataset_id` / `status` / `progress` / `config` / `data_meta` | `ix_tasks_user_updated(user_id, updated_at)`、`ix_tasks_status(status)` |
| `simulation_results` | `task_id` / `payload` / `caliber_version` / 派生列 | 主键 `task_id`，FK `tasks.id` `ON DELETE CASCADE` |
| `reports` | `report_id` / `task_id` / `owner_id` / `meta_payload` / 产物路径 | `ix_reports_task(task_id, generated_at)`；`report_id` 主键 |

`projects`、`simulation_tasks` 对 `users` 有外键；`reports.task_id` 与 `reports.owner_id` 不设外键（D5 的兼容理由）。`data_meta` 与 `config` 用 `JSON` 类型（SQLite 为 TEXT，MySQL 为 JSON）。

### D12 初始化数据

**选择**：首次启动若 `users` 为空，写入 `admin(id=1, role=admin)` 与 `user(id=2, role=engineer)`，密码均为 `123456`（bcrypt 哈希），与现状一致；**按 username 判存在**，任何已存在账户一律不覆盖。项目**不注入**演示数据。

**理由**：显式 id 让改动前签发的令牌（`uid=1/2`）继续可用；不注入演示项目，避免"真实数据里混三条假记录"。

**代价**：首次进入项目页是空列表。**缓解**：前端空态已存在；文档写明该变化。

### D13 并发与 SQLite 设置

**选择**：连接事件里执行 `PRAGMA foreign_keys=ON`、`journal_mode=WAL`、`busy_timeout=30000`、`synchronous=NORMAL`；引擎 `pool_pre_ping=True`。仿真进度写库按"每周一次 + 状态变化即时"提交，不逐小时写。

**理由**：WAL 允许"一写多读"，`busy_timeout` 把偶发并发写冲突转化为等待而不是 500。周级进度已足够满足"重启后看到最后进度"。

**代价**：SQLite 仍是单写者；两个全年仿真并行时写事务会排队。**缓解**：进度写入很短；如成为瓶颈切 MySQL（D1 已保留路径）。

### D14 接口兼容策略

- 路径与字段名不变；`TaskResponse` 的时间字段由数据库时间序列化，格式与原来一致。
- `GET /api/simulate/results` 的 `projectId`：任务有 `project_id` 则返回真实值，否则返回 `0`（前端类型为 number，不校验非零）。
- 项目创建接受 `{name, buildingType, area, status?}`，保持现状的严格校验风格。
- `GET /api/reports/{id}` 返回的字段集合沿用历史 meta.json 的键（`reportId/taskId/ownerId/reportVersion/caliberVersion/generatedAt/carbonFactor/chapterOrder/chapterTitles`）。

## Risks / Trade-offs

- **[风险] SQLite 并发写锁** → WAL + 30s busy_timeout + 周级进度写；并行仿真的写事务很短，必要时切 MySQL。
- **[风险] 数据库与数据文件/报告目录不是同一事务** → 数据文件只增不改、写入用 `.tmp` + rename；报告"先产物后索引"并在索引失败时清理；启动对账兜底。
- **[风险] 自建迁移器缺少生态能力（autogenerate/downgrade）** → 迁移只增不改、每个迁移可在空库上重复验证、`status` 暴露版本；后续可平滑切 Alembic。
- **[风险] 结果 JSON 文档无法做跨任务 SQL 聚合** → 派生列覆盖看板需求；需要时再加物化表，不改契约。
- **[风险] 本地时间戳** → 单站点部署可接受；跨时区需求出现时统一改 UTC 并加迁移。
- **[风险] 历史报告的任务已不存在，无法校验归属** → 以 `meta.json` 的 `ownerId` 为准；缺失归属的记录只对管理员开放（保持现状的 403 语义）。
- **[风险] 删除/篡改数据库或被清空的产物** → 下载前校验文件存在与校验和；缺失返回 404 并说明，不返回空内容。
- **[权衡] 保持进程内后台任务** → 重启即中断（状态收敛为可解释的失败），不承诺"断点续算"；这是非目标。

## Migration Plan

1. **上线**：部署新代码 → 首次启动自动建表、写入默认账户、把 `data/reports/` 下的历史报告补入索引；`data/hvac.db` 与 `data/datasets/` 自动创建。
2. **数据**：不迁移任何内存数据（无可迁移载体）；报告产物原地不动；前端无强制改动。
3. **回滚**：停服 → 回退代码 → 旧代码不读数据库，直接忽略 `data/hvac.db`；`data/reports/` 未被改动，历史报告仍可下载。必要时删除 `data/hvac.db` 与 `data/datasets/`（新库会在下次上线重建）。
4. **校验**：`python scripts/verify_persistence.py` 在临时数据库上跑完整链路（登录 → 建项目 → 提交任务 → 结果 → 报告 → 模拟重启 → 再读），并核对报告与数据指纹。

## Open Questions

- 数据留存与报告产物的**清理策略**（保留天数 / 按任务删除）本次不做，待有容量压力或合规要求时单独立项。
- MySQL 的实际部署验证（驱动安装、字符集、JSON 列行为）留待上云时补；本次以 SQLite 为验收环境。
- 多实例部署下的任务并发与启动收敛语义（谁负责把别人的 running 任务标记失败）留待引入多副本时决定。
