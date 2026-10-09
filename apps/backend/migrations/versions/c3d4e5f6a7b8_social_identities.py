"""네이버·카카오 로그인 식별자. 기존 계정과 이메일로 자동 연결하지 않는다."""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("social_identities",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "subject", name="uq_social_provider_subject"))
    op.create_index("ix_social_identities_user_id", "social_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_social_identities_user_id", table_name="social_identities")
    op.drop_table("social_identities")
