"""持久化框架自检（tasks 5.1-5.5）。

覆盖：迁移幂等、种子幂等、历史报告回填、SQLite PRAGMA、登录鉴权、
项目隔离、数据集去重与篡改检测、真实仿真落库、并行任务结果隔离、
结果与终态原子性、报告生成/索引/下载、模拟重启后的恢复、中断任务收敛。

运行：
    python scripts/verify_persistence.py
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.gettempdir()) / f"hvac_persist_{uuid.uuid4().hex[:10]}"
TMP.mkdir(parents=True, exist_ok=True)

os.environ["DATA_DIR"] = str(TMP)
os.environ["HVAC_REPORTS_DIR"] = str(TMP / "reports")
os.environ["DATABASE_URL"] = ""
os.environ["DB_AUTO_MIGRATE"] = "true"

sys.path.insert(0, str(ROOT / "src" / "apiserver"))

RESULTS = []
AREA_PRIMARY = 120000.0


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    if ok:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}" + (f" :: {detail}" if detail else ""))


def load_rows(limit: int, offset: int = 0):
    path = ROOT / "src" / "main" / "buildingload" / "buildingloads_adjusted.csv"
    with open(path, "r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        headers = list(reader.fieldnames or [])
        rows = []
        for index, row in enumerate(reader):
            if index < offset:
                continue
            if index >= offset + limit:
                break
            item = {}
            for key, value in row.items():
                try:
                    item[key] = float(value)
                except (TypeError, ValueError):
                    item[key] = value
            rows.append(item)
    return headers, rows


async def startup() -> dict:
    from app.config import ensure_storage_dirs
    from app.db.migrate import upgrade
    from app.db.seed import seed_default_users
    from app.db.session import session_scope
    from app.repositories import reports as reports_repo
    from app.repositories import tasks as tasks_repo

    ensure_storage_dirs()
    executed = await upgrade()
    async with session_scope() as session:
        seeded = await seed_default_users(session)
        interrupted = await tasks_repo.mark_interrupted(session)
        reconcile = await reports_repo.reconcile_from_disk(session)
    return {
        "migrated": executed,
        "seeded": seeded,
        "interrupted": interrupted,
        "reconcile": reconcile,
    }


async def main() -> int:
    # 把仓库里已有的报告复制到临时报告目录，验证"启动回填"
    legacy_source = ROOT / "data" / "reports"
    legacy_ids = []
    if legacy_source.is_dir():
        for entry in legacy_source.iterdir():
            if entry.is_dir() and (entry / "meta.json").is_file():
                legacy_ids.append(entry.name)
        shutil.copytree(legacy_source, TMP / "reports", dirs_exist_ok=True)

    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from sqlalchemy import func, select, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.api.deps import get_current_user
    from app.api.routes.auth import login
    from app.api.routes.projects import create_project, get_projects
    from app.api.routes.reports import (
        download_report,
        generate_report,
        get_report_meta,
        list_reports,
    )
    from app.api.routes.simulate import (
        get_simulation_results,
        restart_simulation,
        start_simulation,
    )
    from app.config import Settings, ensure_storage_dirs, settings
    from app.db.session import (
        dispose_engine,
        get_engine,
        get_session_factory,
        session_scope,
    )
    from app.db.migrate import ensure_schema_ready
    from app.models.orm import Base, Dataset, Project, Report, SimulationTask, User
    from app.models.schemas import (
        LoginRequest,
        ProjectCreate,
        SimulationConfig,
        StartSimulationRequest,
    )
    from app.repositories import datasets as datasets_repo
    from app.repositories import projects as projects_repo
    from app.repositories import reports as reports_repo
    from app.repositories import results as results_repo
    from app.repositories import tasks as tasks_repo
    from app.repositories import users as users_repo
    import app.api.routes.reports as reports_routes
    from app.services.simulation_service import simulation_service

    # ---------- 1. 启动：迁移 / 种子 / 报告对账 ----------
    state = await startup()
    check("首次启动执行迁移 v1/v2", state["migrated"] == [1, 2], str(state["migrated"]))
    check("首次启动写入默认账户", state["seeded"] == 2, str(state["seeded"]))
    check(
        "历史报告回填全部产物",
        state["reconcile"]["imported"] == len(legacy_ids) and len(legacy_ids) > 0,
        f"imported={state['reconcile']['imported']} legacy={len(legacy_ids)}",
    )

    state_again = await startup()
    check("迁移幂等（第二次无新版本）", state_again["migrated"] == [], str(state_again["migrated"]))
    check("种子幂等（第二次不新增账户）", state_again["seeded"] == 0, str(state_again["seeded"]))
    check(
        "回填幂等（第二次不重复导入）",
        state_again["reconcile"]["imported"] == 0,
        str(state_again["reconcile"]),
    )

    async with get_engine().connect() as conn:
        journal_mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        foreign_keys = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
    check("SQLite 使用 WAL", str(journal_mode).lower() == "wal", str(journal_mode))
    check("SQLite 开启外键", int(foreign_keys) == 1, str(foreign_keys))

    expected_tables = {
        "schema_migrations", "users", "projects", "datasets",
        "simulation_tasks", "simulation_results", "reports",
    }
    check(
        "ORM 声明七张表",
        expected_tables <= set(Base.metadata.tables),
        str(sorted(Base.metadata.tables)),
    )

    from app.models import database as legacy_database

    check(
        "models.database 兼容入口可用",
        legacy_database.Base is Base and callable(legacy_database.get_db),
    )

    async with session_scope() as session:
        user_count = await session.scalar(select(func.count()).select_from(User))
    check("用户表只有两条种子账户", int(user_count) == 2, str(user_count))

    async with session_scope() as session:
        try:
            await users_repo.create(session, username="admin", hashed_password="x")
            unique_blocked = False
        except IntegrityError:
            unique_blocked = True
            await session.rollback()
    check("用户名唯一约束生效", unique_blocked)

    # ---------- 2. 登录与鉴权 ----------
    async with session_scope() as session:
        token_response = await login(LoginRequest(username="admin", password="123456"), session)
        admin = {
            "id": token_response.user["id"],
            "username": token_response.user["username"],
            "role": token_response.user["role"],
            "email": token_response.user.get("email"),
        }
        me = await get_current_user(token=token_response.access_token, db=session)
    check("默认账户可登录", admin["id"] == 1 and me["username"] == "admin", str(admin))

    async with session_scope() as session:
        try:
            await login(LoginRequest(username="admin", password="wrong"), session)
            bad_login_status = None
        except HTTPException as exc:
            bad_login_status = exc.status_code
    check("错误密码返回 401", bad_login_status == 401, str(bad_login_status))

    # ---------- 3. 项目隔离 ----------
    async with session_scope() as session:
        project = await create_project(
            ProjectCreate(name="持久化自检项目", buildingType="office", area=50000),
            admin,
            session,
        )
        admin_projects = await get_projects(admin, session)
        other = await projects_repo.create(session, owner_id=2, name="他人项目", area=1000)
        other_id = other.id
        mine = await projects_repo.list_for_user(session, 1, is_admin=False)
        everyone = await projects_repo.list_for_user(session, 1, is_admin=True)
    check("项目创建落库并出现在列表", any(p["id"] == project["id"] for p in admin_projects), str(project))
    check("普通用户看不到他人项目", all(p.id != other_id for p in mine), str([p.id for p in mine]))
    check("管理员能看到他人项目", any(p.id == other_id for p in everyone), str([p.id for p in everyone]))

    # ---------- 4. 数据集：去重与篡改检测 ----------
    headers, rows = load_rows(168)
    config = SimulationConfig().model_dump(mode="json")
    async with session_scope() as session:
        dataset_a = await datasets_repo.save_from_rows(
            session, rows=rows, headers=headers, time_column=headers[0],
            filename="buildingloads_adjusted.csv", uploaded_by=1,
        )
        dataset_b = await datasets_repo.save_from_rows(
            session, rows=rows, headers=headers, time_column=headers[0],
            filename="another-name.csv", uploaded_by=1,
        )
        dataset_id = dataset_a.id
        dataset_path = Path(dataset_a.storage_path)
        dataset_sha = dataset_a.sha256
    file_count = len(list((TMP / "datasets").glob("*.json")))
    check("相同内容复用同一数据集", dataset_a.id == dataset_b.id, f"{dataset_a.id} / {dataset_b.id}")
    check("数据集文件只有一份", file_count == 1, str(file_count))
    check("数据集文件指纹与登记一致", hashlib.sha256(dataset_path.read_bytes()).hexdigest() == dataset_sha)

    # ---------- 5. 真实仿真任务落库 ----------
    task_id = str(uuid.uuid4())
    async with session_scope() as session:
        await tasks_repo.create(
            session,
            task_id=task_id,
            user_id=1,
            project_id=project["id"],
            dataset_id=dataset_id,
            project_name="持久化自检项目",
            building_type="office",
            area=AREA_PRIMARY,
            config=config,
            data_meta={"fileName": "buildingloads_adjusted.csv", "totalRows": len(rows)},
        )

    request_data = {
        "config": config,
        "data": {"rows": rows, "headers": headers, "timeColumn": headers[0]},
        "projectName": "持久化自检项目",
        "buildingType": "office",
        "area": AREA_PRIMARY,
        "dataMeta": {"fileName": "buildingloads_adjusted.csv", "totalRows": len(rows)},
    }
    started = time.time()
    await simulation_service.run_task(task_id, request_data)
    elapsed = time.time() - started
    async with session_scope() as session:
        task = await tasks_repo.get(session, task_id)
        payload = await results_repo.load_payload(session, task_id)
    check("仿真任务完成", task is not None and task.status == "completed", f"{getattr(task, 'status', None)} in {elapsed:.1f}s")
    check("结果七区块齐备（含缺口明细）", bool(payload) and {"meta", "summary", "weekly_data", "monthly_data", "unmet_hours_detail"} <= set(payload), str(list(payload)) if payload else "none")
    check("结果记录数据行数", (payload or {}).get("meta", {}).get("totalRows") == len(rows), str((payload or {}).get("meta", {}).get("totalRows")))
    check("结果记录面积", (payload or {}).get("summary", {}).get("area") == AREA_PRIMARY, str((payload or {}).get("summary", {}).get("area")))
    chiller_load_rate = (payload or {}).get("summary", {}).get("avgChillerLoadRate")
    check(
        "结果包含全年冷机平均负荷率",
        isinstance(chiller_load_rate, (int, float)) and 0 <= float(chiller_load_rate) <= 100,
        str(chiller_load_rate),
    )
    async with session_scope() as session:
        result_response = await get_simulation_results(task_id, admin, session)
    check(
        "结果接口返回冷机平均负荷率",
        abs(
            float(result_response.summary.avgChillerLoadRate) - float(chiller_load_rate)
        ) < 1e-6,
        str(result_response.summary.avgChillerLoadRate),
    )

    async with session_scope() as session:
        row = await session.get(SimulationTask, task_id)
        completed_at = row.completed_at
    check("完成后写入完成时间", completed_at is not None)

    # ---------- 4.1 项目随仿真完成出现在列表 ----------
    async with session_scope() as session:
        projects_now = await get_projects(admin, session)
    target = next((item for item in projects_now if item["id"] == project["id"]), None)
    check(
        "项目状态随仿真完成变为 completed",
        target is not None and target["status"] == "completed",
        str(target.get("status") if target else None),
    )
    check(
        "项目列表带最近任务与结果摘要",
        target is not None
        and (target.get("latestTask") or {}).get("taskId") == task_id
        and target.get("latestSummary") is not None
        and abs(target["latestSummary"]["totalEnergy"] - payload["summary"]["totalEnergy"]) < 1e-6,
        str(target.get("latestTask") if target else None),
    )

    # ---------- 4.2 未指定 projectId 时自动建项目 ----------
    auto_request = StartSimulationRequest(
        projectName="自动建项目检查",
        buildingType="office",
        area=15000.0,
        config=SimulationConfig(),
        data={"headers": headers, "rows": rows},
        dataMeta={"fileName": "auto.csv", "totalRows": len(rows)},
    )
    async with session_scope() as session:
        started = await start_simulation(auto_request, admin, session)

    deadline = time.time() + 180
    auto_task = None
    while time.time() < deadline:
        await asyncio.sleep(0.3)
        async with session_scope() as session:
            auto_task = await tasks_repo.get(session, started.taskId)
            if auto_task is not None and auto_task.status in ("completed", "failed"):
                break

    async with session_scope() as session:
        auto_projects = await get_projects(admin, session)
    auto_project = next(
        (item for item in auto_projects if item["name"] == "自动建项目检查"), None
    )
    check("未指定 projectId 时自动创建项目", auto_project is not None)
    check(
        "自动项目关联本次仿真任务",
        auto_project is not None
        and (auto_project.get("latestTask") or {}).get("taskId") == started.taskId,
        str(auto_project.get("latestTask") if auto_project else None),
    )
    check(
        "自动项目状态反映仿真完成",
        auto_project is not None
        and auto_project["status"] == "completed"
        and auto_task is not None
        and auto_task.status == "completed",
        f"project={auto_project['status'] if auto_project else None} "
        f"task={getattr(auto_task, 'status', None)}",
    )

    # ---------- 4.3 同名项目复用（不新建第二个项目） ----------
    reuse_request = StartSimulationRequest(
        projectName="自动建项目检查",
        buildingType="office",
        area=15000.0,
        config=SimulationConfig(),
        data={"headers": headers, "rows": rows},
        dataMeta={"fileName": "auto-reuse.csv", "totalRows": len(rows)},
    )
    async with session_scope() as session:
        reused = await start_simulation(reuse_request, admin, session)

    deadline = time.time() + 180
    reused_task = None
    while time.time() < deadline:
        await asyncio.sleep(0.3)
        async with session_scope() as session:
            reused_task = await tasks_repo.get(session, reused.taskId)
            if reused_task is not None and reused_task.status in ("completed", "failed"):
                break

    async with session_scope() as session:
        same_name_rows = (
            await session.execute(
                select(Project).where(
                    Project.owner_id == 1, Project.name == "自动建项目检查"
                )
            )
        ).scalars().all()
    async with session_scope() as session:
        first_task = await tasks_repo.get(session, auto_task.id) if auto_task is not None else None
        reused_row = await tasks_repo.get(session, reused.taskId)
    check(
        "同名项目复用（不新建第二个项目）",
        len(same_name_rows) == 1,
        f"projects={len(same_name_rows)}",
    )
    check(
        "同名两次仿真的任务挂在同一项目",
        first_task is not None
        and reused_row is not None
        and first_task.project_id is not None
        and first_task.project_id == reused_row.project_id
        and bool(same_name_rows)
        and first_task.project_id == same_name_rows[0].id,
        f"{getattr(first_task, 'project_id', None)} / {getattr(reused_row, 'project_id', None)} "
        f"/ {same_name_rows[0].id if same_name_rows else None}",
    )

    # ---------- 4.4 全年无冷机在线时该指标为 0（而非缺失或无穷大） ----------
    zero_headers = ["datetime", "load", "t_dry", "d"]
    zero_rows = [
        {
            "datetime": f"2025-01-0{day} {hour:02d}:00",
            "load": 0.0,
            "t_dry": 5.0,
            "d": 0.003,
        }
        for day in (1, 2)
        for hour in range(24)
    ]
    zero_request = StartSimulationRequest(
        projectName="无冷机在线检查",
        buildingType="office",
        area=10000.0,
        config=SimulationConfig(),
        data={"headers": zero_headers, "rows": zero_rows},
        dataMeta={"fileName": "zero-load.csv", "totalRows": len(zero_rows)},
    )
    async with session_scope() as session:
        zero_started = await start_simulation(zero_request, admin, session)

    deadline = time.time() + 180
    zero_task = None
    while time.time() < deadline:
        await asyncio.sleep(0.3)
        async with session_scope() as session:
            zero_task = await tasks_repo.get(session, zero_started.taskId)
            if zero_task is not None and zero_task.status in ("completed", "failed"):
                break
    async with session_scope() as session:
        zero_payload = await results_repo.load_payload(session, zero_started.taskId)
    zero_summary = (zero_payload or {}).get("summary") or {}
    check(
        "无冷机在线的仿真跑通",
        zero_task is not None and zero_task.status == "completed",
        f"{getattr(zero_task, 'status', None)} / {getattr(zero_task, 'error', None)}",
    )
    check(
        "全年无冷机在线时负荷率为 0（字段仍在）",
        "avgChillerLoadRate" in zero_summary
        and float(zero_summary.get("avgChillerLoadRate")) == 0.0
        and float(zero_summary.get("totalQStation") or 0.0) == 0.0,
        f"rate={zero_summary.get('avgChillerLoadRate')!r} q={zero_summary.get('totalQStation')!r}",
    )

    # ---------- 5.1 结果与终态原子性 ----------
    atomic_id = str(uuid.uuid4())
    async with session_scope() as session:
        await tasks_repo.create(
            session, task_id=atomic_id, user_id=1, project_name="原子性检查", area=1000.0
        )
        await tasks_repo.set_status(session, atomic_id, "running")
    async with session_scope() as session:
        try:
            # 集合无法序列化为 JSON，flush 时必然抛错
            await results_repo.save_with_status(
                session, atomic_id, {"summary": {}, "meta": {}, "bad": {1, 2}}
            )
            atomic_blocked = False
        except Exception:  # noqa: BLE001
            atomic_blocked = True
            await session.rollback()
    async with session_scope() as session:
        atomic_task = await tasks_repo.get(session, atomic_id)
        atomic_result = await results_repo.load_payload(session, atomic_id)
    check(
        "结果写入失败不回写完成态",
        atomic_blocked and atomic_task.status == "running" and atomic_result is None,
        f"blocked={atomic_blocked} status={getattr(atomic_task, 'status', None)} "
        f"result={atomic_result is not None}",
    )

    # ---------- 5.2 取消在计算中生效 ----------
    cancel_id = str(uuid.uuid4())
    cancel_headers, cancel_rows = load_rows(168)
    async with session_scope() as session:
        await tasks_repo.create(
            session, task_id=cancel_id, user_id=1, project_name="取消检查",
            area=AREA_PRIMARY, config=config, data_meta={"totalRows": len(cancel_rows)},
        )
    runner = asyncio.create_task(simulation_service.run_task(cancel_id, {
        "config": config,
        "data": {"rows": cancel_rows, "headers": cancel_headers},
        "projectName": "取消检查",
        "buildingType": "office",
        "area": AREA_PRIMARY,
        "dataMeta": {"totalRows": len(cancel_rows)},
    }))
    await asyncio.sleep(0.05)
    async with session_scope() as session:
        await tasks_repo.set_status(session, cancel_id, "cancelled")
    await runner
    async with session_scope() as session:
        cancel_task = await tasks_repo.get(session, cancel_id)
        cancel_result = await results_repo.load_payload(session, cancel_id)
    check(
        "取消后不会被改写为完成",
        cancel_task.status == "cancelled" and cancel_result is None,
        f"status={getattr(cancel_task, 'status', None)} result={cancel_result is not None}",
    )

    # ---------- 6. 并行任务结果隔离 ----------
    async def run_isolated(area: float, limit: int, offset: int = 0):
        local_headers, local_rows = load_rows(limit, offset)
        local_task_id = str(uuid.uuid4())
        async with session_scope() as session:
            await tasks_repo.create(
                session, task_id=local_task_id, user_id=1, project_name=f"并发-{int(area)}",
                building_type="office", area=area,
                config=config, data_meta={"totalRows": len(local_rows)},
            )
        await simulation_service.run_task(
            local_task_id,
            {
                "config": config,
                "data": {"rows": local_rows, "headers": local_headers},
                "projectName": f"并发-{int(area)}",
                "buildingType": "office",
                "area": area,
                "dataMeta": {"totalRows": len(local_rows)},
            },
        )
        async with session_scope() as session:
            return await results_repo.load_payload(session, local_task_id)

    # 取夏季两段不同数据，保证能耗非零，才能验证"结果没有互相覆盖"
    payload_a, payload_b = await asyncio.gather(
        run_isolated(100000.0, 48, 4000), run_isolated(200000.0, 48, 5000)
    )
    energy_a = payload_a["summary"]["totalEnergy"]
    energy_b = payload_b["summary"]["totalEnergy"]
    check(
        "并行任务各自记录自己的面积",
        payload_a["summary"]["area"] == 100000.0 and payload_b["summary"]["area"] == 200000.0,
        f"{payload_a['summary']['area']} / {payload_b['summary']['area']}",
    )
    check(
        "并行任务结果互不覆盖",
        energy_a > 0
        and energy_b > 0
        and energy_a != energy_b
        and payload_a["meta"]["startTime"] != payload_b["meta"]["startTime"],
        f"energy={energy_a} / {energy_b}; start={payload_a['meta']['startTime']} / {payload_b['meta']['startTime']}",
    )

    # ---------- 7. 报告：生成 / 索引 / 下载 ----------
    async with session_scope() as session:
        generated = await generate_report(task_id, admin, session)
        report_id = generated["reportId"]
        report_dir = Path(settings.reports_dir) / report_id
        report_row = await reports_repo.get(session, report_id)
        listed = await list_reports(task_id, admin, session)
        meta = await get_report_meta(report_id, admin, session)
        download = await download_report(report_id, admin, session)
        html_bytes_first = Path(download.path).read_bytes()
        download2 = await download_report(report_id, admin, session)
        html_bytes_second = Path(download2.path).read_bytes()

    check("报告产物三件套齐全", all((report_dir / name).is_file() for name in ("report.html", "result.json", "meta.json")), str(report_dir))
    check("报告索引写入并带校验和", report_row is not None and report_row.html_sha256 == hashlib.sha256(html_bytes_first).hexdigest())
    check("报告列表按任务返回", listed["total"] == 1 and listed["reports"][0]["reportId"] == report_id, str(listed))
    check("报告元信息可读", meta.get("reportId") == report_id and meta.get("caliberVersion") == "v2", str(meta.get("reportId")))
    check("下载返回文件响应且字节稳定", isinstance(download, FileResponse) and html_bytes_first == html_bytes_second)

    # 历史报告的 task 行已不存在，但按报告归属仍应能列出
    async with session_scope() as session:
        legacy_meta = await get_report_meta(legacy_ids[0], admin, session) if legacy_ids else {}
        legacy_task_id = legacy_meta.get("taskId")
        legacy_list = await list_reports(legacy_task_id, admin, session) if legacy_task_id else {"total": 0}
    check(
        "历史报告可按任务列出（task 行不存在）",
        legacy_list.get("total", 0) >= 1,
        str(legacy_list),
    )

    # ---------- 8. 数据被篡改后拒绝复现 ----------
    original = dataset_path.read_bytes()
    dataset_path.write_bytes(original + b" ")
    async with session_scope() as session:
        try:
            await datasets_repo.load_document(session, dataset_id)
            tamper_blocked = False
        except datasets_repo.DatasetIntegrityError:
            tamper_blocked = True
    dataset_path.write_bytes(original)
    check("篡改数据集被拒绝复现", tamper_blocked)

    # ---------- 8.1 迁移 v2：一次性回填历史任务的项目关联 ----------
    from app.db.migrations.v2_backfill_project_links import upgrade as backfill_upgrade

    orphan_task_id = str(uuid.uuid4())
    async with session_scope() as session:
        await tasks_repo.create(
            session, task_id=orphan_task_id, user_id=1,
            project_name="历史未关联项目", building_type="office", area=8000.0,
            config=config, data_meta={"totalRows": 1},
        )
        await tasks_repo.set_status(session, orphan_task_id, "failed", error="历史任务")

    # 直接跑迁移体（等价于启动时执行 v2），跑两次验证幂等
    async with get_engine().begin() as conn:
        await backfill_upgrade(conn)
    async with get_engine().begin() as conn:
        await backfill_upgrade(conn)

    async with session_scope() as session:
        orphan_task = await tasks_repo.get(session, orphan_task_id)
        orphan_project = (
            await projects_repo.get(session, orphan_task.project_id)
            if orphan_task and orphan_task.project_id else None
        )
        same_name = (
            await session.execute(
                select(Project).where(
                    Project.owner_id == 1, Project.name == "历史未关联项目"
                )
            )
        ).scalars().all()
    check(
        "历史任务由 v2 迁移回填项目关联",
        orphan_project is not None
        and orphan_project.name == "历史未关联项目"
        and orphan_project.status == "failed",
        f"project={getattr(orphan_project, 'name', None)} "
        f"status={getattr(orphan_project, 'status', None)}",
    )
    check("迁移 v2 幂等（不重复建项目）", len(same_name) == 1, str(len(same_name)))

    # ---------- 9. 模拟重启：状态恢复 + 中断收敛 ----------
    running_task_id = str(uuid.uuid4())
    async with session_scope() as session:
        await tasks_repo.create(
            session, task_id=running_task_id, user_id=1, project_name="中断任务",
            building_type="office", area=AREA_PRIMARY, config=config,
            data_meta={"totalRows": 1},
        )
        await tasks_repo.set_status(session, running_task_id, "running", progress=42)

    payload_before_restart = payload
    await dispose_engine()
    state_restart = await startup()

    async with session_scope() as session:
        task_after = await tasks_repo.get(session, task_id)
        payload_after = await results_repo.load_payload(session, task_id)
        interrupted_after = await tasks_repo.get(session, running_task_id)
        reports_after = await list_reports(task_id, admin, session)
        legacy_after = await get_report_meta(legacy_ids[0], admin, session) if legacy_ids else None

    check("重启后任务仍为完成", task_after is not None and task_after.status == "completed", str(getattr(task_after, "status", None)))
    check("重启后结果逐字段一致", payload_after == payload_before_restart)
    check("重启后报告列表仍可读", reports_after["total"] == 1, str(reports_after))
    check("重启后历史报告仍可读", legacy_ids and legacy_after and legacy_after.get("reportId") == legacy_ids[0])
    check(
        "重启收敛中断任务为失败并写明原因",
        interrupted_after is not None
        and interrupted_after.status == "failed"
        and "服务重启中断" in (interrupted_after.error or ""),
        f"{getattr(interrupted_after, 'status', None)} / {getattr(interrupted_after, 'error', None)}",
    )

    # ---------- 10. 重新仿真：从留存数据回读 ----------
    async with session_scope() as session:
        restarted = await restart_simulation(task_id, admin, session)
    check("重新仿真复位为 pending", restarted.status.value == "pending", restarted.status.value)

    deadline = time.time() + 300
    final_status = None
    while time.time() < deadline:
        await asyncio.sleep(0.5)
        async with session_scope() as session:
            current = await tasks_repo.get(session, task_id)
            final_status = current.status if current else None
            payload_restart = await results_repo.load_payload(session, task_id)
        if final_status in ("completed", "failed", "cancelled"):
            break
    check("重新仿真完成", final_status == "completed", str(final_status))
    check(
        "重新仿真复用留存数据",
        bool(payload_restart) and payload_restart["meta"].get("totalRows") == len(rows),
        str((payload_restart or {}).get("meta", {}).get("totalRows")),
    )
    check(
        "重新仿真时间轴未被打乱",
        bool(payload_restart)
        and payload_restart["meta"].get("startTime") == payload_before_restart["meta"].get("startTime")
        and payload_restart["meta"].get("weeks") == payload_before_restart["meta"].get("weeks"),
        f"{ (payload_restart or {}).get('meta', {}).get('startTime') } vs {payload_before_restart['meta'].get('startTime')}",
    )

    # ---------- 11. 报告产物缺失时明确失败 ----------
    victim = legacy_ids[0]
    victim_html = Path(settings.reports_dir) / victim / "report.html"
    victim_backup = victim_html.read_bytes()
    victim_html.unlink()
    async with session_scope() as session:
        try:
            await download_report(victim, admin, session)
            missing_status = None
        except HTTPException as exc:
            missing_status = exc.status_code
            missing_detail = exc.detail
        victim_row = await reports_repo.get(session, victim)
    victim_html.write_bytes(victim_backup)
    check("产物缺失时下载返回 404", missing_status == 404, str(missing_status))
    check("产物缺失时说明原因", "产物缺失" in str(locals().get("missing_detail", "")), str(locals().get("missing_detail")))
    check("产物缺失时索引标记 missing", victim_row is not None and victim_row.artifact_state == "missing", str(getattr(victim_row, "artifact_state", None)))

    # ---------- 12. 索引写入失败时清理产物 ----------
    await asyncio.sleep(1.1)  # 报告 id 精确到秒，错开一秒避免撞名
    dirs_before = {p.name for p in Path(settings.reports_dir).iterdir() if p.is_dir()}
    original_insert = reports_routes.reports_repo.insert

    async def _failing_insert(*args, **kwargs):
        raise RuntimeError("inject index failure")

    reports_routes.reports_repo.insert = _failing_insert
    try:
        async with session_scope() as session:
            try:
                await generate_report(task_id, admin, session)
                index_failure = None
            except HTTPException as exc:
                index_failure = exc
    finally:
        reports_routes.reports_repo.insert = original_insert
    dirs_after = {p.name for p in Path(settings.reports_dir).iterdir() if p.is_dir()}
    check(
        "索引写入失败返回 500",
        index_failure is not None and index_failure.status_code == 500,
        str(index_failure),
    )
    check(
        "索引失败时清理本次产物",
        dirs_before == dirs_after,
        f"before={len(dirs_before)} after={len(dirs_after)}",
    )

    # ---------- 12.1 删除项目（仿真任务与结果保留） ----------
    from app.api.routes.projects import delete_project

    async with session_scope() as session:
        temp_project = await projects_repo.create(
            session, owner_id=1, name="待删除项目", area=1000.0
        )
        temp_project_id = temp_project.id
    async with session_scope() as session:
        deleted = await delete_project(temp_project_id, admin, session)
    async with session_scope() as session:
        still_there = await projects_repo.get(session, temp_project_id)
    check(
        "删除项目后不再出现在列表",
        deleted.get("projectId") == temp_project_id and still_there is None,
        str(deleted),
    )

    # ---------- 12.2 删除后重启不复活（一次性回填，design D1/D2） ----------
    zombie_task_id = str(uuid.uuid4())
    async with session_scope() as session:
        zombie_project = await projects_repo.create(
            session, owner_id=1, name="重启不复活检查", area=1200.0
        )
        zombie_project_id = zombie_project.id
        await tasks_repo.create(
            session,
            task_id=zombie_task_id,
            user_id=1,
            project_id=zombie_project_id,
            project_name="重启不复活检查",
            area=1200.0,
        )
        await tasks_repo.set_status(session, zombie_task_id, "completed")
    async with session_scope() as session:
        await delete_project(zombie_project_id, admin, session)

    async with session_scope() as session:
        links_before = await tasks_repo.list_for_user(session, 1, True)
        null_before = sum(1 for row in links_before if row.project_id is None and row.project_name)
    state_zombie = await startup()
    async with session_scope() as session:
        revived = await projects_repo.get_by_name(session, 1, "重启不复活检查")
        zombie_task = await tasks_repo.get(session, zombie_task_id)
        links_after = await tasks_repo.list_for_user(session, 1, True)
        null_after = sum(1 for row in links_after if row.project_id is None and row.project_name)
    check("删除后重启项目不复活", revived is None, str(revived))
    check(
        "删除后任务保持未关联",
        zombie_task is not None and zombie_task.project_id is None,
        str(getattr(zombie_task, "project_id", None)),
    )
    check(
        "启动不再回填（未关联任务数不变）",
        null_before == null_after and state_zombie["migrated"] == [],
        f"{null_before}->{null_after} migrated={state_zombie['migrated']}",
    )

    # ---------- 12.3 删除拒绝：运行中任务不是最新那条（design D3） ----------
    async with session_scope() as session:
        busy_project = await projects_repo.create(
            session, owner_id=1, name="删除拒绝检查", area=900.0
        )
        busy_project_id = busy_project.id
        await tasks_repo.create(
            session,
            task_id=str(uuid.uuid4()),
            user_id=1,
            project_id=busy_project_id,
            project_name="删除拒绝检查",
        )
    await asyncio.sleep(0.02)
    async with session_scope() as session:
        newer_id = str(uuid.uuid4())
        await tasks_repo.create(
            session,
            task_id=newer_id,
            user_id=1,
            project_id=busy_project_id,
            project_name="删除拒绝检查",
        )
        await tasks_repo.set_status(session, newer_id, "completed")
    async with session_scope() as session:
        try:
            await delete_project(busy_project_id, admin, session)
            busy_status = None
        except HTTPException as exc:
            busy_status = exc.status_code
    check("运行中任务不是最新时仍拒绝删除", busy_status == 409, str(busy_status))

    # ---------- 13. 关闭自动迁移且缺结构时拒绝启动 ----------
    gate_engine = create_async_engine(
        f"sqlite+aiosqlite:///{(TMP / 'empty_gate.db').as_posix()}"
    )
    try:
        try:
            await ensure_schema_ready(gate_engine)
            gate_error = None
        except RuntimeError as exc:
            gate_error = str(exc)
    finally:
        await gate_engine.dispose()
    check(
        "缺结构且关闭自动迁移时拒绝启动",
        gate_error is not None and "结构不完整" in gate_error,
        str(gate_error),
    )

    # ---------- 14. 存储不可用时明确失败 ----------
    blocker = TMP / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    try:
        ensure_storage_dirs(Settings(DATA_DIR=blocker))
        storage_error = None
    except RuntimeError as exc:
        storage_error = str(exc)
    check(
        "存储目录不可用时以可读错误失败",
        storage_error is not None and "存储目录" in storage_error,
        str(storage_error),
    )

    # ---------- 汇总 ----------
    await dispose_engine()
    failures = [item for item in RESULTS if not item[1]]
    print("-" * 60)
    print(f"共 {len(RESULTS)} 项断言，通过 {len(RESULTS) - len(failures)} 项，失败 {len(failures)} 项")
    if failures:
        print("失败项：")
        for name, _, detail in failures:
            print(f"  - {name} :: {detail}")
        print(f"临时目录保留用于排查: {TMP}")
        return 1
    shutil.rmtree(TMP, ignore_errors=True)
    print("全部通过，临时目录已清理")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
