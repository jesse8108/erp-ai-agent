"""健康检查端点。

提供三个级别的健康检查:
- /health: liveness（应用是否活着）
- /health/ready: readiness（是否能接流量 - 含数据库连接）
- /health/info: 详细信息（版本、环境、扩展等）
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict[str, str]:
    """基本活性检查。"""
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """就绪检查 - 验证数据库连接 + 扩展是否就位。"""
    checks: dict[str, Any] = {}

    # 1. 基础连接
    try:
        result = await session.execute(text("SELECT version()"))
        pg_version = result.scalar_one()
        checks["database"] = {"status": "ok", "version": pg_version}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # 2. pg_trgm 扩展（公司/型号简称 fallback 必备）
    try:
        result = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
        )
        has_trgm = result.scalar_one_or_none() is not None
        checks["pg_trgm"] = {"status": "ok" if has_trgm else "missing"}
    except Exception as e:
        checks["pg_trgm"] = {"status": "error", "error": str(e)}

    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }


@router.get("/info")
async def info() -> dict[str, Any]:
    """详细信息（仅开发环境可见）。"""
    if not settings.is_development:
        return {"message": "info endpoint is disabled in non-development"}

    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "app_env": settings.app_env,
        "anthropic_model": settings.anthropic_model,
        "scheduler_enabled": settings.scheduler_enabled,
    }
