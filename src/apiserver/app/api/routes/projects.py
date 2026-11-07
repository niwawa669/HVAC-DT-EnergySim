from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.schemas import ProjectCreate
from app.repositories import projects as projects_repo

router = APIRouter(prefix="/projects", tags=["projects"])


async def _serialize_detail(db: AsyncSession, project) -> Dict[str, Any]:
    """项目 + 最近一次仿真任务 + 该任务的结果摘要（若已完成）。"""
    latest = await projects_repo.latest_task(db, project.id)
    summary = None
    if latest is not None and latest.status == "completed":
        summary = await projects_repo.latest_result_summary(db, latest.id)
    return projects_repo.serialize(project, latest, summary)


@router.get("")
async def get_projects(
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目列表（普通用户只看自己创建的）。"""
    items = await projects_repo.list_for_user(
        db, current_user.get("id"), current_user.get("role") == "admin"
    )
    return [await _serialize_detail(db, item) for item in items]


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目详情（含最近一次仿真与结果摘要）。"""
    project = await projects_repo.get(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.owner_id != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问此项目")
    return await _serialize_detail(db, project)


@router.post("")
async def create_project(
    project_data: ProjectCreate,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建项目。"""
    project = await projects_repo.create(
        db,
        owner_id=current_user.get("id"),
        name=project_data.name,
        building_type=project_data.buildingType,
        area=project_data.area,
        status=project_data.status or "pending",
    )
    return await _serialize_detail(db, project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除项目：仿真任务与结果保留（任务变为未关联），报告不受影响。"""
    project = await projects_repo.get(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.owner_id != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权删除此项目")

    if await projects_repo.has_active_tasks(db, project.id):
        raise HTTPException(status_code=409, detail="项目有正在运行的仿真，无法删除")

    await projects_repo.delete(db, project)
    return {"message": "项目已删除", "projectId": project_id}
