# Tasks

> 决策依据见 `design.md`，行为契约见 `specs/persistence/spec.md`。项目无自动化测试框架，验证采用「可观察行为 + 可复现命令」。
> 后端验证统一使用 `github_HVAC` 环境：`& 'D:/anaconda3/envs/github_HVAC/python.exe'`，工作目录 `src/apiserver`（与 dev.ps1 一致）；脚本可从仓库根运行，但需自行把 `src/apiserver` 加入 `sys.path`。

## 0. 基线与依赖（阻塞后续全部任务）

- [x] 0.1 记录改动前基线：把内存态字段清单（用户/项目/任务）、`data/reports/` 下全部报告目录（当前 11 份）的 `reportId/taskId/ownerId`、以及 `/api/simulate/results` 响应样例写入 `docs/baseline/baseline-before-persistence.json`；验证：文件存在且覆盖目录中的每个 reportId
- [x] 0.2 确认依赖可用且不新增必需包：`& 'D:/anaconda3/envs/github_HVAC/python.exe' -c "import sqlalchemy, aiosqlite, greenlet; print(sqlalchemy.__version__)"`；验证：输出 `2.0.34`，requirements 中不新增运行时依赖（仅注释说明 MySQL 驱动）

## 1. 持久化基础设施（D1/D2/D6/D10/D13）

- [x] 1.1 `config.py` 增加 `DATA_DIR`（默认 `<repo>/data`）、`DATASETS_DIR`、`REPORTS_DIR`、`DB_AUTO_MIGRATE`、`DB_ECHO`，并把 `DATABASE_URL` 归一化为 async 方言（`sqlite:///` → `sqlite+aiosqlite:///`，`mysql://` → `mysql+aiomysql://`）；验证：打印 settings 时 URL 含 `+aiosqlite`，且默认库路径在仓库 `data/` 下而非 `src/apiserver/`
- [x] 1.2 新增 `app/db/session.py`：`create_async_engine`、`async_sessionmaker(expire_on_commit=False)`、`get_db()` 依赖、`session_scope()` 上下文；SQLite 连接事件设置 `foreign_keys=ON / journal_mode=WAL / busy_timeout=30000 / synchronous=NORMAL`；验证：临时库上执行 `PRAGMA journal_mode` 返回 `wal`、`foreign_keys` 返回 1
- [x] 1.3 新增 `app/models/orm.py`：七张表与索引（`schema_migrations`、`users`、`projects`、`datasets`、`simulation_tasks`、`simulation_results`、`reports`），JSON 列用 `sqlalchemy.JSON`，`reports.task_id` 不设外键；验证：`Base.metadata.create_all` 后 `inspect` 出 7 张表，列名与 design D11 一致
- [x] 1.4 新增 `app/db/migrations/`（v1 = 初始结构）与 `app/db/migrate.py`（`upgrade()` / `status()`，CLI `python -m app.db.migrate upgrade|status`），`schema_migrations` 记录版本；验证：空库连续执行两次 `upgrade`，版本只记录一次、业务表行数不变
- [x] 1.5 把空文件 `app/models/database.py` 改为兼容入口（导出 `Base`、`engine`、`get_db`），避免旧 import 断链；验证：`from app.models.database import Base, engine, get_db` 可用

## 2. 仓储层（D3/D4/D5/D11）

- [x] 2.1 `app/repositories/users.py`：按用户名/ id 查询、创建、改密、判断是否为空；验证：临时库写入后在另一个 session 读到同一行，且重复用户名触发唯一约束
- [x] 2.2 `app/repositories/projects.py`：创建、按 owner 列表、按 id 查询、更新状态；验证：A 创建的项目在 B 的列表中不可见，admin 可见
- [x] 2.3 `app/repositories/datasets.py`：`save_from_rows`（规范化 JSON、sha256 命名、临时文件 + rename、同内容去重）、`load_rows`（读前校验指纹）；验证：同内容两次保存返回同一 id 且目录只有一个文件；篡改文件后 `load_rows` 抛错
- [x] 2.4 `app/repositories/tasks.py`：创建、更新进度、置状态、按用户/任务查询、启动收敛（`pending/running` → `failed`）；验证：收敛只影响未完成任务，已完成/失败/取消行不变
- [x] 2.5 `app/repositories/results.py`：`save_with_status(task_id, payload)` 在同一事务写结果并把任务置 `completed`；`load_payload(task_id)` 返回原始七区块；验证：事务内抛错时任务状态不是 `completed` 且无结果行
- [x] 2.6 `app/repositories/reports.py`：插入索引（含 `meta_payload`、路径、校验和）、按 id/任务查询、`reconcile` 扫描产物目录回填、标记 `artifact_state`；验证：临时报告目录全部回填后查询计数与目录数一致

## 3. 业务接入（D7/D8/D9/D12/D14）

