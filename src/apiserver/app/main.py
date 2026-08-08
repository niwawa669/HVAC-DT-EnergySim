from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.api.routes import auth, projects, upload, simulate, reports
from app.websocket.manager import websocket_manager
from app.services.simulation_service import simulation_service

# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(reports.router, prefix="/api")

# WebSocket 端点
@app.websocket("/ws/simulate/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    connection_id = None
    try:
        # 接受连接
        connection_id = await websocket_manager.connect(task_id, websocket)
        
        # 等待消息循环
        while True:
            # 接收客户端消息（ping/pong）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
                
    except WebSocketDisconnect:
        print(f"WebSocket 断开: {task_id}")
    except Exception as e:
        print(f"WebSocket 错误: {e}")
    finally:
        if connection_id:
            websocket_manager.disconnect(connection_id)

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}

# 启动入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )