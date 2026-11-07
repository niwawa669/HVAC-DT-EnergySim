# 持久化框架（运维与开发说明）

> 对应 change：`persistence-framework`。设计决策见 `openspec/changes/persistence-framework/design.md`（D1–D14）。

## 一、存储布局

| 内容 | 位置 | 说明 |
|---|---|---|
| 关系库 | `data/hvac.db`（默认） | SQLite，WAL 模式；由 `DATABASE_URL` 覆盖 |
| 输入数据文件 | `data/datasets/<sha256>.json` | 逐时数据，文件名即内容指纹 |
| 报告产物 | `data/reports/<report_id>/` | 仍是唯一产物：`report.html / result.json / meta.json` |
| 报告索引 | 数据库 `reports` 表 | 只做检索与归属校验，不复制 HTML |

## 二、数据表

| 表 | 作用 | 关键约束 |
|---|---|---|
| `schema_migrations` | 已执行的迁移版本 | 主键 `version`，每个版本只执行一次 |
| `users` | 账户与角色 | `username` 唯一；首次启动写入 admin/user |
| `projects` | 项目 | `owner_id` 外键；按 owner 过滤 |
| `datasets` | 输入数据元数据 | 主键 = sha256，同内容去重 |
| `simulation_tasks` | 任务状态机 | 索引 `(user_id, updated_at)`、`status` |
| `simulation_results` | 七区块结果 | 主键/外键 `task_id`，级联删除 |
| `reports` | 报告索引 | 主键 `report_id`；`task_id` 不设外键（兼容历史报告） |

## 三、启动与关闭

启动顺序（`app/main.py` 的 lifespan）：

1. `ensure_storage_dirs()`：创建并校验 `DATA_DIR / DATASETS_DIR / REPORTS_DIR` 可写，否则以可读错误退出；
2. 迁移：`DB_AUTO_MIGRATE=true` 时补齐未执行版本；关闭时只做结构自检，缺结构即拒绝启动。
   **v2 一次性回填**历史任务的项目关联就在这一步：按（用户, 项目名）建/复用项目并回填 `project_id`，只执行一次；
3. 种子：用户表为空时写入默认账户（admin/user，密码 123456），已存在则不覆盖；
4. 收敛：把 `pending/running` 任务置为 `failed`，原因写明"服务重启中断"；
5. 对账：扫描报告目录，补插索引；索引在库但产物缺失的标为 `artifact_state=missing`。

> 启动**不再回填**项目关联。回填若留在启动流程里，会把“用户删除项目后解绑的任务”重新解释成“待回填”，删除的项目下次启动就会复活（见 change `project-lifecycle-and-evaluation` 的设计决策 D1/D2）。

关闭时释放连接池（`engine.dispose()`）。

## 四、常用命令

以下命令在 `src/apiserver` 目录下执行（与 `scripts/dev.ps1` 的启动目录一致）：

```powershell
# 结构状态（当前版本 / 已执行清单 / 待执行数量）
python -m app.db.migrate status

# 手动补齐迁移（等价于启动时的自动迁移）
python -m app.db.migrate upgrade

# 持久化自检：迁移幂等、种子幂等、历史报告回填、登录、项目隔离、
# 数据集去重/篡改检测、真实仿真落库、并行隔离、报告生成/下载、重启恢复
python scripts/verify_persistence.py
```

> 后端依赖使用 `github_HVAC` 环境；在仓库根运行脚本即可，脚本会自行把 `src/apiserver` 加入 `sys.path`。
> 直接跑 uvicorn 时工作目录应为 `src/apiserver`（与 `scripts/dev.ps1` 一致）。

## 五、配置项

| 环境变量 / 配置 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | 空 -> `data/hvac.db` | 支持 `sqlite:///`、`mysql://`，会自动补异步方言 |
| `DATA_DIR` | `<repo>/data` | 库、数据集、报告的根目录 |
| `DATASETS_DIR` | `DATA_DIR/datasets` | 输入数据文件 |
| `REPORTS_DIR` | `DATA_DIR/reports` | 报告产物（`HVAC_REPORTS_DIR` 仍兼容） |
| `DB_AUTO_MIGRATE` | `true` | 启动时自动升级结构 |
| `DB_ECHO` | `false` | 输出 SQL（排查用） |

## 六、备份与回滚

- **备份**：停服后复制 `data/hvac.db`（连同 `-wal/-shm`）与 `data/datasets/`、`data/reports/` 三处即可。
- **回滚到旧代码**：停服 -> 回退代码 -> 启动。旧代码不读数据库，`data/reports/` 未被改动，历史报告仍可下载；必要时删除 `data/hvac.db` 与 `data/datasets/`。
- **删除数据库**：只丢任务/项目/账户与报告索引；报告 HTML 仍在盘上，下次启动会按目录重新回填索引。

## 七、行为变化（对使用者的影响）

1. 项目列表不再包含 3 条内置演示数据，首次进入为空列表，新建项目会真正落库。
2. `GET /api/simulate/results/{task_id}` 的 `projectId`：任务关联了项目时为真实 id，未关联时为 `0`。
3. 服务重启后未完成的任务会显示为"失败：服务重启中断"，可点击"重新仿真"从留存数据重算。
4. 同一份输入数据重复提交不会产生第二份文件（按内容哈希去重）。
5. 启动仿真时若未指定 projectId，会按（用户, 项目名）自动创建/复用项目；项目状态随任务同步（待处理/运行中/已完成/失败/已取消），项目列表与详情返回最近任务和结果摘要。
6. 删除项目只解除任务关联，仿真任务、结果与报告仍保留；删除是硬删除，重启后项目不会重新出现（历史任务的项目关联只在迁移 v2 回填一次）。
