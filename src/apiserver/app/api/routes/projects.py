from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from datetime import datetime

from app.api.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

# 模拟项目数据
fake_projects = [
    {
        "id": 1,
        "name": "办公楼能耗仿真项目",
        "buildingType": "office",
        "area": 10000,
        "status": "completed",
        "createdAt": "2026-07-28T14:30:00",
        "updatedAt": "2026-08-01T10:00:00"
    },
    {
        "id": 2,
        "name": "商业综合体能耗分析",
        "buildingType": "commercial",
        "area": 50000,
        "status": "running",
        "createdAt": "2026-07-29T09:15:00",
        "updatedAt": "2026-08-01T09:30:00"
    },
    {
        "id": 3,
        "name": "住宅小区暖通仿真",
        "buildingType": "residential",
        "area": 20000,
        "status": "pending",
        "createdAt": "2026-07-30T16:45:00",
        "updatedAt": "2026-07-30T16:45:00"
    }
]

@router.get("")
async def get_projects(current_user: Dict = Depends(get_current_user)):
    """获取项目列表"""
    return fake_projects

@router.get("/{project_id}")
async def get_project(
    project_id: int,
    current_user: Dict = Depends(get_current_user)
):
    """获取项目详情"""
    for project in fake_projects:
        if project["id"] == project_id:
            return project
    raise HTTPException(status_code=404, detail="项目不存在")

@router.post("")
async def create_project(
    project_data: Dict[str, Any],
    current_user: Dict = Depends(get_current_user)
):
    """创建项目"""
    new_project = {
        "id": len(fake_projects) + 1,
        **project_data,
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    fake_projects.append(new_project)
    return new_project