"""迁移清单：按 version 升序执行，只增不改。"""
from __future__ import annotations

from typing import List

from app.db.migrations.base import Migration
from app.db.migrations.v1_initial import migration as v1_initial
from app.db.migrations.v2_backfill_project_links import migration as v2_backfill

MIGRATIONS: List[Migration] = [v1_initial, v2_backfill]

__all__ = ["MIGRATIONS", "Migration"]
