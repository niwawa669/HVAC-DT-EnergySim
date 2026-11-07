import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings

# 仓库根：src/apiserver/app/config.py -> app -> apiserver -> src -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_DIR = REPO_ROOT / "data"


def normalize_database_url(raw: str, data_dir: Path) -> str:
    """把常见的同步 DSN 归一化为异步方言。

    - 空值 -> <data_dir>/hvac.db 的 SQLite 异步库
    - sqlite:///x -> sqlite+aiosqlite:///x
    - mysql://x  -> mysql+aiomysql://x
    - postgres://x -> postgresql+asyncpg://x
    """
    url = (raw or "").strip()
    if not url:
        return f"sqlite+aiosqlite:///{(Path(data_dir) / 'hvac.db').as_posix()}"
    if url.startswith("sqlite+aiosqlite://"):
        return url
    if url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + url[len("sqlite://"):]
    if url.startswith("mysql+pymysql://"):
        return "mysql+aiomysql://" + url[len("mysql+pymysql://"):]
    if url.startswith("mysql://"):
        return "mysql+aiomysql://" + url[len("mysql://"):]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "HVAC仿真系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ===== 持久化配置（D1/D10）=====
    # DATABASE_URL 留空时落到 DATA_DIR/hvac.db；支持 sqlite:///、mysql:// 等旧写法
    DATABASE_URL: str = ""
    DATA_DIR: Path = _DEFAULT_DATA_DIR
    DATASETS_DIR: Optional[Path] = None
    REPORTS_DIR: Optional[Path] = None
    DB_AUTO_MIGRATE: bool = True
    DB_ECHO: bool = False

    # Redis 配置 (Celery)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB

    # CORS 配置
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:5174"]

    # 算法路径
    ALGORITHM_PATH: str = "../algorithm"

    class Config:
        env_file = ".env"
        case_sensitive = True

    # ===== 派生的存储路径（只读）=====
    @property
    def data_dir(self) -> Path:
        return Path(self.DATA_DIR).expanduser()

    @property
    def datasets_dir(self) -> Path:
        if self.DATASETS_DIR:
            return Path(self.DATASETS_DIR).expanduser()
        return self.data_dir / "datasets"

    @property
    def reports_dir(self) -> Path:
        # 兼容既有的 HVAC_REPORTS_DIR 环境变量
        env = os.environ.get("HVAC_REPORTS_DIR")
        if env:
            return Path(env).expanduser()
        if self.REPORTS_DIR:
            return Path(self.REPORTS_DIR).expanduser()
        return self.data_dir / "reports"

    @property
    def database_url(self) -> str:
        return normalize_database_url(self.DATABASE_URL, self.data_dir)


def ensure_storage_dirs(settings_obj: Optional[Settings] = None) -> None:
    """确保存储目录存在且可写；不可用时抛可读错误（不得静默落盘）。"""
    s = settings_obj or settings
    for directory in (s.data_dir, s.datasets_dir, s.reports_dir):
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(f"存储目录不可用: {directory}（{exc}）") from exc
        probe = Path(directory) / ".write_probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise RuntimeError(f"存储目录不可写: {directory}（{exc}）") from exc


settings = Settings()
