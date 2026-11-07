"""账户管理自检（个人资料 / 改密 / 管理员用户管理）。

运行：
    python scripts/verify_accounts.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.gettempdir()) / f"hvac_accounts_{uuid.uuid4().hex[:8]}"
TMP.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(TMP)
os.environ["HVAC_REPORTS_DIR"] = str(TMP / "reports")
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, str(ROOT / "src" / "apiserver"))

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f" :: {detail}"))


async def expect_status(code: int, coro) -> bool:
    from fastapi import HTTPException

    try:
        await coro
        return False
    except HTTPException as exc:
        return exc.status_code == code


async def main() -> int:
    from app.api.routes.auth import (
        change_password,
        login,
        update_profile,
    )
    from app.api.routes.users import (
        create_user,
        delete_user,
        list_users,
        reset_user_password,
        update_user,
    )
    from app.config import ensure_storage_dirs
    from app.db.migrate import upgrade
    from app.db.seed import seed_default_users
    from app.db.session import dispose_engine, session_scope
    from app.models.schemas import (
        LoginRequest,
        PasswordChange,
        PasswordReset,
        ProfileUpdate,
        UserCreate,
        UserUpdate,
    )
    from app.repositories import projects as projects_repo

    ensure_storage_dirs()
    await upgrade()
    async with session_scope() as session:
        await seed_default_users(session)

    # ---------- 登录与管理员鉴权 ----------
    async with session_scope() as session:
        admin_login = await login(LoginRequest(username="admin", password="123456"), session)
        admin = {
            "id": admin_login.user["id"],
            "username": admin_login.user["username"],
            "role": admin_login.user["role"],
        }
        engineer_login = await login(LoginRequest(username="user", password="123456"), session)
        engineer = {
            "id": engineer_login.user["id"],
            "username": engineer_login.user["username"],
            "role": engineer_login.user["role"],
        }
        listed = await list_users(None, 1, 20, admin, session)

    check("管理员可登录", admin["id"] == 1 and admin["role"] == "admin")
    check("账户列表返回种子账户", listed["total"] == 2, str(listed["total"]))
    check("账户列表携带启用状态", all("isActive" in item for item in listed["items"]))

    # ---------- 非管理员不能管理账户 ----------
    async with session_scope() as session:
        forbidden = await expect_status(403, list_users(None, 1, 20, engineer, session))
        forbidden_create = await expect_status(
            403,
            create_user(
                UserCreate(username="hacker", password="secret123"), engineer, session
            ),
        )
    check("普通用户不能查看账户列表", forbidden)
    check("普通用户不能新建账户", forbidden_create)

    # ---------- 新建账户 ----------
    async with session_scope() as session:
        created = await create_user(
            UserCreate(
                username="engineer1",
                password="secret123",
                email="engineer1@example.com",
                role="engineer",
            ),
            admin,
            session,
        )
    new_id = created["id"]
    check("管理员可新建账户", created["username"] == "engineer1" and created["isActive"] is True)

    async with session_scope() as session:
        duplicate = await expect_status(
            409,
            create_user(
                UserCreate(username="engineer1", password="secret123"), admin, session
            ),
        )
    check("重复用户名被拒绝", duplicate)

    # ---------- 个人资料 ----------
    async with session_scope() as session:
        updated = await update_profile(
            ProfileUpdate(email="admin-new@example.com"), admin, session
        )
    check("可更新自己的邮箱", updated["email"] == "admin-new@example.com", str(updated.get("email")))

    # ---------- 修改自己的密码 ----------
    async with session_scope() as session:
        wrong_password = await expect_status(
            400,
            change_password(
                PasswordChange(currentPassword="wrong", newPassword="newsecret1"), admin, session
            ),
        )
        same_password = await expect_status(
            400,
            change_password(
                PasswordChange(currentPassword="123456", newPassword="123456"), admin, session
            ),
        )
        changed = await change_password(
            PasswordChange(currentPassword="123456", newPassword="newsecret1"), admin, session
        )
    check("当前密码错误时拒绝改密", wrong_password)
    check("新密码不能与当前密码相同", same_password)
    check("修改自己密码成功", changed.get("message") == "密码已更新")

    async with session_scope() as session:
        old_login = await expect_status(
            401, login(LoginRequest(username="admin", password="123456"), session)
        )
        new_login = await login(LoginRequest(username="admin", password="newsecret1"), session)
    check("旧密码失效", old_login)
    check("新密码可登录", new_login.user["username"] == "admin")

    # ---------- 管理员修改账户 ----------
    async with session_scope() as session:
        edited = await update_user(
            new_id,
            UserUpdate(email="changed@example.com", role="engineer", isActive=True),
            admin,
            session,
        )
    check("管理员可修改邮箱/角色/状态", edited["email"] == "changed@example.com")

    async with session_scope() as session:
        self_role = await expect_status(
            400, update_user(admin["id"], UserUpdate(role="engineer"), admin, session)
        )
        self_disable = await expect_status(
            400, update_user(admin["id"], UserUpdate(isActive=False), admin, session)
        )
        self_delete = await expect_status(400, delete_user(admin["id"], admin, session))
    check("不能修改自己的角色", self_role)
    check("不能停用自己", self_disable)
    check("不能删除自己", self_delete)

    # ---------- 停用与启用 ----------
    async with session_scope() as session:
        await update_user(new_id, UserUpdate(isActive=False), admin, session)
    async with session_scope() as session:
        disabled_login = await expect_status(
            401, login(LoginRequest(username="engineer1", password="secret123"), session)
        )
    check("停用后无法登录", disabled_login)

    async with session_scope() as session:
        await update_user(new_id, UserUpdate(isActive=True), admin, session)
    async with session_scope() as session:
        enabled_login = await login(
            LoginRequest(username="engineer1", password="secret123"), session
        )
    check("启用后可登录", enabled_login.user["id"] == new_id)

    # ---------- 管理员重置密码 ----------
    async with session_scope() as session:
        reset = await reset_user_password(
            new_id, PasswordReset(newPassword="reset1234"), admin, session
        )
    check("管理员可重置密码", reset.get("userId") == new_id, str(reset))

    async with session_scope() as session:
        reset_login = await login(
            LoginRequest(username="engineer1", password="reset1234"), session
        )
    check("重置后的密码可登录", reset_login.user["id"] == new_id)

    # ---------- 有关联数据的账户不能删除 ----------
    async with session_scope() as session:
        await projects_repo.create(
            session, owner_id=engineer["id"], name="工程师的项目", area=1000.0
        )
        guarded = await expect_status(409, delete_user(engineer["id"], admin, session))
    check("有项目/任务的账户不允许删除", guarded)

    # ---------- 删除无关联数据的账户 ----------
    async with session_scope() as session:
        deleted = await delete_user(new_id, admin, session)
    check("管理员可删除无关联账户", deleted.get("userId") == new_id, str(deleted))

    async with session_scope() as session:
        gone_login = await expect_status(
            401, login(LoginRequest(username="engineer1", password="reset1234"), session)
        )
    check("删除后无法登录", gone_login)

    await dispose_engine()
    failures = [item for item in RESULTS if not item[1]]
    print("-" * 60)
    print(f"共 {len(RESULTS)} 项断言，通过 {len(RESULTS) - len(failures)} 项，失败 {len(failures)} 项")
    if failures:
        print("失败项：")
        for name, _, detail in failures:
            print(f"  - {name} :: {detail}")
        print(f"临时目录保留用于排查: {TMP}")
        return 1
    shutil.rmtree(TMP, ignore_errors=True)
    print("全部通过，临时目录已清理")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
