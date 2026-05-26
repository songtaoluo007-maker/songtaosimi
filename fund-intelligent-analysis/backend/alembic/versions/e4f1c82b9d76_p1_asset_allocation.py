"""p1_asset_allocation

Revision ID: e4f1c82b9d76
Revises: d9e2a7f15834
Create Date: 2026-05-26 22:00:00.000000

P1.2 — 目标资产配置 + 再平衡预警
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f1c82b9d76"
down_revision: Union[str, Sequence[str], None] = "d9e2a7f15834"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "asset_allocation_targets" not in tables:
        op.create_table(
            "asset_allocation_targets",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("asset_class", sa.String(length=20), nullable=False),
            sa.Column("target_pct", sa.Numeric(5, 2), nullable=False),
            sa.Column("tolerance_pct", sa.Numeric(4, 2), nullable=False, server_default="5.0"),
            sa.Column("notes", sa.String(length=200), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("asset_class", name="uq_aat_class"),
        )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "rebalance_alerts" not in tables:
        op.create_table(
            "rebalance_alerts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("detect_date", sa.Date(), nullable=False),
            sa.Column("asset_class", sa.String(length=20), nullable=False),
            sa.Column("target_pct", sa.Numeric(5, 2), nullable=True),
            sa.Column("current_pct", sa.Numeric(5, 2), nullable=True),
            sa.Column("deviation_pct", sa.Numeric(5, 2), nullable=True),
            sa.Column("suggested_action", sa.String(length=10), nullable=True),
            sa.Column("suggested_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("is_acknowledged", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_ra_unack", "rebalance_alerts", ["is_acknowledged", "detect_date"])


def downgrade() -> None:
    op.drop_index("idx_ra_unack", table_name="rebalance_alerts")
    op.drop_table("rebalance_alerts")
    op.drop_table("asset_allocation_targets")
