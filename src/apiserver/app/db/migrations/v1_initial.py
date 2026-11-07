"""v1：初始结构（D11 七张表）。

使用 metadata.create_all + checkfirst，保证空库与半建库都能收敛到同一结构；
后续版本只允许追加，不得改写本文件。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.migrations.base import Migration
from app.models.orm import Base


async def upgrade(conn: AsyncConnection) -> None:
    await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))


migration = Migration(version=1, name="初始结构", upgrade=upgrade)
