import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.algorithm_wrapper import algorithm_wrapper


class SimulationService:
    """仿真服务 - 管理仿真任务和调用算法"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, Any] = {}
    
    def register_websocket(self, task_id: str, websocket):
        """注册 WebSocket 连接"""
        self.websocket_connections[task_id] = websocket
        print(f"📝 WebSocket 注册成功: {task_id}, 当前连接数: {len(self.websocket_connections)}")
    
    def unregister_websocket(self, task_id: str):
        """取消注册 WebSocket 连接"""
        if task_id in self.websocket_connections:
            del self.websocket_connections[task_id]
            print(f"📝 WebSocket 已注销: {task_id}, 剩余连接数: {len(self.websocket_connections)}")
    
    async def _send_websocket_message(self, task_id: str, message: Dict):
        """通过 WebSocket 发送消息"""
        ws = self.websocket_connections.get(task_id)
        if ws:
            try:
                message_str = json.dumps(message)
                await ws.send_text(message_str)
                print(f"📤 发送 WebSocket 消息到 {task_id}: {message.get('type')}")
                return True
            except Exception as e:
                print(f"❌ 发送 WebSocket 消息失败: {e}")
                if task_id in self.websocket_connections:
                    del self.websocket_connections[task_id]
                return False
        else:
            print(f"⚠️ WebSocket 连接不存在: {task_id}")
            return False
    
    async def start_simulation(self, request_data: Dict[str, Any]) -> str:
        """启动仿真"""
        task_id = str(uuid.uuid4())
        
        self.tasks[task_id] = {
            "status": "pending",
            "progress": 0,
            "current_week": 0,
            "total_weeks": 52,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "config": request_data.get("config"),
            "data": request_data.get("data"),
            "project_name": request_data.get("projectName"),
            "building_type": request_data.get("buildingType"),
            "area": request_data.get("area", 2931.0),
            "user_id": 1,
            "result": None,
            "error": None
        }
        
        print(f"🚀 创建仿真任务: {task_id}")
        
        asyncio.create_task(self._run_simulation_task(task_id, request_data))
        
        return task_id
    
    async def _run_simulation_task(self, task_id: str, request_data: Dict[str, Any]):
        """执行仿真计算 - 流式处理"""
        try:
            print(f"🔄 开始执行仿真任务: {task_id}")
            
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "running"
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            await self._send_websocket_message(task_id, {
                "type": "started",
                "message": "仿真开始计算..."
            })
            
            rows = request_data["data"]["rows"]
            config = request_data.get("config", {})
            area = request_data.get("area", 2931.0)
            
            print(f"📊 数据行数: {len(rows)}, 建筑面积: {area} m²")
            print(f"📋 配置参数: {config.get('Qr_chiller_BCH')} kW 大机, {config.get('Qr_chiller_SCH')} kW 小机")
            
            # ===== 流式调用算法（传入 config） =====
            week_count = 0
            
            for week_result in algorithm_wrapper.run_simulation_streaming(
                data=rows,
                config=config,
                area=area
            ):
                week_count += 1
                week_number = week_result.get('weekNumber', week_count)
                progress = int((week_count / 52) * 100) if week_count <= 52 else 100
                
                if task_id in self.tasks:
                    self.tasks[task_id]["progress"] = progress
                    self.tasks[task_id]["current_week"] = week_number
                    self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
                
                # ===== 推送本周数据 =====
                await self._send_websocket_message(task_id, {
                    "type": "progress",
                    "data": {
                        "weekNumber": week_number,
                        "progressPercentage": progress,
                        "totalCoolingLoad": week_result.get('totalCoolingLoad', 0),
                        "peakCoolingLoad": week_result.get('peakCoolingLoad', 0),
                        "totalQStation": week_result.get('totalQStation', 0),
                        "totalEnergyConsumption": week_result.get('totalEnergyConsumption', 0),
                        "avgSystemCop": week_result.get('avgSystemCop', 0),
                        "avgOutdoorTemp": week_result.get('avgOutdoorTemp', 0)
                    }
                })
                
                print(f"📤 已推送第 {week_number} 周数据，进度 {progress}%")
                
                await asyncio.sleep(0.02)
            
            # ===== 获取汇总结果 =====
            summary = algorithm_wrapper.get_last_summary()
            weekly_results = algorithm_wrapper.get_last_weekly_data()
            
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["progress"] = 100
                self.tasks[task_id]["result"] = {
                    "summary": summary,
                    "weekly_data": weekly_results
                }
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            # ===== 发送完成消息 =====
            await self._send_websocket_message(task_id, {
                "type": "completed",
                "summary": {
                    "totalEnergy": summary.get('totalEnergy', 0),
                    "totalCoolingLoad": summary.get('totalCoolingLoad', 0),
                    "totalQStation": summary.get('totalQStation', 0),
                    "peakCoolingLoad": summary.get('peakCoolingLoad', 0),
                    "eui": summary.get('eui', 0),
                    "avgCop": summary.get('avgCop', 0),
                    "carbonEmission": summary.get('carbonEmission', 0),
                    "area": summary.get('area', 0)
                }
            })
            
            print(f"✅ 仿真任务 {task_id} 完成")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 仿真任务 {task_id} 失败: {error_msg}")
            import traceback
            traceback.print_exc()
            
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error"] = error_msg
                self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
            
            await self._send_websocket_message(task_id, {
                "type": "failed",
                "error": error_msg
            })
    
    def reset_task(self, task_id: str) -> bool:
        """重置任务状态，保留数据用于重新仿真"""
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id]["status"] = "pending"
        self.tasks[task_id]["progress"] = 0
        self.tasks[task_id]["current_week"] = 0
        self.tasks[task_id]["started_at"] = datetime.now().isoformat()
        self.tasks[task_id]["updated_at"] = datetime.now().isoformat()
        self.tasks[task_id]["result"] = None
        self.tasks[task_id]["error"] = None
        
        print(f"🔄 任务已重置: {task_id}")
        return True
    
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
        if task_id in self.tasks and self.tasks[task_id]["status"] in ["pending", "running"]:
            self.tasks[task_id]["status"] = "cancelled"
            return True
        return False
    
    def list_user_tasks(self, user_id: int) -> list:
        """获取用户的所有任务"""
        tasks = []
        for task_id, status in self.tasks.items():
            if status.get("user_id") == user_id:
                tasks.append({
                    "taskId": task_id,
                    "status": status.get("status"),
                    "progress": status.get("progress", 0),
                    "projectName": status.get("project_name"),
                    "startedAt": status.get("started_at"),
                    "updatedAt": status.get("updated_at")
                })
        return sorted(tasks, key=lambda x: x.get("updatedAt", ""), reverse=True)


# 单例
simulation_service = SimulationService()