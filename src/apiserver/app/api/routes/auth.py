from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any

from app.models.schemas import LoginRequest, TokenResponse
from app.core.security import create_access_token, verify_password, get_password_hash
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# 模拟用户数据库
fake_users_db = {
    "admin": {
        "id": 1,
        "username": "admin",
        "hashed_password": get_password_hash("123456"),
        "role": "admin",
        "email": "admin@example.com"
    },
    "user": {
        "id": 2,
        "username": "user",
        "hashed_password": get_password_hash("123456"),
        "role": "engineer",
        "email": "user@example.com"
    }
}

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    user = fake_users_db.get(request.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "uid": user["id"]}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "email": user.get("email")
        }
    )

@router.get("/me")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user