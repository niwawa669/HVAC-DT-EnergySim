# Tasks

> 本 change 的实现先于文档落地：第 1 组是已落地部分的留痕复核，第 2–4 组是本次设计裁决带来的待修工作，第 5 组是集成验收。验证环境为 `github_HVAC`（Python 3.12）与 `vue-tsc`。

## 1. 已落地部分（复核留痕）

- [x] 1.1 启动仿真未传 `projectId` 时按（用户, 项目名）建/复用项目并关联任务；验证：`verify_persistence.py`「未指定 projectId 时自动创建项目」「自动项目关联本次仿真任务」通过
- [x] 1.2 任务状态同步到项目状态，重新仿真复位为待运行；验证：`verify_persistence.py`「自动项目状态反映仿真完成」「重新仿真复位为 pending」通过
- [x] 1.3 项目列表与详情聚合最近任务与结果摘要，无任务时字段显式为空；验证：`serialize` 恒定返回 `latestTask` / `latestSummary`，无任务项目仍出现在列表
- [x] 1.4 新建项目表单的默认值、必填校验与上传区等宽对齐；验证：项目名默认「测试项目」，上传拖拽区宽度为 100%（无固定 360px）
- [x] 1.5 雷达图五维 0–100 归一化、60 分参考线与明细表；验证：`buildRadarMetrics` 返回 5 项且 `score` 落在 0–100
- [x] 1.6 全年冷机平均负荷率从算法层贯通到结果契约与前端；验证：结果 schema 含该字段，`verify_persistence.py` 的冷机平均负荷率断言通过

## 2. 回填降级为一次性迁移（D2）

- [x] 2.1 新增 `app/db/migrations/v2_backfill_project_links.py`：用原生 SQL 按 (user_id, project_name) 分组建/复用项目并回填 `project_id`，注册进 `MIGRATIONS`；验证：空库 `upgrade()` 后 `schema_migrations` 出现版本 2，再执行一次无新版本
- [x] 2.2 迁移输出回填统计（回填任务数、新建项目数）；验证：日志数量与「执行前 `project_id IS NULL` 且 `project_name` 非空」的任务条数一致
- [x] 2.3 撤掉 `main.py` 启动序列中的回填调用并调整启动日志与顺序；验证：启动日志不再出现「回填项目关联」，`main.py` 中无 `backfill_task_links` 引用
- [x] 2.4 清理 `repositories/projects.py` 里 `backfill_task_links` 的归宿（删除，或明确标注仅供迁移使用）；验证：无死代码残留，`python -c "import app.main"` 通过
- [x] 2.5 `verify_persistence.py` 的迁移断言由 `[1]` 改为 `[1, 2]`，并让脚本内的 `startup()` 与 `main.py` 启动序列一致；验证：脚本首次启动断言打印 `[1, 2]`，第二次为 `[]`
- [x] 2.6 README「六、持久化与恢复」的启动顺序与 `docs/persistence.md` 的回填表述改为「迁移（含一次性回填）→ 种子 → 收敛中断任务 → 报告对账」；验证：文档中不再出现「启动时回填历史任务的项目关联」

## 3. 删除语义（D1 / D3）

- [x] 3.1 删除拒绝条件改为「该项目下存在 `pending` 或 `running` 任务」，不再只看最近一条；验证：构造「运行中任务不是最新那条」的项目，`DELETE /api/projects/1` 返回 409 而非 200
- [x] 3.2 删除后重启不复活；验证：删除项目 → 执行启动序列 → 该项目不在列表，其任务 `project_id` 仍为 `NULL`
- [x] 3.3 `verify_persistence.py` 增加两条断言：「删除 → 重启后项目不复活」「一次性回填只发生一次」；验证：脚本全绿；把 2.3 撤掉的回填调用临时放回后，第一条断言变红

## 4. 旧结果评价（D5）

- [x] 4.1 结果缺 `avgChillerLoadRate` 时该维度不得以 0 分参评：等级与点位标为缺失，不显示「待改进」、不落在圆心；验证：用去掉该字段的结果 JSON 打开监控页，该维度无 0 分点位
- [x] 4.2 雷达图说明注明「按当前基准折算」；验证：监控页雷达图说明文字含该句
- [x] 4.3 `docs/radar-benchmark.md` 与 README「九、结果评价」声明「阈值更新会让历史结果的分数与等级变化，结果数值不变」；验证：两处文档均含该声明

## 5. 集成验收

- [x] 5.1 `python scripts/verify_persistence.py` 全绿（含第 2、3 组新增断言）
- [x] 5.2 `python scripts/verify_accounts.py` 不回归
- [x] 5.3 在 `src/main` 下执行 `vue-tsc --noEmit -p tsconfig.app.json`，退出码 0
- [x] 5.4 手工链路：新建并完成一次仿真 → 删除该项目 → 重启服务 → 列表无该项目；打开改造前的结果显示「—（旧结果）」；验证：连续两次重启结果一致

## Workflow follow-up

- 复核通过后执行 `openspec validate --change project-lifecycle-and-evaluation` 并归档：`project-lifecycle`、`project-setup`、`result-evaluation` 进入主 specs，`simulation-result` 为修改。
- 归档前确认 v2 迁移在发布说明中标注为「一次性回填，可能复活发布时仍存的孤儿任务」。
