from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.schemas import (
    StartSimulationRequest,
    TaskResponse,
    TaskStatus,
    SimulationResultResponse,
    SimulationSummary,
    SimulationMeta,
    WeeklyData,
    MonthlyData,
    EnergyBreakdown,
    PeakContext,
    UnmetHour,
)
from app.repositories import datasets as datasets_repo
from app.repositories import projects as projects_repo
from app.repositories import results as results_repo
from app.repositories import tasks as tasks_repo
from app.services.algorithm_wrapper import algorithm_wrapper
from app.services.simulation_service import simulation_service

router = APIRouter(prefix="/simulate", tags=["simulation"])

HISTOGRAM_BINS = 10
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def _normalise_histogram(raw) -> list:
    """把负荷率分布规范为长度 10 的整数列表（D8）。"""
    try:
        values = [int(round(float(v))) for v in (raw or [])]
    except (TypeError, ValueError):
        values = []
    values = [max(0, v) for v in values][:HISTOGRAM_BINS]
    return values + [0] * (HISTOGRAM_BINS - len(values))


async def _get_task_or_404(
    db: AsyncSession, task_id: str, current_user: Dict, action: str = "访问"
):
    task = await tasks_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail=f"无权{action}此任务")
    return task


def _task_response(task) -> TaskResponse:
    return TaskResponse(
        taskId=task.id,
        status=TaskStatus(task.status),
        progress=task.progress,
        currentWeek=task.current_week,
        totalWeeks=task.total_weeks,
        startedAt=task.started_at,
        updatedAt=task.updated_at,
        message=task.error,
    )


