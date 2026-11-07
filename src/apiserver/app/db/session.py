"""数据库引擎与会话（D6/D13）。

- engine 惰性创建，但导入本模块时会创建一个（并确保存储目录可用）
- get_db() 供 FastAPI 依赖使用，成功提交、异常回滚
- session_scope() 供后台任务使用，语义与 get_db 一致
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import ensure_storage_dirs, settings

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _create_engine() -> AsyncEngine:
    ensure_storage_dirs()
    url = settings.database_url
    connect_args = {"timeout": 30} if _is_sqlite(url) else {}
    engine = create_async_engine(
        url,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if _is_sqlite(url):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：一次请求一个会话，成功提交、异常回滚。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """后台任务用的事务边界：正常退出提交，异常回滚。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """释放连接池（关闭服务或测试模拟重启时调用）。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


# 兼容旧代码：from app.models.database import engine
engine = get_engine()
