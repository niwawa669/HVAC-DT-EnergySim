from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any
from datetime import datetime
import uuid
import asyncio

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
from app.services.simulation_service import simulation_service
from app.services.algorithm_wrapper import algorithm_wrapper
from app.api.deps import get_current_user

router = APIRouter(prefix="/simulate", tags=["simulation"])

HISTOGRAM_BINS = 10


def _normalise_histogram(raw) -> list:
    """把负荷率分布规范为长度 10 的整数列表（D8）。

    缺失或非法输入一律回落为 10 个 0，保证字段长度恒定、消费方无需做存在性判断。
    """
    try:
        values = [int(round(float(v))) for v in (raw or [])]
    except (TypeError, ValueError):
        values = []
    values = [max(0, v) for v in values][:HISTOGRAM_BINS]
    return values + [0] * (HISTOGRAM_BINS - len(values))


@router.post("/start", response_model=TaskResponse)
async def start_simulation(
    request: StartSimulationRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """启动仿真任务"""
    try:
        request_dict = request.model_dump()
        task_id = str(uuid.uuid4())

        # 6.5：参数未映射时在启动前拒绝，并指名参数
        try:
            algorithm_wrapper.validate_config(request_dict.get("config"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        
        # 初始化任务状态
        simulation_service.tasks[task_id] = {
            "status": "pending",
            "progress": 0,
            "current_week": 0,
            "total_weeks": 52,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "config": request_dict.get("config"),
            "data": request_dict.get("data"),
            "data_meta": request_dict.get("dataMeta"),
            "project_name": request_dict.get("projectName"),
            "building_type": request_dict.get("buildingType"),
            "area": request_dict.get("area", 2931.0),
            "user_id": current_user.get("id"),
            "result": None,
            "error": None
        }
        
        print(f"🚀 创建仿真任务: {task_id}")
        print(f"📋 配置参数: 大机 {request_dict.get('config', {}).get('Qr_chiller_BCH')} kW, "
              f"小机 {request_dict.get('config', {}).get('Qr_chiller_SCH')} kW")
        
        asyncio.create_task(
            simulation_service._run_simulation_task(task_id, request_dict)
        )
        
        return TaskResponse(
            taskId=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            currentWeek=0,
            totalWeeks=52,
            message="仿真任务已启动"
        )
        
    except Exception as e:
        print(f"❌ 启动仿真失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_simulation_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """获取仿真任务状态"""
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if status.get("user_id") != current_user.get("id"):
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return TaskResponse(
        taskId=task_id,
        status=TaskStatus(status["status"]),
        progress=status.get("progress", 0),
        currentWeek=status.get("current_week", 0),
        totalWeeks=status.get("total_weeks", 52),
        startedAt=status.get("started_at"),
        updatedAt=status.get("updated_at"),
        message=status.get("error")
    )


@router.post("/cancel/{task_id}")
async def cancel_simulation(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """取消仿真任务"""
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if status.get("user_id") != current_user.get("id"):
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权操作此任务")
    
    if status["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="任务已完成或已取消")
    
    success = simulation_service.cancel_task(task_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="取消任务失败")
    
    asyncio.create_task(
        simulation_service._send_websocket_message(task_id, {
            "type": "cancelled",
            "message": "仿真任务已取消"
        })
    )
    
    return {"message": "仿真已取消", "taskId": task_id}


@router.post("/restart/{task_id}", response_model=TaskResponse)
async def restart_simulation(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """重新仿真 - 使用相同的任务ID重新计算"""
    try:
        status = simulation_service.get_task_status(task_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if status.get("user_id") != current_user.get("id"):
            if current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="无权操作此任务")
        
        simulation_service.reset_task(task_id)
        
        request_data = {
            "config": status.get("config"),
            "data": status.get("data"),
            "projectName": status.get("project_name"),
            "buildingType": status.get("building_type"),
            "area": status.get("area", 2931.0)
        }
        
        asyncio.create_task(
            simulation_service._run_simulation_task(task_id, request_data)
        )
        
        return TaskResponse(
            taskId=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            currentWeek=0,
            totalWeeks=52,
            message="仿真已重新启动"
        )
        
    except Exception as e:
        print(f"❌ 重新仿真失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{task_id}", response_model=SimulationResultResponse)
async def get_simulation_results(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """获取仿真结果"""
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if status.get("user_id") != current_user.get("id"):
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权访问此任务")
    
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = status.get("result")

    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")

    summary = result.get("summary", {})
    weekly_data = result.get("weekly_data", [])
    monthly_data = result.get("monthly_data", [])
    meta = result.get("meta", {})

    def _bd(d):
        d = d or {}
        return EnergyBreakdown(chiller=d.get("chiller", 0), pump_chw=d.get("pump_chw", 0),
                               pump_cw=d.get("pump_cw", 0), tower=d.get("tower", 0))

    breakdown = _bd(summary.get("breakdown"))
    peak = summary.get("peakContext") or {}

    # 七个区块始终存在，无数据时以空集合或零值表达（D4 / 7.1）
    return SimulationResultResponse(
        taskId=task_id,
        projectId=1,
        createdAt=status.get("started_at", datetime.now().isoformat()),
        meta=SimulationMeta(**{k: meta[k] for k in meta if k in SimulationMeta.model_fields}),
        summary=SimulationSummary(
            totalEnergy=summary.get("totalEnergy", 0),
            totalCoolingLoad=summary.get("totalCoolingLoad", 0),
            totalQStation=summary.get("totalQStation", 0),
            peakCoolingLoad=summary.get("peakCoolingLoad", 0),
            eui=summary.get("eui", 0),
            avgCop=summary.get("avgCop", 0),
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
    current_user: Dict = Depends(get_current_user)
):
    """获取用户的所有仿真任务列表"""
    tasks = []
    for task_id, status in simulation_service.tasks.items():
        if status.get("user_id") == current_user.get("id") or current_user.get("role") == "admin":
            tasks.append({
                "taskId": task_id,
                "status": status.get("status"),
                "progress": status.get("progress", 0),
                "projectName": status.get("project_name"),
                "startedAt": status.get("started_at"),
                "updatedAt": status.get("updated_at")
            })
    
    tasks.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
    
    return {
        "tasks": tasks,
        "total": len(tasks)
    }