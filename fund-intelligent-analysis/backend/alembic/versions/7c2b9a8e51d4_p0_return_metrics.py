"""p0_return_metrics

Revision ID: 7c2b9a8e51d4
Revises: 8b2107c04b2f
Create Date: 2026-05-26 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c2b9a8e51d4"
down_revision: Union[str, Sequence[str], None] = "8b2107c04b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "portfolio_daily_snapshots" not in tables:
        op.create_table(
            "portfolio_daily_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("total_value", sa.Numeric(16, 2), nullable=False),
            sa.Column("total_cost", sa.Numeric(16, 2), nullable=False),
            sa.Column("total_pnl", sa.Numeric(16, 2), nullable=False),
            sa.Column("cash_flow", sa.Numeric(16, 2), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("snapshot_date", name="uq_portfolio_daily_snapshot_date"),
        )
    index_names = {idx["name"] for idx in inspector.get_indexes("portfolio_daily_snapshots")} if "portfolio_daily_snapshots" in set(sa.inspect(bind).get_table_names()) else set()
    if "ix_portfolio_daily_snapshots_snapshot_date" not in index_names:
        op.create_index("ix_portfolio_daily_snapshots_snapshot_date", "portfolio_daily_snapshots", ["snapshot_date"], unique=False)

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "fund_benchmarks" not in tables:
        op.create_table(
            "fund_benchmarks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fund_code", sa.String(length=10), nullable=False),
            sa.Column("benchmark_symbol", sa.String(length=20), nullable=False),
            sa.Column("benchmark_name", sa.String(length=60), nullable=True),
            sa.Column("benchmark_type", sa.String(length=20), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=True),
            sa.Column("auto_match", sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("fund_code", "benchmark_symbol", name="uq_fund_benchmark_symbol"),
        )
    index_names = {idx["name"] for idx in sa.inspect(bind).get_indexes("fund_benchmarks")}
    if "ix_fund_benchmarks_fund_code" not in index_names:
        op.create_index("ix_fund_benchmarks_fund_code", "fund_benchmarks", ["fund_code"], unique=False)

    holding_columns = {col["name"] for col in sa.inspect(bind).get_columns("holdings")}
    with op.batch_alter_table("holdings") as batch_op:
        if "xirr" not in holding_columns:
            batch_op.add_column(sa.Column("xirr", sa.Numeric(8, 4), nullable=True))
        if "max_drawdown" not in holding_columns:
            batch_op.add_column(sa.Column("max_drawdown", sa.Numeric(8, 4), nullable=True))
        if "max_drawdown_date" not in holding_columns:
            batch_op.add_column(sa.Column("max_drawdown_date", sa.Date(), nullable=True))
        if "recovery_days" not in holding_columns:
            batch_op.add_column(sa.Column("recovery_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("holdings") as batch_op:
        batch_op.drop_column("recovery_days")
        batch_op.drop_column("max_drawdown_date")
        batch_op.drop_column("max_drawdown")
        batch_op.drop_column("xirr")

    op.drop_index("ix_fund_benchmarks_fund_code", table_name="fund_benchmarks")
    op.drop_table("fund_benchmarks")
    op.drop_index("ix_portfolio_daily_snapshots_snapshot_date", table_name="portfolio_daily_snapshots")
    op.drop_table("portfolio_daily_snapshots")
