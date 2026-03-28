"""Add github_review_id and github_comment_ids to reviews table.

DEM-150: Idempotent GitHub review publishing requires storing the GitHub
review ID and a map of finding_id → comment_id so that retries can update
existing reviews/comments rather than creating duplicates.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("github_review_id", sa.BigInteger, nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("github_comment_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reviews", "github_comment_ids")
    op.drop_column("reviews", "github_review_id")
