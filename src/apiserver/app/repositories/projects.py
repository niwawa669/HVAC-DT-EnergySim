"""项目仓储。

项目与仿真任务的关系（D14）：
- 启动仿真时若未显式传 projectId，按（owner, 项目名）自动创建或复用项目；
- 任务状态变化时同步项目状态，使项目列表能反映"最近一次仿真"的结果；
- 删除项目是硬删除（design D1）：任务解绑但保留；历史回填只在 migration v2 执行一次，
  启动不再回填，因此删除掉的项目不会被重新建出来。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, SimulationResult, SimulationTask

VALID_PROJECT_STATUSES = ("pending", "running", "completed", "failed", "cancelled")


def _now() -> datetime:
    return datetime.now()


async def get(session: AsyncSession, project_id: int) -> Optional[Project]:
    return await session.get(Project, project_id)


async def get_by_name(session: AsyncSession, owner_id: int, name: str) -> Optional[Project]:
    stmt = (
        select(Project)
        .where(Project.owner_id == owner_id, Project.name == name)
        .order_by(Project.updated_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def list_for_user(session: AsyncSession, user_id: int, is_admin: bool = False) -> List[Project]:
    stmt = select(Project).order_by(Project.updated_at.desc())
    if not is_admin:
        stmt = stmt.where(Project.owner_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def create(
    session: AsyncSession,
    *,
    owner_id: int,
    name: str,
    building_type: Optional[str] = None,
    area: Optional[float] = None,
    status: str = "draft",
    config: Optional[dict] = None,
) -> Project:
    project = Project(
        owner_id=owner_id,
        name=name,
        building_type=building_type,
        area=area,
        status=status,
        config=config,
    )
    session.add(project)
    await session.flush()
    return project


async def get_or_create_for_simulation(
    session: AsyncSession,
    *,
    owner_id: int,
    name: str,
    building_type: Optional[str] = None,
    area: Optional[float] = None,
) -> Project:
    """按（owner, 名称）复用项目；不存在则创建。名称是用户可见的项目标识。"""
    project = await get_by_name(session, owner_id, name)
    if project is None:
        return await create(
            session,
            owner_id=owner_id,
            name=name,
            building_type=building_type,
            area=area,
            status="pending",
        )
    if building_type is not None:
        project.building_type = building_type
    if area is not None:
        project.area = area
    project.status = "pending"
    project.updated_at = _now()
    await session.flush()
    return project


async def apply_task_status(session: AsyncSession, task: SimulationTask, status: str) -> None:
    """把任务状态同步到所属项目；无关联或未知状态时不动。"""
    if not getattr(task, "project_id", None) or status not in VALID_PROJECT_STATUSES:
        return
    project = await session.get(Project, task.project_id)
    if project is None:
        return
    project.status = status
    project.updated_at = _now()
    await session.flush()


async def update_status(session: AsyncSession, project: Project, status: str) -> Project:
    project.status = status
    project.updated_at = _now()
    await session.flush()
    return project


async def latest_task(session: AsyncSession, project_id: int) -> Optional[SimulationTask]:
    stmt = (
        select(SimulationTask)
        .where(SimulationTask.project_id == project_id)
        .order_by(SimulationTask.updated_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def latest_result_summary(session: AsyncSession, task_id: str) -> Optional[dict]:
    row = (
        await session.execute(
            select(
                SimulationResult.total_energy,
                SimulationResult.total_cooling_load,
                SimulationResult.eui,
                SimulationResult.carbon_emission,
                SimulationResult.peak_load,
                SimulationResult.created_at,
            ).where(SimulationResult.task_id == task_id)
        )
    ).first()
    if row is None:
        return None
    return {
        "totalEnergy": row.total_energy,
        "totalCoolingLoad": row.total_cooling_load,
        "eui": row.eui,
        "carbonEmission": row.carbon_emission,
        "peakLoad": row.peak_load,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


async def delete(session: AsyncSession, project: Project) -> None:
    """删除项目：任务保留（置为未关联），仿真结果与报告不受影响。"""
    await session.execute(
        update(SimulationTask)
        .where(SimulationTask.project_id == project.id)
        .values(project_id=None)
    )
    await session.delete(project)
    await session.flush()


async def has_active_tasks(session: AsyncSession, project_id: int) -> bool:
    """项目下是否存在待运行/运行中的任务（删除前置条件，design D3）。"""
    stmt = (
        select(func.count())
        .select_from(SimulationTask)
        .where(
            SimulationTask.project_id == project_id,
            SimulationTask.status.in_(("pending", "running")),
        )
    )
    return bool(await session.scalar(stmt))


def serialize(
    project: Project,
    latest_task: Optional[SimulationTask] = None,
    summary: Optional[dict] = None,
) -> dict:
    data = {
        "id": project.id,
        "name": project.name,
        "buildingType": project.building_type,
        "area": project.area,
        "status": project.status,
        "createdAt": project.created_at.isoformat() if project.created_at else None,
        "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
        "latestTask": None,
        "latestSummary": summary,
    }
    if latest_task is not None:
        data["latestTask"] = {
            "taskId": latest_task.id,
            "status": latest_task.status,
            "progress": latest_task.progress,
            "updatedAt": latest_task.updated_at.isoformat() if latest_task.updated_at else None,
        }
    return data
