"""p1_user_profile

Revision ID: f5b3a64e29d8
Revises: e4f1c82b9d76
Create Date: 2026-05-26 22:02:00.000000

P1.3 — 用户画像字段（用于 AI 个性化建议）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5b3a64e29d8"
down_revision: Union[str, Sequence[str], None] = "e4f1c82b9d76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROFILE_COLUMNS = [
    ("birth_year", sa.Integer()),
    ("retirement_target_year", sa.Integer()),
    ("investment_horizon_years", sa.Integer()),
    ("funds_purpose", sa.String(length=30)),
    ("target_annual_return", sa.Numeric(5, 2)),
    ("max_acceptable_drawdown", sa.Numeric(5, 2)),
    ("risk_appetite", sa.String(length=20)),
    ("monthly_disposable_income", sa.Numeric(12, 2)),
    ("profile_updated_at", sa.DateTime()),
    ("profile_notes", sa.Text()),
]


def upgrade() -> None:
    bind = op.get_bind()
    existing = {col["name"] for col in sa.inspect(bind).get_columns("user_accounts")}
    with op.batch_alter_table("user_accounts") as batch_op:
        for name, col_type in PROFILE_COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_accounts") as batch_op:
        for name, _ in reversed(PROFILE_COLUMNS):
            batch_op.drop_column(name)
