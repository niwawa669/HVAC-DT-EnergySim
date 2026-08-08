from fastapi import WebSocket
from typing import Dict, List, Optional
import json

class WebSocketManager:
    """WebSocket 连接管理"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.task_connections: Dict[str, str] = {}  # task_id -> connection_id
    
    async def connect(self, task_id: str, websocket: WebSocket) -> str:
        """接受连接"""
        await websocket.accept()
        
        connection_id = f"{task_id}_{id(websocket)}"
        self.active_connections[connection_id] = websocket
        self.task_connections[task_id] = connection_id
        
        # 向仿真服务注册
        from app.services.simulation_service import simulation_service
        simulation_service.register_websocket(task_id, websocket)
        
        # 发送连接确认
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "连接成功",
            "taskId": task_id
        }))
        
        return connection_id
    
    def disconnect(self, connection_id: str):
        """断开连接"""
        if connection_id in self.active_connections:
            # 找到对应的 task_id
            for task_id, conn_id in self.task_connections.items():
                if conn_id == connection_id:
                    del self.task_connections[task_id]
                    from app.services.simulation_service import simulation_service
                    simulation_service.unregister_websocket(task_id)
                    break
            
            del self.active_connections[connection_id]
    
    async def send_message(self, task_id: str, message: dict):
        """发送消息到指定任务"""
        conn_id = self.task_connections.get(task_id)
        if conn_id and conn_id in self.active_connections:
            try:
                ws = self.active_connections[conn_id]
                await ws.send_text(json.dumps(message))
                return True
            except Exception:
                self.disconnect(conn_id)
        return False
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for ws in self.active_connections.values():
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass

# 单例
websocket_manager = WebSocketManager()