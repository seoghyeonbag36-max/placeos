"""개인 캠페인 원장과 동시 수정 버전."""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("program_campaigns",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False))
    op.create_index("ix_program_campaigns_user_id", "program_campaigns", ["user_id"])


def downgrade() -> None:
    op.drop_table("program_campaigns")
