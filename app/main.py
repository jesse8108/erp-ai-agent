"""FastAPI 应用入口。

启动方式:
    开发: uvicorn app.main:app --reload
    生产: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    docker: docker compose up
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import health
from app.core.config import settings

# ============ 日志 ============
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============ 生命周期 ============
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用启动 / 关闭钩子。"""
    # Startup
    logger.info("=" * 50)
    logger.info(f"{settings.app_name} v{settings.app_version} starting...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Anthropic model: {settings.anthropic_model}")
    logger.info("=" * 50)

    yield  # 应用运行期

    # Shutdown
    logger.info("Shutting down...")
    # 后续加：关闭调度器、清理连接池等
    from app.db.session import engine

    await engine.dispose()
    logger.info("Bye.")


# ============ 应用实例 ============
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="ERP 业务管理 AI 对话系统",
    lifespan=lifespan,
    # 生产环境关闭交互式 API 文档
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)


# ============ 路由注册 ============
app.include_router(health.router)


# ============ 根路径 ============
@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """欢迎页。"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs" if settings.is_development else "disabled",
    }


# ============ 全局异常 ============
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """兜底异常处理 - 避免堆栈泄漏到客户端。"""
    logger.exception(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )
