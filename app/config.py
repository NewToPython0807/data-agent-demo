"""配置与日志模块（T03）。

- 仅使用标准库：从项目根目录 .env 文件或环境变量读取配置，不引入额外依赖。
- 提供基础日志输出（控制台 + 滚动文件），异常均可被记录。
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 项目根目录（app/ 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent

_logger = logging.getLogger(__name__)


def _load_dotenv(path: Path) -> dict:
    """极简 .env 解析：KEY=VALUE 每行一条，支持 # 注释与空行。"""
    values: dict = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


@dataclass
class Settings:
    """全局配置（一次性加载）。"""

    app_name: str = "智能问数 Data Agent"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # 数据库
    database_path: str = "data/agent.db"

    # 会话（签名 Cookie）
    secret_key: str = ""
    session_cookie_name: str = "agent_session"
    session_max_age_seconds: int = 7 * 24 * 3600  # 7 天

    # 单账号
    account_username: str = ""
    account_password_hash: str = ""  # bcrypt 哈希（T07 生成与校验）

    # DeepSeek（自然语言 → SQL）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 60

    # 多轮追问上下文（最近 N 轮，可配置）
    multi_turn_context_rounds: int = 5

    # 上传大小上限（MB）
    max_upload_mb: int = 50

    # SQL 自动纠错重试次数（V3）
    max_sql_corrections: int = 2

    @classmethod
    def load(cls) -> "Settings":
        file_values = _load_dotenv(BASE_DIR / ".env")

        def get(name: str, default: str = "") -> str:
            # 环境变量优先于 .env 文件
            return os.environ.get(name, file_values.get(name, default))

        secret = get("SECRET_KEY", "")
        if not secret:
            secret = secrets.token_hex(32)
            _logger.warning(
                "SECRET_KEY 未设置，已随机生成（重启后所有会话失效）。"
                "生产环境请在 .env 中配置固定随机字符串。"
            )

        return cls(
            app_name=get("APP_NAME", "智能问数 Data Agent"),
            host=get("HOST", "0.0.0.0"),
            port=int(get("PORT", "8000")),
            log_level=get("LOG_LEVEL", "INFO"),
            database_path=get("DATABASE_PATH", "data/agent.db"),
            secret_key=secret,
            session_cookie_name=get("SESSION_COOKIE_NAME", "agent_session"),
            session_max_age_seconds=int(get("SESSION_MAX_AGE_SECONDS", str(7 * 24 * 3600))),
            account_username=get("ACCOUNT_USERNAME", ""),
            account_password_hash=get("ACCOUNT_PASSWORD_HASH", ""),
            deepseek_api_key=get("DEEPSEEK_API_KEY", ""),
            deepseek_base_url=get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=get("DEEPSEEK_MODEL", "deepseek-chat"),
            llm_timeout_seconds=int(get("LLM_TIMEOUT_SECONDS", "60")),
            multi_turn_context_rounds=int(get("MULTI_TURN_CONTEXT_ROUNDS", "5")),
            max_upload_mb=int(get("MAX_UPLOAD_MB", "50")),
            max_sql_corrections=int(get("MAX_SQL_CORRECTIONS", "2")),
        )

    @property
    def database_path_abs(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else BASE_DIR / p

    def ensure_dirs(self) -> None:
        """确保数据目录存在（数据库、日志、上传缓存等）。"""
        db_path = self.database_path_abs
        db_path.parent.mkdir(parents=True, exist_ok=True)
        (BASE_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)


def setup_logging(level: str = "INFO") -> None:
    """基础日志：控制台 + data/logs/app.log 滚动文件（单文件 5MB × 3 份）。"""
    root = logging.getLogger()
    if root.handlers:
        return
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    log_dir = BASE_DIR / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    root.setLevel(level.upper())
    _logger.info("日志初始化完成，级别=%s，日志文件=%s", root.level, log_dir / "app.log")


settings = Settings.load()
