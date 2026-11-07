"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# revision 标识由 Alembic 生成。它把每个数据库结构版本串成一条可升级、可回退的链。
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """把数据库从上一版本升级到当前版本。"""
    # Alembic --autogenerate 会把 Base.metadata 与实际数据库的差异写入这里。
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """把数据库回退到上一版本，便于开发阶段撤销一次结构变更。"""
    # 每个 upgrade 的结构操作都应有对应的 downgrade，保证版本历史可逆。
    ${downgrades if downgrades else "pass"}
