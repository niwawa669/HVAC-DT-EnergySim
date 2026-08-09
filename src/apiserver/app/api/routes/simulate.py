from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import asyncio
import json

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
from app.websocket.manager import websocket_manager

router = APIRouter(prefix="/simulate", tags=["simulation"])


@router.post("/start", response_model=TaskResponse)
async def start_simulation(
    request: StartSimulationRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """
    启动仿真任务
    
    接收项目配置和数据，启动异步仿真计算
    """
    try:
        # 转换请求为字典
        request_dict = request.model_dump()
        
        # 生成任务ID
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
            "area": request_dict.get("area"),
            "user_id": current_user.get("id"),
            "result": None,
            "error": None
        }
        
        # 将任务添加到后台队列
        background_tasks.add_task(
            run_simulation_task,
            task_id,
            request_dict,
            current_user
        )
        
        return TaskResponse(
            taskId=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            currentWeek=0,
            totalWeeks=52,
            message="仿真任务已添加到队列"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_simulation_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取仿真任务状态
    """
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查用户权限
    if status.get("user_id") != current_user.get("id"):
        # 管理员可以查看所有任务
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
    """
    取消仿真任务
    """
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查用户权限
    if status.get("user_id") != current_user.get("id"):
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权操作此任务")
    
    if status["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="任务已完成或已取消")
    
    success = simulation_service.cancel_task(task_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="取消任务失败")
    
    # 通过 WebSocket 通知
    await websocket_manager.send_message(task_id, {
        "type": "cancelled",
        "message": "仿真任务已取消"
    })
    
    return {"message": "仿真已取消", "taskId": task_id}


@router.get("/results/{task_id}", response_model=SimulationResultResponse)
async def get_simulation_results(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """
    获取仿真结果
    """
    status = simulation_service.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查用户权限
    if status.get("user_id") != current_user.get("id"):
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权访问此任务")
    
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = status.get("result")
    
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")
    
    return SimulationResultResponse(
        taskId=task_id,
        projectId=1,  # 实际项目中从数据库获取
        summary=SimulationSummary(**result["summary"]),
        weeklyData=[WeeklyData(**item) for item in result["weekly_data"]],
        createdAt=status.get("started_at", datetime.now().isoformat())
    )


@router.get("/list")
async def list_simulations(
    current_user: Dict = Depends(get_current_user)
):
    """
    获取用户的所有仿真任务列表
    """
    tasks = []
    for task_id, status in simulation_service.tasks.items():
        # 只返回当前用户的任务
        if status.get("user_id") == current_user.get("id") or current_user.get("role") == "admin":
            tasks.append({
                "taskId": task_id,
                "status": status.get("status"),
                "progress": status.get("progress", 0),
                "projectName": status.get("project_name"),
                "startedAt": status.get("started_at"),
                "updatedAt": status.get("updated_at")
            })
    
    # 按更新时间倒序排列
    tasks.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
    
    return {
        "tasks": tasks,
        "total": len(tasks)
    }


# ===== 后台任务函数 =====

async def run_simulation_task(
    task_id: str,
    request_data: Dict[str, Any],
    current_user: Dict
):
    """
    后台运行仿真计算
    """
    try:
        # 更新状态为运行中
        if task_id in simulation_service.tasks:
            simulation_service.tasks[task_id]["status"] = "running"
            simulation_service.tasks[task_id]["updated_at"] = datetime.now().isoformat()
        
        # 发送启动通知
        await websocket_manager.send_message(task_id, {
            "type": "started",
            "message": "仿真开始计算..."
        })
        
        # ===== 调用您的算法 =====
        # 这里导入您的算法模块
        # from algorithm.core.simulator import run_simulation
        
        # 解析数据
        config = request_data.get("config", {})
        data = request_data.get("data", {})
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        
        # 将数据转换为 DataFrame（如果 pandas 可用）
        try:
            import pandas as pd
            df = pd.DataFrame(rows)
        except ImportError:
            # 如果没有 pandas，使用字典列表
            df = rows
        
        # 模拟仿真进度（实际项目中替换为真实算法调用）
        total_weeks = 52
        weekly_results = []
        
        for week in range(1, total_weeks + 1):
            # 检查是否被取消
            if task_id in simulation_service.tasks:
                if simulation_service.tasks[task_id].get("status") == "cancelled":
                    await websocket_manager.send_message(task_id, {
                        "type": "cancelled",
                        "message": "仿真已取消"
                    })
                    return
            
            # 计算进度
            progress = int((week / total_weeks) * 100)
            
            # 更新任务状态
            if task_id in simulation_service.tasks:
                simulation_service.tasks[task_id]["progress"] = progress
                simulation_service.tasks[task_id]["current_week"] = week
                simulation_service.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            # ===== 调用您的算法进行逐周计算 =====
            # 这里替换为真实的算法调用
            import math
            import random
            
            week_result = {
                "weekNumber": week,
                "avgOutdoorTemp": 15 + 10 * math.sin((week / 52) * 2 * math.pi) + random.uniform(-2, 2),
                "totalCoolingLoad": 200 + random.uniform(0, 300),
                "totalHeatingLoad": 100 + random.uniform(0, 200),
                "totalEnergyConsumption": 1500 + random.uniform(0, 1500),
                "avgSystemCop": 3.0 + random.uniform(0, 0.5)
            }
            weekly_results.append(week_result)
            
            # 通过 WebSocket 推送进度
            await websocket_manager.send_message(task_id, {
                "type": "progress",
                "data": {
                    "weekNumber": week,
                    "progressPercentage": progress,
                    "totalEnergyConsumption": week_result["totalEnergyConsumption"],
                    "totalCoolingLoad": week_result["totalCoolingLoad"],
                    "totalHeatingLoad": week_result["totalHeatingLoad"],
                    "avgOutdoorTemp": week_result["avgOutdoorTemp"],
                    "avgSystemCop": week_result["avgSystemCop"]
                }
            })
            
            # 模拟计算耗时
            await asyncio.sleep(0.1)
        
        # ===== 计算结果汇总 =====
        total_energy = sum(w["totalEnergyConsumption"] for w in weekly_results)
        total_cooling = sum(w["totalCoolingLoad"] for w in weekly_results)
        total_heating = sum(w["totalHeatingLoad"] for w in weekly_results)
        avg_cop = sum(w["avgSystemCop"] for w in weekly_results) / len(weekly_results)
        
        summary = {
            "totalEnergy": total_energy,
            "eui": total_energy / request_data.get("area", 10000),
            "peakCoolingLoad": max(w["totalCoolingLoad"] for w in weekly_results),
            "peakHeatingLoad": max(w["totalHeatingLoad"] for w in weekly_results),
            "avgCop": avg_cop,
            "carbonEmission": total_energy * 0.5  # 假设碳排放因子
        }
        
        # 更新任务状态为完成
        if task_id in simulation_service.tasks:
            simulation_service.tasks[task_id]["status"] = "completed"
            simulation_service.tasks[task_id]["progress"] = 100
            simulation_service.tasks[task_id]["result"] = {
                "summary": summary,
                "weekly_data": weekly_results
            }
            simulation_service.tasks[task_id]["updated_at"] = datetime.now().isoformat()
        
        # 发送完成通知
        await websocket_manager.send_message(task_id, {
            "type": "completed",
            "summary": summary
        })
        
        print(f"仿真任务 {task_id} 完成")
        
    except Exception as e:
        # 处理错误
        error_msg = str(e)
        print(f"仿真任务 {task_id} 失败: {error_msg}")
        
        if task_id in simulation_service.tasks:
            simulation_service.tasks[task_id]["status"] = "failed"
            simulation_service.tasks[task_id]["error"] = error_msg
            simulation_service.tasks[task_id]["updated_at"] = datetime.now().isoformat()
        
        await websocket_manager.send_message(task_id, {
            "type": "failed",
            "error": error_msg
        })