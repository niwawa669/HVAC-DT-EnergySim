import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

# 导入您的算法
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../algorithm"))
try:
    from algorithm.core.simulator import run_simulation  # 您的算法入口
except ImportError:
    # 如果算法尚未集成，使用模拟实现
    def run_simulation(data: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        """模拟仿真（开发时使用）"""
        import math
        import random
        
        weekly_data = []
        for week in range(1, 53):
            weekly_data.append({
                "weekNumber": week,
                "avgOutdoorTemp": 15 + 10 * math.sin((week / 52) * 2 * math.pi) + random.uniform(-2, 2),
                "totalCoolingLoad": 200 + random.uniform(0, 300),
                "totalHeatingLoad": 100 + random.uniform(0, 200),
                "totalEnergyConsumption": 1500 + random.uniform(0, 1500),
                "avgSystemCop": 3.0 + random.uniform(0, 0.5)
            })
        
        return {
            "summary": {
                "totalEnergy": 125000,
                "eui": 85.6,
                "peakCoolingLoad": 450,
                "peakHeatingLoad": 280,
                "avgCop": 3.2,
                "carbonEmission": 62500
            },
            "weeklyData": weekly_data
        }

class SimulationService:
    """仿真服务"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, Any] = {}
    
    def register_websocket(self, task_id: str, websocket):
        """注册 WebSocket 连接"""
        self.websocket_connections[task_id] = websocket
    
    def unregister_websocket(self, task_id: str):
        """取消注册 WebSocket 连接"""
        if task_id in self.websocket_connections:
            del self.websocket_connections[task_id]
    
    async def start_simulation(self, request_data: Dict[str, Any]) -> str:
        """启动仿真"""
        task_id = str(uuid.uuid4())
        
        self.tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "current_week": 0,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "config": request_data.get("config"),
            "data": request_data.get("data")
        }
        
        # 启动异步任务
        asyncio.create_task(self._run_simulation_task(task_id, request_data))
        
        return task_id
    
    async def _run_simulation_task(self, task_id: str, request_data: Dict[str, Any]):
        """执行仿真计算"""
        try:
            # 解析数据
            headers = request_data["data"]["headers"]
            rows = request_data["data"]["rows"]
            df = pd.DataFrame(rows)
            
            # 获取配置
            config = request_data["config"]
            
            # 调用您的算法
            result = run_simulation(df, config)
            
            # 更新任务状态
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["progress"] = 100
                self.tasks[task_id]["result"] = result
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            # 通过 WebSocket 发送完成消息
            await self._send_websocket_message(task_id, {
                "type": "completed",
                "summary": result["summary"]
            })
            
        except Exception as e:
            # 处理错误
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error"] = str(e)
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            await self._send_websocket_message(task_id, {
                "type": "failed",
                "error": str(e)
            })
    
    async def _send_websocket_message(self, task_id: str, message: Dict):
        """通过 WebSocket 发送消息"""
        ws = self.websocket_connections.get(task_id)
        if ws:
            try:
                import json
                await ws.send_text(json.dumps(message))
            except Exception as e:
                print(f"发送 WebSocket 消息失败: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """获取任务结果"""
        task = self.tasks.get(task_id)
        if task and task.get("status") == "completed":
            return task.get("result")
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.tasks and self.tasks[task_id]["status"] == "running":
            self.tasks[task_id]["status"] = "cancelled"
            return True
        return False

# 单例
simulation_service = SimulationService()