"""층 배치도 사진 — 건물주가 매물(층)마다 올리는 실제 배치도 한 장 (2026-11-22 · docs/decision-pppp-owner-founder-2026-11-22.md).

models/direct.py 와 칼럼·인덱스·FK·고유 제약이 정확히 같아야 한다(tests/test_migration.py 의 alembic check).
⚠ 프로덕션(Neon)에는 배포와 따로 수동으로 올린다 — 사용자가 그 턴에 명시할 때만. b8c9d0e1f2a3(입점 희망서 층) 다음이다.
   표가 아직 없는 DB 에서도 앱은 선다 — 배치도 칸만 「준비 중」(503)이고 매물 기능은 그대로다(services/direct_floor_plans.table_ready).
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_floor_plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("listing_id", sa.String(32), sa.ForeignKey("direct_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mime", sa.String(16), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_direct_floor_plans_listing_id", "direct_floor_plans", ["listing_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_direct_floor_plans_listing_id", table_name="direct_floor_plans")
    op.drop_table("direct_floor_plans")
