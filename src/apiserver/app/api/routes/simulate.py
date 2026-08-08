from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from typing import Dict, Any
import json

from app.models.schemas import (
    StartSimulationRequest,
    TaskResponse,
    TaskStatus,
    SimulationResultResponse
)
from app.services.simulation_service import simulation_service
from app.api.deps import get_current_user

router = APIRouter(prefix="/simulate", tags=["simulation"])

@router.post("/start", response_model=TaskResponse)
async def start_simulation(
    request: StartSimulationRequest,
    current_user: Dict = Depends(get_current_user)
):
    """启动仿真任务"""
    try:
        # 转换为字典
        request_dict = request.model_dump()
        
        # 启动仿真
        task_id = await simulation_service.start_simulation(request_dict)
        
        return TaskResponse(
            taskId=task_id,
            status=TaskStatus.RUNNING,
            progress=0,
            currentWeek=0,
            totalWeeks=52,
            message="仿真已启动"
        )
    except Exception as e:
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
        totalWeeks=52,
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
    success = simulation_service.cancel_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或已完成")
    
    return {"message": "仿真已取消"}

@router.get("/results/{task_id}", response_model=SimulationResultResponse)
async def get_simulation_results(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """获取仿真结果"""
    result = simulation_service.get_task_result(task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在或任务未完成")
    
    return SimulationResultResponse(
        taskId=task_id,
        projectId=1,
        summary=result["summary"],
        weeklyData=result["weeklyData"],
        createdAt=datetime.now()
    )