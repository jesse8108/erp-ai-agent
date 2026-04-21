"""数据库会话管理（异步）。

使用方式:
    from app.db.session import get_session
    
    async def some_endpoint(session: AsyncSession = Depends(get_session)):
        result = await session.execute(select(User))
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ============ 引擎 ============
# psycopg v3 在 SQLAlchemy 2.0 里的 URL 前缀: postgresql+psycopg://
# 不要和 psycopg2 混用（那是 postgresql+psycopg2://）
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,  # 每次从池里拿连接前 ping 一下，防止旧连接失效
    echo=settings.is_development,  # 开发环境打印 SQL
)

# ============ SessionMaker ============
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 后不过期对象（便于后续访问）
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 用的会话生成器。

    自动管理 commit/rollback/close。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
