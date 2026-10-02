"""개인 사업 정보와 로그아웃 토큰 폐기 저장소."""
from alembic import op
import sqlalchemy as sa
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("business_workspaces",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("revoked_tokens", sa.Column("token_hash", sa.String(64), primary_key=True))


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_table("business_workspaces")
