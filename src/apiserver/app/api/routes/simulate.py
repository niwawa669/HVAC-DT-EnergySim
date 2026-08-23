import asyncio

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any
from datetime import datetime
import uuid

from app.models.schemas import (
    StartSimulationRequest,
    TaskResponse,
    TaskStatus,
    SimulationResultResponse,
    SimulationSummary,
    WeeklyData
)
from app.services.simulation_service import simulation_service
from app.api.deps import get_current_user

router = APIRouter(prefix="/simulate", tags=["simulation"])


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
            "project_name": request_dict.get("projectName"),
            "building_type": request_dict.get("buildingType"),
            "area": request_dict.get("area", 2931.0),
            "user_id": current_user.get("id"),
            "result": None,
            "error": None
        }
        
        print(f"🚀 创建仿真任务: {task_id}")
        
        # ===== 使用 BackgroundTasks 替代 asyncio.create_task =====
        background_tasks.add_task(
            simulation_service._run_simulation_task,
            task_id,
            request_dict
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
    
    if status["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="任务已完成或已取消")
    
    success = simulation_service.cancel_task(task_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="取消任务失败")
    
    return {"message": "仿真已取消", "taskId": task_id}


@router.get("/results/{task_id}", response_model=SimulationResultResponse)
async def get_simulation_results(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """获取仿真结果"""
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = status.get("result")
    
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")
    
    return SimulationResultResponse(
        taskId=task_id,
        projectId=1,
        summary=SimulationSummary(**result["summary"]),
        weeklyData=[WeeklyData(**item) for item in result["weekly_data"]],
        createdAt=status.get("started_at", datetime.now().isoformat())
    )


@router.get("/list")
async def list_simulations(
    current_user: Dict = Depends(get_current_user)
):
    """获取用户的所有仿真任务"""
    tasks = simulation_service.list_user_tasks(current_user.get("id", 1))
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/restart/{task_id}", response_model=TaskResponse)
async def restart_simulation(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """重新仿真 - 使用相同的任务ID重新计算"""
    try:
        # 检查任务是否存在
        status = simulation_service.get_task_status(task_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 检查用户权限
        if status.get("user_id") != current_user.get("id"):
            if current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="无权操作此任务")
        
        # 重置任务状态
        simulation_service.reset_task(task_id)
        
        # 获取原始数据
        request_data = {
            "config": status.get("config"),
            "data": status.get("data"),
            "projectName": status.get("project_name"),
            "buildingType": status.get("building_type"),
            "area": status.get("area", 2931.0)
        }
        
        # 重新启动仿真
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