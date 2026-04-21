"""应用配置 - 从环境变量加载。

使用方式:
    from app.core.config import settings
    print(settings.database_url)
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置（从 .env 或环境变量加载）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略 .env 中未在此定义的变量
    )

    # ============ 应用 ============
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "ERP AI Agent"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ============ 数据库 ============
    database_url: str = Field(
        default="postgresql+psycopg://erp_dev:erp_dev_local@localhost:5432/erp_ai",
        description="SQLAlchemy 连接串，使用 psycopg v3 驱动",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # ============ Anthropic ============
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-6"

    # ============ 飞书 ============
    feishu_app_id: str = ""
    feishu_app_secret: SecretStr = SecretStr("")
    feishu_verification_token: SecretStr = SecretStr("")
    feishu_encrypt_key: SecretStr = SecretStr("")

    # ============ 工商 API ============
    qichacha_api_key: SecretStr = SecretStr("")

    # ============ 安全 ============
    secret_key: SecretStr = SecretStr("change-me-to-random-32-chars")
    session_expire_minutes: int = 1440

    # ============ 定时任务 ============
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Asia/Shanghai"

    @property
    def is_development(self) -> bool:
        """是否开发环境。"""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """是否生产环境。"""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """单例模式返回配置（lru_cache 保证全进程只加载一次）。"""
    return Settings()


# 便捷导出
settings = get_settings()
