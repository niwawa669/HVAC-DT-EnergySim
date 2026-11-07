from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

from app.config import ensure_storage_dirs, settings
from app.api.routes import auth, projects, upload, simulate, reports, design, users
from app.db.migrate import ensure_schema_ready, upgrade
from app.db.seed import seed_default_users
from app.db.session import dispose_engine, session_scope
from app.repositories import reports as reports_repo
from app.repositories import tasks as tasks_repo
from app.services.simulation_service import simulation_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动：迁移（含 v2 一次性回填）-> 种子账户 -> 收敛未完成任务 -> 报告对账。"""
    ensure_storage_dirs()

    executed = []
    if settings.DB_AUTO_MIGRATE:
        executed = await upgrade()
    else:
        await ensure_schema_ready()

    async with session_scope() as session:
        seeded = await seed_default_users(session)
        # 历史任务的项目关联由 migration v2 一次性回填（design D2）；
        # 启动不再回填，否则用户删掉的项目会被重新建出来。
        interrupted = await tasks_repo.mark_interrupted(session)
        reconcile = await reports_repo.reconcile_from_disk(session)

    print(
        "🗄️ 持久化就绪: "
        f"迁移={executed or '无'} 新增账户={seeded} "
        f"中断任务={interrupted} 报告索引扫描={reconcile.get('scanned', 0)} "
        f"补录={reconcile.get('imported', 0)} 缺失产物={reconcile.get('missing', 0)}"
    )
    yield
    await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 HTTP 路由
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(design.router, prefix="/api")
app.include_router(users.router, prefix="/api")


# ===== WebSocket 端点 =====
@app.websocket("/ws/simulate/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket 连接端点"""
    print(f"🔗 WebSocket 连接请求: {task_id}")

    try:
        await websocket.accept()
        print(f"✅ WebSocket 已接受: {task_id}")

        # 注册连接（即使 task_id 还没有仿真任务）
        simulation_service.register_websocket(task_id, websocket)
        print(f"📝 WebSocket 已注册: {task_id}")

        # 发送连接确认
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "WebSocket 连接成功",
            "taskId": task_id,
        }))
        print(f"📤 已发送连接确认: {task_id}")

        # 保持连接
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        print(f"⚠️ WebSocket 断开: {task_id}")
    except Exception as e:  # noqa: BLE001
        print(f"❌ WebSocket 错误: {e}")
    finally:
        simulation_service.unregister_websocket(task_id)
        print(f"📝 WebSocket 已注销: {task_id}")


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