- [x] 3.1 `api/routes/auth.py` 改为查库登录（bcrypt 校验），`/auth/me` 返回库中身份；验证：错误密码 401，正确密码返回 token，`user.id` 为 1/2
- [x] 3.2 `api/deps.py` 从数据库解析当前用户（`uid` 优先、缺失回退用户名；用户不存在或停用 → 401）；验证：删除库中用户后旧 token 返回 401
- [x] 3.3 `api/routes/projects.py` 的列表/详情/创建改为落库，响应保持 camelCase；验证：`POST /api/projects` 后 `GET` 列表与详情可取到；他人的项目返回 404/403
- [x] 3.4 `api/routes/simulate.py` 的 `start`：留存数据集 + 创建任务行（用户、项目、配置、数据元信息），再启动后台任务；验证：响应含 `taskId`，库中任务与数据集两行齐备，数据集文件 sha256 与登记值一致
- [x] 3.5 仿真循环：每周更新进度与 `updated_at`，每轮检查取消状态；验证：启动后立即取消，最终状态为 `cancelled` 且不会在结束后被改写为 `completed`
- [x] 3.6 完成路径：结果与 `completed` 同事务提交后再推送 WebSocket；验证：所有 `completed` 任务必有结果行；注入写结果异常时任务为 `failed`
- [x] 3.7 失败路径：异常写入 `status=failed` 与可读 `error`；验证：注入算法异常后库中 `error` 非空且结果查询被拒绝
- [x] 3.8 `restart` 从留存数据集回读输入并重置任务；验证：服务重启后对同一任务重新仿真成功，结果 `meta.totalRows` 与上次一致
- [x] 3.9 `status/results/list/cancel` 改为读库；`results` 的 `projectId` 有关联时返回真实 id、未关联返回 0；验证：两条任务分别覆盖两种情况，且响应七区块字段不变
- [x] 3.10 `algorithm_wrapper.run_simulation_streaming` 增加 `result_sink`，结束前写入 summary/weekly/monthly/meta/unmet（同时保留 `_last_*`）；验证：两个不同面积任务并行运行，各自 sink 中的面积正确、互不覆盖
- [x] 3.11 `api/routes/reports.py` 生成报告：校验任务已完成且结果存在 → 渲染 → `write_report_snapshot` → 插索引；索引失败时删除刚落盘目录并返回 500；验证：注入索引异常后目录被清理、接口返回 500 且无下载链接
- [x] 3.12 报告查询：`meta/download/list` 走索引，下载前校验文件存在与大小；验证：删除 `report.html` 后下载返回 404 且说明产物缺失；`list` 只含该任务报告
- [x] 3.13 `main.py` 增加 lifespan：迁移 → 写默认账户 → 收敛未完成任务 → 对账历史报告，关闭时 `engine.dispose()`；`DB_AUTO_MIGRATE=false` 且缺表时报可读错误；验证：启动日志出现四项各一次，二次启动不重复
- [x] 3.14 `schemas.py`：`StartSimulationRequest` 增加可选 `projectId`（默认 `None`），响应模型不变；验证：OpenAPI 中字段存在，旧请求（不带该字段）仍正常受理

## 4. 配置与文档

- [x] 4.1 `.gitignore` 增加 `data/hvac.db*` 与 `data/datasets/`；验证：在仓库根新建 `data/hvac.db` 后 `git status` 不显示为待提交
- [x] 4.2 `requirements.txt` 增加 `aiomysql` 的注释说明（MySQL 部署时安装），不引入运行时强制依赖；验证：文件含说明，SQLite 环境照常导入
- [x] 4.3 `README.md` 新增「持久化与恢复」章节：默认库与数据位置、迁移命令、重启语义（未完成任务收敛）、项目列表不再含演示数据；验证：按文档命令 `python -m app.db.migrate status` 可输出当前版本
- [x] 4.4 `程序框架设计方案.md` 数据层一节改为与实现一致（SQLAlchemy 2.0 async + 自建迁移），或明确标注 design D1 取代 Tortoise 方案；验证：文档不再把 Tortoise/Aerich 作为现行方案
- [x] 4.5 新增 `docs/persistence.md`：表结构、文件布局、备份与回滚、常用命令；验证：文档中的每条命令实跑通过

## 5. 集成验证

- [x] 5.1 新增 `scripts/verify_persistence.py`：在临时目录与临时库上跑「登录 → 建项目 → 提交任务（小数据） → 写结果 → 生成报告 → 重建引擎模拟重启 → 再读任务/结果/报告」；验证：脚本输出全部 `[PASS]`，退出码 0
- [x] 5.2 重启恢复断言：同一临时库两次初始化后，任务、七区块结果、报告索引均仍在且内容一致；验证：脚本重启段落断言通过
- [x] 5.3 并发隔离断言：两个不同面积的请求并行运行到完成，各自结果中的面积与汇总互不覆盖；验证：脚本断言两个任务的 `summary.area` 分别正确
- [x] 5.4 历史报告回填：把 `data/reports/` 的全部报告目录复制到临时报告目录，启动对账后按任务列出；验证：脚本断言回填条数与目录数一致且可下载
- [x] 5.5 幂等与防护断言：迁移重复执行、数据集重复提交、篡改数据集文件三种情形；验证：脚本分别断言「版本不重复」「同一 dataset id」「读取消验失败」
- [x] 5.6 端到端全年仿真不回归：`& 'D:/anaconda3/envs/github_HVAC/python.exe' scripts/verify_simulation.py` 三条断言仍通过；再跑一次真实任务生成报告并连续下载两次比对 sha256；验证：三条 `[PASS]` + 两次 sha256 相同
- [x] 5.7 前端不回归：`npx vue-tsc --noEmit -p tsconfig.app.json`（工作目录 `src/main`）零错误；验证：命令退出码 0

## 6. 验收口径

- [x] 6.1 三条可外部复核的结论：①重启后同一任务结果七区块与重启前一致；②两个并行任务结果不串号；③历史报告在重启后仍可列出并下载；验证：三条均可在 `verify_persistence.py` 输出中定位
- [x] 6.2 把持久化前后对照写入 `docs/migration-diff.md` 新增一节（内存态 → 库表、报告索引来源、任务恢复能力），并逐项注明对应决策编号；验证：差异项均可归因到 design 的 D1–D14

## Workflow follow-up

- 评审通过后归档本 change，并同步 `openspec/specs/persistence/spec.md` 主规格。
- 数据/报告清理策略与 MySQL 上云验证作为后续独立 change 处理（见 design 的 Open Questions）。
