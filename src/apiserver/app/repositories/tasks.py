"""仿真任务仓储（D7）。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import SimulationResult, SimulationTask
from app.repositories import projects as projects_repo

TERMINAL_STATUSES = ("completed", "failed", "cancelled")
UNFINISHED_STATUSES = ("pending", "running")
INTERRUPTED_ERROR = "服务重启中断（进程退出时任务未完成），可点击重新仿真"


def _now() -> datetime:
    return datetime.now()


async def create(
    session: AsyncSession,
    *,
    task_id: str,
    user_id: int,
    project_id: Optional[int] = None,
    dataset_id: Optional[str] = None,
    project_name: Optional[str] = None,
    building_type: Optional[str] = None,
    area: Optional[float] = None,
    config: Optional[dict] = None,
    data_meta: Optional[dict] = None,
    total_weeks: int = 52,
) -> SimulationTask:
    now = _now()
    task = SimulationTask(
        id=task_id,
        user_id=user_id,
        project_id=project_id,
        dataset_id=dataset_id,
        status="pending",
        progress=0,
        current_week=0,
        total_weeks=total_weeks,
        project_name=project_name,
        building_type=building_type,
        area=area,
        config=config,
        data_meta=data_meta,
        started_at=now,
        updated_at=now,
    )
    session.add(task)
    await session.flush()
    return task


async def get(session: AsyncSession, task_id: str) -> Optional[SimulationTask]:
    return await session.get(SimulationTask, task_id)


async def update_progress(
    session: AsyncSession,
    task_id: str,
    *,
    progress: int,
    current_week: Optional[int] = None,
) -> Optional[str]:
    """更新进度并返回当前状态；任务不存在返回 None。"""
    task = await session.get(SimulationTask, task_id)
    if task is None:
        return None
    task.progress = max(0, min(100, int(progress)))
    if current_week is not None:
        task.current_week = int(current_week)
    task.updated_at = _now()
    await session.flush()
    return task.status


async def set_status(
    session: AsyncSession,
    task_id: str,
    status: str,
    *,
    error: Optional[str] = None,
    progress: Optional[int] = None,
) -> bool:
    task = await session.get(SimulationTask, task_id)
    if task is None:
        return False
    task.status = status
    task.error = error
    task.updated_at = _now()
    if progress is not None:
        task.progress = int(progress)
    if status == "completed":
        task.completed_at = _now()
    elif status in ("pending", "running"):
        task.completed_at = None
    await projects_repo.apply_task_status(session, task, status)
    await session.flush()
    return True


async def reset_for_restart(session: AsyncSession, task_id: str) -> bool:
    task = await session.get(SimulationTask, task_id)
    if task is None:
        return False
    result = await session.get(SimulationResult, task_id)
    if result is not None:
        await session.delete(result)
    now = _now()
    task.status = "pending"
    task.progress = 0
    task.current_week = 0
    task.error = None
    task.started_at = now
    task.updated_at = now
    task.completed_at = None
    await projects_repo.apply_task_status(session, task, "pending")
    await session.flush()
    return True


async def mark_interrupted(session: AsyncSession) -> int:
    """启动收敛：未完成任务 -> failed，并写明原因；同步所属项目状态。"""
    tasks = list(
        (
            await session.execute(
                select(SimulationTask).where(SimulationTask.status.in_(UNFINISHED_STATUSES))
            )
        ).scalars().all()
    )
    now = _now()
    for task in tasks:
        task.status = "failed"
        task.error = INTERRUPTED_ERROR
        task.updated_at = now
        task.completed_at = None
        await projects_repo.apply_task_status(session, task, "failed")
    await session.flush()
    return len(tasks)


async def list_for_user(
    session: AsyncSession, user_id: int, is_admin: bool = False
) -> List[SimulationTask]:
    stmt = select(SimulationTask).order_by(SimulationTask.updated_at.desc())
    if not is_admin:
        stmt = stmt.where(SimulationTask.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


def summarize(task: SimulationTask) -> dict:
    return {
        "taskId": task.id,
        "status": task.status,
        "progress": task.progress,
        "projectName": task.project_name,
        "startedAt": task.started_at.isoformat() if task.started_at else None,
        "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
    }
