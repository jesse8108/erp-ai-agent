"""initial placeholder - verify alembic runs

Revision ID: 20260421_0001
Revises: 
Create Date: 2026-04-21 12:00:00.000000

注：这是 W0 的占位 migration，仅用于验证 Alembic 配置正确。
实际建表在 W1 的 autogenerate migration 里完成。

upgrade/downgrade 都是 no-op，执行后数据库不会有任何变化。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260421_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """W0 占位 - 仅确认 alembic 能跑。真正建表在 W1。"""
    # 用一条无副作用的 SQL 证明连接和事务正常
    op.execute("SELECT 1")


def downgrade() -> None:
    """W0 占位回滚。"""
    op.execute("SELECT 1")
