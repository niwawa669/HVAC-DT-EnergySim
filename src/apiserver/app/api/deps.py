from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.repositories import users as users_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取当前用户：优先按 token 里的 uid 查库，缺失时回退用户名。"""
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    user_id: Optional[int] = payload.get("uid")

    user = None
    if user_id is not None:
        user = await users_repo.get_by_id(db, int(user_id))
    if user is None and username:
        user = await users_repo.get_by_username(db, str(username))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账户已停用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
    }
