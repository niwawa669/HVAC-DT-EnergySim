"""v2：一次性回填历史任务的项目关联（design.md D2）。

改动前启动的任务没有 `project_id`，项目列表里看不到它们。本迁移按（用户, 项目名）
建/复用项目并回填关联，执行一次即结束——此后 `project_id IS NULL` 只表示
"用户删除了项目、任务被解绑"，服务启动不得再回填（D1/D2）。

只用原生 SQL：迁移必须与业务代码解耦，否则日后重构会让历史迁移失效。
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.migrations.base import Migration

VALID_PROJECT_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
FALLBACK_STATUS = "pending"


def _stamp() -> str:
    """与 SQLAlchemy 的 DateTime 存储格式一致，SQLite 与 MySQL 均可接受。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


async def upgrade(conn: AsyncConnection) -> None:
    rows = (
        await conn.execute(
            text(
                "SELECT id, user_id, project_name, building_type, area, status, updated_at "
                "FROM simulation_tasks "
                "WHERE project_id IS NULL AND project_name IS NOT NULL AND project_name <> ''"
            )
        )
    ).mappings().all()

    groups: Dict[Tuple[int, str], List[dict]] = {}
    for row in rows:
        groups.setdefault((int(row["user_id"]), str(row["project_name"])), []).append(dict(row))

    created = 0
    linked = 0
    for (owner_id, name), items in groups.items():
        # 取该组里最近更新的一条，作为项目属性的来源
        latest = max(items, key=lambda item: str(item["updated_at"] or ""))
        project_id = (
            await conn.execute(
                text(
                    "SELECT id FROM projects WHERE owner_id = :owner_id AND name = :name "
                    "ORDER BY updated_at DESC, id DESC LIMIT 1"
                ),
                {"owner_id": owner_id, "name": name},
            )
        ).scalar()

        status = latest["status"] if latest["status"] in VALID_PROJECT_STATUSES else FALLBACK_STATUS
        now = _stamp()
        if project_id is None:
            result = await conn.execute(
                text(
                    "INSERT INTO projects "
                    "(owner_id, name, building_type, area, status, config, created_at, updated_at) "
                    "VALUES (:owner_id, :name, :building_type, :area, :status, NULL, :now, :now)"
                ),
                {
                    "owner_id": owner_id,
                    "name": name,
                    "building_type": latest["building_type"],
                    "area": latest["area"],
                    "status": status,
                    "now": now,
                },
            )
            project_id = getattr(result, "lastrowid", None)
            if project_id is None:
                project_id = (
                    await conn.execute(
                        text(
                            "SELECT id FROM projects WHERE owner_id = :owner_id AND name = :name "
                            "ORDER BY id DESC LIMIT 1"
                        ),
                        {"owner_id": owner_id, "name": name},
                    )
                ).scalar()
            created += 1
        else:
            # 与仓储层原行为一致：任务没带类型/面积时保留项目已有值
            await conn.execute(
                text(
                    "UPDATE projects SET building_type = COALESCE(:building_type, building_type), "
                    "area = COALESCE(:area, area), status = :status, updated_at = :now "
                    "WHERE id = :id"
                ),
                {
                    "building_type": latest["building_type"],
                    "area": latest["area"],
                    "status": status,
                    "now": now,
                    "id": project_id,
                },
            )

        ids = [str(item["id"]) for item in items]
        await conn.execute(
            text(
                "UPDATE simulation_tasks SET project_id = :project_id WHERE id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"project_id": project_id, "ids": ids},
        )
        linked += len(ids)

    if linked:
        print(
            f"📦 一次性回填（v2）：{linked} 条历史任务关联到 {len(groups)} 个项目"
            f"（新建 {created} 个）"
        )


migration = Migration(version=2, name="回填历史任务的项目关联", upgrade=upgrade)
