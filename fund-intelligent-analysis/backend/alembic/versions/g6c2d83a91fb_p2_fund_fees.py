"""p2_fund_fees

Revision ID: g6c2d83a91fb
Revises: f5b3a64e29d8
Create Date: 2026-05-26 23:40:00.000000

P2.1 — 基金费率表 + 每日计提账本
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6c2d83a91fb"
down_revision: Union[str, Sequence[str], None] = "f5b3a64e29d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "fund_fee_schedules" not in tables:
        op.create_table(
            "fund_fee_schedules",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("purchase_fee_rate", sa.Numeric(7, 5), nullable=True, server_default="0"),
            sa.Column("purchase_fee_discount", sa.Numeric(4, 3), nullable=True, server_default="0.1"),
            sa.Column("redemption_fee_schedule", sa.Text(), nullable=True),
            sa.Column("management_fee_rate", sa.Numeric(7, 5), nullable=True, server_default="0"),
            sa.Column("custody_fee_rate", sa.Numeric(7, 5), nullable=True, server_default="0"),
            sa.Column("sales_service_fee_rate", sa.Numeric(7, 5), nullable=True, server_default="0"),
            sa.Column("source", sa.String(length=20), nullable=True, server_default="manual"),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("fund_code", name="uq_ffs_fund"),
        )
        op.create_index("ix_fund_fee_schedules_fund_code", "fund_fee_schedules", ["fund_code"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "fee_daily_accruals" not in tables:
        op.create_table(
            "fee_daily_accruals",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("accrual_date", sa.Date(), nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("holding_value", sa.Numeric(16, 2), nullable=True, server_default="0"),
            sa.Column("daily_mgmt_fee", sa.Numeric(12, 4), nullable=True, server_default="0"),
            sa.Column("daily_custody_fee", sa.Numeric(12, 4), nullable=True, server_default="0"),
            sa.Column("daily_sales_fee", sa.Numeric(12, 4), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("accrual_date", "fund_code", name="uq_fda_date_fund"),
        )
        op.create_index("idx_fda_date", "fee_daily_accruals", ["accrual_date"])


def downgrade() -> None:
    op.drop_index("idx_fda_date", table_name="fee_daily_accruals")
    op.drop_table("fee_daily_accruals")
    op.drop_index("ix_fund_fee_schedules_fund_code", table_name="fund_fee_schedules")
    op.drop_table("fund_fee_schedules")
