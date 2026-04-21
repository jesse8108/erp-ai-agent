"""健康检查端点测试。

运行:
    pytest tests/test_health.py -v
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root_returns_app_info() -> None:
    """根路径应返回应用名和版本。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ERP AI Agent"
    assert data["status"] == "running"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    """基本健康检查应返回 ok。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# 注：test_health_ready 需要真实的 DB 连接，
# 放到 W1 再补（建表后跑集成测试）。
