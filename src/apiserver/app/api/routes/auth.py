from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.schemas import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    TokenResponse,
)
from app.repositories import users as users_repo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录（账户来自数据库，密码 bcrypt 校验）。"""
    user = await users_repo.get_by_username(db, request.username)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "uid": user.id}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=users_repo.serialize(user),
    )


@router.get("/me")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """获取当前用户信息。"""
    return current_user


@router.put("/me")
async def update_profile(
    request: ProfileUpdate,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前账户的基础信息（目前仅邮箱）。"""
    user = await users_repo.get_by_id(db, int(current_user["id"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账户不存在")

    if "email" in request.model_fields_set:
        user.email = request.email or None
    await db.flush()
    return users_repo.serialize(user)


@router.post("/change-password")
async def change_password(
    request: PasswordChange,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前账户的密码（需校验当前密码）。"""
    user = await users_repo.get_by_id(db, int(current_user["id"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账户不存在")

    if not verify_password(request.currentPassword, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")

    if request.newPassword == request.currentPassword:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    await users_repo.set_password(db, user, get_password_hash(request.newPassword))
    return {"message": "密码已更新"}
