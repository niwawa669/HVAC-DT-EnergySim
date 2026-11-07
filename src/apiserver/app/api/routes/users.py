"""账户管理接口（仅管理员）。"""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.schemas import PasswordReset, UserCreate, UserUpdate
from app.repositories import users as users_repo

router = APIRouter(prefix="/users", tags=["users"])


def _require_admin(current_user: Dict) -> None:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可管理账户",
        )


@router.get("")
async def list_users(
    search: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """分页查询账户（可按用户名/邮箱搜索）。"""
    _require_admin(current_user)
    page = max(1, page)
    page_size = min(max(1, pageSize), 100)
    rows, total = await users_repo.list_users(
        db,
        keyword=search,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return {
        "items": [users_repo.serialize(user) for user in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreate,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """新建账户。"""
    _require_admin(current_user)

    if await users_repo.get_by_username(db, request.username) is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = await users_repo.create(
        db,
        username=request.username,
        hashed_password=get_password_hash(request.password),
        role=request.role,
        email=request.email or None,
    )
    return users_repo.serialize(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    request: UserUpdate,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改账户的邮箱、角色或启用状态。"""
    _require_admin(current_user)

    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="账户不存在")

    fields = request.model_fields_set

    if target.id == int(current_user["id"]):
        if "role" in fields and request.role is not None and request.role != target.role:
            raise HTTPException(status_code=400, detail="不能修改自己的角色")
        if "isActive" in fields and request.isActive is False:
            raise HTTPException(status_code=400, detail="不能停用当前登录账户")

    new_role = request.role if ("role" in fields and request.role is not None) else target.role
    new_active = (
        request.isActive
        if ("isActive" in fields and request.isActive is not None)
        else target.is_active
    )

    if target.role == "admin" and target.is_active and (new_role != "admin" or not new_active):
        remaining = await users_repo.count_active_admins(db, exclude_user_id=target.id)
        if remaining == 0:
            raise HTTPException(status_code=409, detail="至少需要保留一个启用状态的管理员")

    if "email" in fields:
        target.email = request.email or None
    if "role" in fields and request.role is not None:
        target.role = request.role
    if "isActive" in fields and request.isActive is not None:
        target.is_active = request.isActive

    await db.flush()
    return users_repo.serialize(target)


@router.post("/{user_id}/password")
async def reset_user_password(
    user_id: int,
    request: PasswordReset,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员重置指定账户的密码。"""
    _require_admin(current_user)

    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="账户不存在")

    await users_repo.set_password(db, target, get_password_hash(request.newPassword))
    return {"message": "密码已重置", "userId": target.id}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除账户：已有项目或仿真任务时拒绝，建议改为停用。"""
    _require_admin(current_user)

    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="账户不存在")

    if target.id == int(current_user["id"]):
        raise HTTPException(status_code=400, detail="不能删除当前登录账户")

    if target.role == "admin" and target.is_active:
        remaining = await users_repo.count_active_admins(db, exclude_user_id=target.id)
        if remaining == 0:
            raise HTTPException(status_code=409, detail="至少需要保留一个启用状态的管理员")

    if await users_repo.has_owned_records(db, target.id):
        raise HTTPException(
            status_code=409,
            detail="该账户已有项目或仿真任务，请改为停用，避免丢失历史数据归属",
        )

    await users_repo.delete(db, target)
    return {"message": "账户已删除", "userId": user_id}
