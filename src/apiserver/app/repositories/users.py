"""用户仓储。"""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, SimulationTask, User


async def get_by_username(session: AsyncSession, username: str) -> Optional[User]:
    return await session.scalar(select(User).where(User.username == username))


async def get_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    return await session.get(User, user_id)


async def count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(User)) or 0)


async def list_users(
    session: AsyncSession,
    *,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> Tuple[List[User], int]:
    filters = []
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        filters.append(or_(User.username.ilike(like), User.email.ilike(like)))

    count_stmt = select(func.count()).select_from(User)
    stmt = select(User)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)

    total = int(await session.scalar(count_stmt) or 0)
    rows = list(
        (
            await session.execute(stmt.order_by(User.id).offset(offset).limit(limit))
        ).scalars().all()
    )
    return rows, total


async def count_active_admins(session: AsyncSession, exclude_user_id: Optional[int] = None) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role == "admin", User.is_active.is_(True)
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return int(await session.scalar(stmt) or 0)


async def has_owned_records(session: AsyncSession, user_id: int) -> bool:
    """用户是否已有项目或仿真任务（删除账户前的前置检查）。"""
    projects = await session.scalar(
        select(func.count()).select_from(Project).where(Project.owner_id == user_id)
    )
    tasks = await session.scalar(
        select(func.count()).select_from(SimulationTask).where(SimulationTask.user_id == user_id)
    )
    return bool(int(projects or 0)) or bool(int(tasks or 0))


async def create(
    session: AsyncSession,
    *,
    username: str,
    hashed_password: str,
    role: str = "engineer",
    email: Optional[str] = None,
    is_active: bool = True,
    user_id: Optional[int] = None,
) -> User:
    user = User(
        id=user_id,
        username=username,
        email=email,
        role=role,
        hashed_password=hashed_password,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    return user


async def set_password(session: AsyncSession, user: User, hashed_password: str) -> None:
    user.hashed_password = hashed_password
    await session.flush()


async def delete(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.flush()


def serialize(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
        "isActive": user.is_active,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
    }
