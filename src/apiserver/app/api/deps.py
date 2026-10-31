from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any

from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """获取当前用户（依赖注入）"""
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从用户库解析真实 id。此前的实现把 id 硬编码为 1，导致所有登录用户
    # 在鉴权时都是同一个身份，"仅任务所属用户可访问"这类规则永远不生效。
    user_id = payload.get("uid")
    if user_id is None:
        try:
            from app.api.routes.auth import fake_users_db
        except ImportError:  # pragma: no cover - 循环导入兜底
            fake_users_db = {}
        user_id = (fake_users_db.get(username) or {}).get("id")

    return {
        "id": user_id,
        "username": username,
        "role": payload.get("role", "engineer")
    }