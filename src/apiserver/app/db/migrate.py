"""自建版本化迁移器（D2）。

用法：
    python -m app.db.migrate upgrade   # 补齐未执行的版本
    python -m app.db.migrate status    # 输出当前版本、已执行清单与待执行数量
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.db.migrations import MIGRATIONS
from app.db.session import dispose_engine, get_engine
from app.models.orm import Base, SchemaMigration


async def _ensure_version_table(conn: AsyncConnection) -> None:
    table = Base.metadata.tables["schema_migrations"]
    await conn.run_sync(lambda sync_conn: table.create(sync_conn, checkfirst=True))


def _applied_versions():
    return select(SchemaMigration.version, SchemaMigration.name).order_by(SchemaMigration.version)


async def upgrade(engine: Optional[AsyncEngine] = None) -> List[int]:
    """按序执行未记录的迁移，返回本次新执行的版本列表。"""
    eng = engine or get_engine()
    executed: List[int] = []
    async with eng.begin() as conn:
        await _ensure_version_table(conn)
        rows = (await conn.execute(_applied_versions())).all()
        applied = {row[0] for row in rows}
        for migration in MIGRATIONS:
            if migration.version in applied:
                continue
            await migration.upgrade(conn)
            await conn.execute(
                SchemaMigration.__table__.insert().values(
                    version=migration.version,
                    name=migration.name,
                    applied_at=datetime.now(),
                )
            )
            executed.append(migration.version)
    return executed


async def status(engine: Optional[AsyncEngine] = None) -> dict:
    """返回结构版本状态（供 CLI 与运维自查）。

    只读：表不存在时按"全部待执行"处理，不在查询路径上隐式建表。
    """
    eng = engine or get_engine()
    try:
        async with eng.connect() as conn:
            rows = (await conn.execute(_applied_versions())).all()
    except (OperationalError, ProgrammingError):
        rows = []
    applied = [{"version": row[0], "name": row[1]} for row in rows]
    applied_versions = {item["version"] for item in applied}
    pending = [m.version for m in MIGRATIONS if m.version not in applied_versions]
    current = max(applied_versions) if applied_versions else 0
    return {
        "currentVersion": current,
        "applied": applied,
        "pending": pending,
        "totalMigrations": len(MIGRATIONS),
    }


async def ensure_schema_ready(engine: Optional[AsyncEngine] = None) -> None:
    """DB_AUTO_MIGRATE=false 时用于启动自检：缺结构就以可读错误拒绝启动。"""
    state = await status(engine)
    if state["pending"]:
        raise RuntimeError(
            "数据库结构不完整（待执行迁移: "
            + ", ".join(str(v) for v in state["pending"])
            + "），且已关闭自动迁移；请先执行 python -m app.db.migrate upgrade"
        )


def main(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    command = (args[0] if args else "status").strip().lower()

    async def _run():
        try:
            if command == "upgrade":
                executed = await upgrade()
                if executed:
                    print("已执行迁移版本: " + ", ".join(str(v) for v in executed))
                else:
                    print("无待执行迁移")
                print(json.dumps(await status(), ensure_ascii=False, indent=2))
                return 0
            if command == "status":
                print(json.dumps(await status(), ensure_ascii=False, indent=2))
                return 0
            print(f"未知命令: {command}（可用: upgrade, status）", file=sys.stderr)
            return 2
        finally:
            await dispose_engine()

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
