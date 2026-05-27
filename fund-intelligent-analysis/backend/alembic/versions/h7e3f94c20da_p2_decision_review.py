"""p2_decision_review

Revision ID: h7e3f94c20da
Revises: g6c2d83a91fb
Create Date: 2026-05-26 23:55:00.000000

P2.2 — 用户决策复盘
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h7e3f94c20da"
down_revision: Union[str, Sequence[str], None] = "g6c2d83a91fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "user_decision_reviews" not in tables:
        op.create_table(
            "user_decision_reviews",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("advice_id", sa.Integer(), nullable=True),
            sa.Column("fund_code", sa.String(length=10), nullable=True),
            sa.Column("decision_date", sa.Date(), nullable=False),
            sa.Column("user_action", sa.String(length=20), nullable=True),
            sa.Column("decision_type", sa.String(length=20), nullable=True),
            sa.Column("decision_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("market_state_then", sa.String(length=20), nullable=True),
            sa.Column("portfolio_value_then", sa.Numeric(16, 2), nullable=True),
            sa.Column("fund_nav_then", sa.Numeric(10, 4), nullable=True),
            sa.Column("portfolio_value_30d", sa.Numeric(16, 2), nullable=True),
            sa.Column("fund_nav_30d", sa.Numeric(10, 4), nullable=True),
            sa.Column("market_state_30d", sa.String(length=20), nullable=True),
            sa.Column("outcome", sa.String(length=20), nullable=True),
            sa.Column("outcome_pct", sa.Numeric(6, 2), nullable=True),
            sa.Column("lesson", sa.Text(), nullable=True),
            sa.Column("is_reviewed", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_udr_date", "user_decision_reviews", ["decision_date"])
        op.create_index("idx_udr_pending", "user_decision_reviews", ["is_reviewed", "decision_date"])

    tables = set(sa.inspect(bind).get_table_names())
    if "behavior_bias_snapshots" not in tables:
        op.create_table(
            "behavior_bias_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("month", sa.String(length=7), nullable=False),
            sa.Column("chase_high_score", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("cut_low_score", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("frequent_trade_score", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("avg_holding_days", sa.Numeric(8, 1), nullable=True, server_default="0"),
            sa.Column("follow_advice_rate", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("follow_win_rate", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("reverse_win_rate", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("self_win_rate", sa.Numeric(5, 2), nullable=True, server_default="0"),
            sa.Column("biggest_regret", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("month", name="uq_bbs_month"),
        )


def downgrade() -> None:
    op.drop_table("behavior_bias_snapshots")
    op.drop_index("idx_udr_pending", table_name="user_decision_reviews")
    op.drop_index("idx_udr_date", table_name="user_decision_reviews")
    op.drop_table("user_decision_reviews")