@router.post("/start", response_model=TaskResponse)
async def start_simulation(
    request: StartSimulationRequest,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启动仿真任务：留存输入数据 + 任务落库，再交给后台执行。"""
    try:
        request_dict = request.model_dump(mode="json")

        # 6.5：参数未映射时在启动前拒绝，并指名参数
        try:
            algorithm_wrapper.validate_config(request_dict.get("config"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        data = request_dict.get("data") or {}
        rows = data.get("rows") or []
        if not rows:
            raise HTTPException(status_code=400, detail="数据不能为空")
        headers = data.get("headers") or list(rows[0].keys())
        time_column = data.get("timeColumn") or (headers[0] if headers else None)

        # 先确定项目归属，避免校验失败时已经在磁盘留下数据文件。
        # 未显式传 projectId 时，按（owner, 项目名）自动创建/复用项目，
        # 否则"完成一次仿真"在项目列表里永远看不到。
        project_id = request_dict.get("projectId")
        if project_id is not None:
            project = await projects_repo.get(db, int(project_id))
            if project is None:
                raise HTTPException(status_code=404, detail="项目不存在")
            if project.owner_id != current_user.get("id") and current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="无权在该项目下创建任务")
        else:
            project = await projects_repo.get_or_create_for_simulation(
                db,
                owner_id=current_user.get("id"),
                name=request.projectName,
                building_type=request_dict.get("buildingType"),
                area=request.area,
            )
            project_id = project.id

        await projects_repo.update_status(db, project, "pending")

        data_meta = dict(request_dict.get("dataMeta") or {})
        dataset = await datasets_repo.save_from_rows(
            db,
            rows=rows,
            headers=headers,
            time_column=time_column,
            filename=data_meta.get("fileName"),
            uploaded_by=current_user.get("id"),
        )

        task_id = str(uuid.uuid4())
        data_meta["datasetId"] = dataset.id
        data_meta.setdefault("sha256", dataset.sha256)
        data_meta.setdefault("totalRows", len(rows))

        await tasks_repo.create(
            db,
            task_id=task_id,
            user_id=current_user.get("id"),
            project_id=int(project_id),
            dataset_id=dataset.id,
            project_name=request.projectName,
            building_type=request_dict.get("buildingType"),
            area=request.area,
            config=request_dict.get("config"),
            data_meta=data_meta,
        )
        # 先提交，确保后台任务能读到自己这一行
        await db.commit()

        print(f"🚀 创建仿真任务: {task_id}")
        simulation_service.start_task(task_id, request_dict)

        return TaskResponse(
            taskId=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            currentWeek=0,
            totalWeeks=52,
            message="仿真任务已启动",
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 启动仿真失败: {exc}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_simulation_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取仿真任务状态。"""
    task = await _get_task_or_404(db, task_id, current_user)
    return _task_response(task)


@router.post("/cancel/{task_id}")
async def cancel_simulation(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消仿真任务。"""
    task = await _get_task_or_404(db, task_id, current_user, action="操作")

    if task.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="任务已完成或已取消")

    await tasks_repo.set_status(db, task_id, "cancelled")
    await db.commit()

    await simulation_service._send_websocket_message(task_id, {
        "type": "cancelled",
        "message": "仿真任务已取消",
    })

    return {"message": "仿真已取消", "taskId": task_id}


@router.post("/restart/{task_id}", response_model=TaskResponse)
async def restart_simulation(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新仿真：从留存数据集回读输入，使用相同任务 ID 重算。"""
    try:
        task = await _get_task_or_404(db, task_id, current_user, action="操作")

        if not task.dataset_id:
            raise HTTPException(status_code=400, detail="任务缺少留存输入数据，无法重新仿真")

        try:
            _, document = await datasets_repo.load_document(db, task.dataset_id)
        except datasets_repo.DatasetError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        request_data = {
            "config": task.config,
            "data": {
                "rows": document.get("rows") or [],
                "headers": document.get("headers") or [],
                "timeColumn": document.get("timeColumn"),
            },
            "projectName": task.project_name,
            "buildingType": task.building_type,
            "area": task.area if task.area else 2931000.0,
            "dataMeta": task.data_meta or {},
        }

        await tasks_repo.reset_for_restart(db, task_id)
        await db.commit()

        simulation_service.start_task(task_id, request_data)

        return TaskResponse(
            taskId=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            currentWeek=0,
            totalWeeks=52,
            message="仿真已重新启动",
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 重新仿真失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/results/{task_id}", response_model=SimulationResultResponse)
async def get_simulation_results(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取仿真结果（七区块）。"""
    task = await _get_task_or_404(db, task_id, current_user)

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    result = await results_repo.load_payload(db, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")

    summary = result.get("summary") or {}
    weekly_data = result.get("weekly_data") or []
    monthly_data = result.get("monthly_data") or []
    meta = result.get("meta") or {}

    def _bd(item):
        item = item or {}
        return EnergyBreakdown(
            chiller=item.get("chiller", 0),
            pump_chw=item.get("pump_chw", 0),
            pump_cw=item.get("pump_cw", 0),
            tower=item.get("tower", 0),
        )

    breakdown = _bd(summary.get("breakdown"))
    peak = summary.get("peakContext") or {}

    # 七个区块始终存在，无数据时以空集合或零值表达（D4 / 7.1）
    return SimulationResultResponse(
        taskId=task_id,
        projectId=task.project_id or 0,
        createdAt=task.started_at.isoformat() if task.started_at else datetime.now().isoformat(),
        meta=SimulationMeta(**{k: meta[k] for k in meta if k in SimulationMeta.model_fields}),
        summary=SimulationSummary(
            totalEnergy=summary.get("totalEnergy", 0),
            totalCoolingLoad=summary.get("totalCoolingLoad", 0),
            totalQStation=summary.get("totalQStation", 0),
            peakCoolingLoad=summary.get("peakCoolingLoad", 0),
            eui=summary.get("eui", 0),
            avgCop=summary.get("avgCop", 0),
            avgChillerLoadRate=summary.get("avgChillerLoadRate", 0),
            systemEER=summary.get("systemEER", 0),
            totalUnmet=summary.get("totalUnmet", 0),
            unmetHours=summary.get("unmetHours", 0),
            totalUnservedOff=summary.get("totalUnservedOff", 0),
            carbonEmission=summary.get("carbonEmission", 0),
            area=summary.get("area", 0),
        ),
        weekly=[WeeklyData(
            weekNumber=w.get("weekNumber", 0),
            weekLabel=w.get("weekLabel"),
            weekStart=w.get("weekStart"),
            weekEnd=w.get("weekEnd"),
            hours=w.get("hours", 0),
            totalCoolingLoad=w.get("totalCoolingLoad", 0),
            peakCoolingLoad=w.get("peakCoolingLoad", 0),
            totalQStation=w.get("totalQStation", 0),
            totalEnergyConsumption=w.get("totalEnergyConsumption", 0),
            avgSystemCop=w.get("avgSystemCop", 0),
            avgChillerCop=w.get("avgChillerCop", 0),
            avgOutdoorTemp=w.get("avgOutdoorTemp", 0),
            breakdown=_bd(w.get("breakdown")),
            supplyGap=w.get("supplyGap", 0),
            unservedWhenOff=w.get("unservedWhenOff", 0),
            unmetHours=w.get("unmetHours", 0),
            progressPercentage=w.get("progressPercentage", 0),
        ) for w in weekly_data],
        monthly=[MonthlyData(
            month=m.get("month"),
            hours=m.get("hours", 0),
            totalCoolingLoad=m.get("totalCoolingLoad", 0),
            totalQStation=m.get("totalQStation", 0),
            totalEnergyConsumption=m.get("totalEnergyConsumption", 0),
            avgChillerCop=m.get("avgChillerCop", 0),
            systemEER=m.get("systemEER", 0),
            breakdown=_bd(m.get("breakdown")),
            supplyGap=m.get("totalUnmet", 0),
        ) for m in monthly_data],
        breakdown=breakdown,
        operating_stats=summary.get("operatingStats") or {},
        load_rate_histogram=_normalise_histogram(summary.get("loadRateHistogram")),
        unmet_hours_detail=[
            UnmetHour(**{k: u.get(k) for k in UnmetHour.model_fields})
            for u in (result.get("unmet_hours_detail") or [])
        ],
        peak_context=PeakContext(
            timestamp=peak.get("timestamp"),
            load=peak.get("load", 0),
            loadUnit=peak.get("loadUnit", "kW"),
            temperature=peak.get("temperature"),
            humid=peak.get("humid"),
            qStation=peak.get("qStation", 0),
            chillerCOP=peak.get("chillerCOP", 0),
            systemEER=peak.get("systemEER", 0),
            loadRate=peak.get("loadRate", 0),
            nSCH=peak.get("nSCH", 0),
            nBCH=peak.get("nBCH", 0),
        ),
    )


@router.get("/list")
async def list_simulations(
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的所有仿真任务列表。"""
    rows = await tasks_repo.list_for_user(
        db, current_user.get("id"), current_user.get("role") == "admin"
    )
    tasks = [tasks_repo.summarize(task) for task in rows]
    return {"tasks": tasks, "total": len(tasks)}
