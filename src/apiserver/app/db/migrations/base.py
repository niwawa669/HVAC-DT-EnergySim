"""迁移基类：每条迁移是一个版本号 + 名称 + 幂等的 upgrade 函数。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    upgrade: Callable[[AsyncConnection], Awaitable[None]]
