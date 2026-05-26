"""p0_fund_managers

Revision ID: a3e5c91d8f02
Revises: 7c2b9a8e51d4
Create Date: 2026-05-26 21:30:00.000000

P0.2 — 基金经理信息 + 离职预警

新增表：
- fund_managers: 基金历任/现任经理
- manager_alerts: 经理变更预警事件
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3e5c91d8f02"
down_revision: Union[str, Sequence[str], None] = "7c2b9a8e51d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "fund_managers" not in tables:
        op.create_table(
            "fund_managers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("manager_name", sa.String(length=60), nullable=False),
            sa.Column("manager_id", sa.String(length=40), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("tenure_return_pct", sa.Numeric(10, 2), nullable=True),
            sa.Column("tenure_annualized_pct", sa.Numeric(8, 2), nullable=True),
            sa.Column("is_current", sa.Boolean(), nullable=True),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("fund_code", "manager_name", "start_date",
                                name="uq_fund_manager_start"),
        )
        op.create_index("ix_fund_managers_fund_code", "fund_managers", ["fund_code"])
        op.create_index("idx_fm_current", "fund_managers", ["fund_code", "is_current"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "manager_alerts" not in tables:
        op.create_table(
            "manager_alerts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("alert_type", sa.String(length=40), nullable=False),
            sa.Column("old_manager", sa.String(length=60), nullable=True),
            sa.Column("new_manager", sa.String(length=60), nullable=True),
            sa.Column("alert_date", sa.Date(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("severity", sa.String(length=10), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_ma_fund_unread", "manager_alerts",
                        ["fund_code", "is_read"])
        op.create_index("idx_ma_severity", "manager_alerts",
                        ["severity", "alert_date"])


def downgrade() -> None:
    op.drop_index("idx_ma_severity", table_name="manager_alerts")
    op.drop_index("idx_ma_fund_unread", table_name="manager_alerts")
    op.drop_table("manager_alerts")

    op.drop_index("idx_fm_current", table_name="fund_managers")
    op.drop_index("ix_fund_managers_fund_code", table_name="fund_managers")
    op.drop_table("fund_managers")
