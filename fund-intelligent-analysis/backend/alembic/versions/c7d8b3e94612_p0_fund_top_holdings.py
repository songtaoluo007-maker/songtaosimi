"""p0_fund_top_holdings

Revision ID: c7d8b3e94612
Revises: a3e5c91d8f02
Create Date: 2026-05-26 21:42:00.000000

P0.3 — 持仓重叠度数据基础表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8b3e94612"
down_revision: Union[str, Sequence[str], None] = "a3e5c91d8f02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "fund_top_holdings" not in tables:
        op.create_table(
            "fund_top_holdings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("stock_code", sa.String(length=10), nullable=False),
            sa.Column("stock_name", sa.String(length=60), nullable=True),
            sa.Column("weight_pct", sa.Numeric(6, 3), nullable=True),
            sa.Column("shares", sa.Numeric(20, 2), nullable=True),
            sa.Column("market_value", sa.Numeric(20, 2), nullable=True),
            sa.Column("quarter", sa.String(length=10), nullable=False),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("fund_code", "stock_code", "quarter",
                                name="uq_fth_fund_stock_quarter"),
        )
        op.create_index("idx_fth_fund_quarter", "fund_top_holdings",
                        ["fund_code", "quarter"])
        op.create_index("idx_fth_stock", "fund_top_holdings", ["stock_code"])


def downgrade() -> None:
    op.drop_index("idx_fth_stock", table_name="fund_top_holdings")
    op.drop_index("idx_fth_fund_quarter", table_name="fund_top_holdings")
    op.drop_table("fund_top_holdings")
