"""初始化数据（D12）：仅在用户表为空时写入默认账户，不覆盖任何已存在账户。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.orm import User

DEFAULT_USERS = [
    {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "password": "123456",
    },
    {
        "id": 2,
        "username": "user",
        "email": "user@example.com",
        "role": "engineer",
        "password": "123456",
    },
]


async def seed_default_users(session: AsyncSession) -> int:
    count = await session.scalar(select(func.count()).select_from(User))
    if count:
        return 0
    for item in DEFAULT_USERS:
        session.add(
            User(
                id=item["id"],
                username=item["username"],
                email=item["email"],
                role=item["role"],
                hashed_password=get_password_hash(item["password"]),
                is_active=True,
            )
        )
    await session.flush()
    return len(DEFAULT_USERS)
