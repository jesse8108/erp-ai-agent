"""Alembic 异步迁移环境配置。

关键点:
- 从 app.core.config 读取 DATABASE_URL（单一真源）
- 使用异步引擎（跟 app 保持一致）
- autogenerate 时从 app.db.base.Base 读取元数据
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 导入应用配置和 ORM Base
from app.core.config import settings
from app.db.base import Base

# 重要: W1 建完 model 后，需要在这里 import 所有 model，
# 否则 autogenerate 发现不了表。示例:
# from app.db.models import contracts, companies, users  # noqa

# Alembic 配置对象
config = context.config

# 从 settings 覆盖 alembic.ini 中的 url
config.set_main_option("sqlalchemy.url", settings.database_url)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 读取元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline 模式 - 生成 SQL 而不执行。

    用于: alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # 检测字段类型变化
        compare_server_default=True,  # 检测默认值变化
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在给定 connection 上执行迁移。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式执行迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # migration 用完就扔
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Online 模式 - 连数据库执行。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
