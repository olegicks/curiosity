"""estimate questions

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-23 10:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questions", sa.Column("estimate", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.drop_constraint(op.f("ck_questions_type_allowed"), "questions", type_="check")
    op.create_check_constraint(
        op.f("ck_questions_type_allowed"),
        "questions",
        "type IN ('single_choice','multi_select','true_false','estimate')",
    )
    op.add_column("lesson_attempt_answers", sa.Column("value", sa.Double(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson_attempt_answers", "value")
    op.execute("DELETE FROM questions WHERE type = 'estimate'")
    op.drop_constraint(op.f("ck_questions_type_allowed"), "questions", type_="check")
    op.create_check_constraint(
        op.f("ck_questions_type_allowed"),
        "questions",
        "type IN ('single_choice','multi_select','true_false')",
    )
    op.drop_column("questions", "estimate")
