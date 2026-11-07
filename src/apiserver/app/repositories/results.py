"""仿真结果仓储（D3/D7）：结果与任务终态在同一事务提交。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, SimulationResult, SimulationTask


class TaskCancelled(RuntimeError):
    """任务已被取消，结果不得覆盖终态。"""


def _now() -> datetime:
    return datetime.now()


async def save_with_status(
    session: AsyncSession, task_id: str, payload: Dict[str, Any]
) -> SimulationResult:
    """写结果并把任务置为 completed；调用方负责提交事务。"""
    task = await session.get(SimulationTask, task_id)
    if task is None:
        raise LookupError(f"任务不存在: {task_id}")
    if task.status == "cancelled":
        raise TaskCancelled(f"任务已取消，不写入结果: {task_id}")

    summary = payload.get("summary") or {}
    meta = payload.get("meta") or {}
    row = await session.get(SimulationResult, task_id)
    if row is None:
        row = SimulationResult(task_id=task_id, payload=payload)
        session.add(row)
    else:
        row.payload = payload
    row.caliber_version = meta.get("caliberVersion")
    row.total_energy = summary.get("totalEnergy")
    row.total_cooling_load = summary.get("totalCoolingLoad")
    row.eui = summary.get("eui")
    row.carbon_emission = summary.get("carbonEmission")
    row.peak_load = meta.get("peakLoad") or summary.get("peakCoolingLoad")
    row.created_at = _now()

    task.status = "completed"
    task.progress = 100
    task.error = None
    task.updated_at = _now()
    task.completed_at = _now()

    # 项目状态与结果、任务终态同一事务提交，项目列表立刻看到"已完成"
    if task.project_id:
        project = await session.get(Project, task.project_id)
        if project is not None:
            project.status = "completed"
            project.updated_at = _now()
    await session.flush()
    return row


async def load_payload(session: AsyncSession, task_id: str) -> Optional[Dict[str, Any]]:
    row = await session.get(SimulationResult, task_id)
    return dict(row.payload) if row is not None else None


async def delete_for_task(session: AsyncSession, task_id: str) -> bool:
    row = await session.get(SimulationResult, task_id)
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True
