"""p1_investment_plans

Revision ID: d9e2a7f15834
Revises: c7d8b3e94612
Create Date: 2026-05-26 21:50:00.000000

P1.1 — 定投计划 + 执行记录
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e2a7f15834"
down_revision: Union[str, Sequence[str], None] = "c7d8b3e94612"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "investment_plans" not in tables:
        op.create_table(
            "investment_plans",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("plan_name", sa.String(length=60), nullable=True),
            sa.Column("plan_type", sa.String(length=10), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("day_of_period", sa.Integer(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("target_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("auto_execute", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_ip_active_fund", "investment_plans", ["is_active", "fund_code"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "investment_plan_executions" not in tables:
        op.create_table(
            "investment_plan_executions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("scheduled_date", sa.Date(), nullable=False),
            sa.Column("executed", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("executed_at", sa.DateTime(), nullable=True),
            sa.Column("trade_id", sa.Integer(), nullable=True),
            sa.Column("actual_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("actual_shares", sa.Numeric(16, 4), nullable=True),
            sa.Column("nav_price", sa.Numeric(10, 4), nullable=True),
            sa.Column("skip_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["plan_id"], ["investment_plans.id"]),
            sa.UniqueConstraint("plan_id", "scheduled_date", name="uq_ipe_plan_date"),
        )
        op.create_index("idx_ipe_due", "investment_plan_executions", ["executed", "scheduled_date"])


def downgrade() -> None:
    op.drop_index("idx_ipe_due", table_name="investment_plan_executions")
    op.drop_table("investment_plan_executions")
    op.drop_index("idx_ip_active_fund", table_name="investment_plans")
    op.drop_table("investment_plans")
