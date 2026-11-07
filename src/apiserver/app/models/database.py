"""兼容入口：旧的 models.database 导出。

实际实现位于 app/db/session.py（引擎/会话）与 app/models/orm.py（模型）。
"""
from app.db.session import engine, get_db, get_engine, get_session_factory, session_scope
from app.models.orm import Base

__all__ = ["Base", "engine", "get_db", "get_engine", "get_session_factory", "session_scope"]
