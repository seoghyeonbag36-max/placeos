"""방문자 의견 저장 테이블."""
from alembic import op
import sqlalchemy as sa
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("visitor_feedback",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("page", sa.String(500), nullable=False),
        sa.Column("contact", sa.String(320), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notification_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("visitor_feedback")
