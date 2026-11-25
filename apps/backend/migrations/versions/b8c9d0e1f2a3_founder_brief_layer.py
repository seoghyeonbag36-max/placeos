"""입점 희망서 · 조건 제안서 층 — 창업자 희망서(3단계 공개) · 희망서 공개 동의 · 조건 제안/팝업 신청 ·
매물 설비 칸 · 문의를 연 쪽/계약 진행 방법 (2026-11-21 · docs/decision-founder-brief-2026-11-21.md).

models/direct.py 와 칼럼·인덱스·FK·고유 제약이 정확히 같아야 한다(tests/test_migration.py 의 alembic check).
⚠ 프로덕션(Neon)에는 배포와 따로 수동으로 올린다 — 사용자가 그 턴에 명시할 때만. a7b8c9d0e1f2(직거래 층) 다음이다.
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 매물 설비 — None = 건물주가 적지 않음(모름)
    op.add_column("direct_listings", sa.Column("exhaust_ok", sa.Boolean(), nullable=True))
    op.add_column("direct_listings", sa.Column("power_kw", sa.Integer(), nullable=True))
    op.add_column("direct_listings", sa.Column("water_ok", sa.Boolean(), nullable=True))
    # 문의를 연 쪽 · 계약 진행 방법 — 기존 행은 창업자가 연 문의·미정이다
    op.add_column("direct_inquiries",
                  sa.Column("initiated_by", sa.String(16), nullable=False, server_default="founder"))
    op.add_column("direct_inquiries",
                  sa.Column("contract_path", sa.String(16), nullable=False, server_default=""))

    op.create_table(
        "direct_briefs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("industry_key", sa.String(32), nullable=False),
        sa.Column("area_min_m2", sa.Float(), nullable=True),
        sa.Column("area_max_m2", sa.Float(), nullable=True),
        sa.Column("floor_bands", sa.JSON(), nullable=False),
        sa.Column("needs_exhaust", sa.Boolean(), nullable=False),
        sa.Column("needs_water", sa.Boolean(), nullable=False),
        sa.Column("power_kw_min", sa.Integer(), nullable=True),
        sa.Column("rent_cap_manwon", sa.Integer(), nullable=True),
        sa.Column("deposit_cap_manwon", sa.Integer(), nullable=True),
        sa.Column("desired_start", sa.Date(), nullable=True),
        sa.Column("district_ids", sa.JSON(), nullable=False),
        sa.Column("popup_first", sa.Boolean(), nullable=False),
        sa.Column("accept_invites", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("business_stage", sa.String(16), nullable=False),
        sa.Column("funding_total_manwon", sa.Integer(), nullable=True),
        sa.Column("funding_own_manwon", sa.Integer(), nullable=True),
        sa.Column("unit_price_won", sa.Integer(), nullable=True),
        sa.Column("variable_cost_pct", sa.Float(), nullable=True),
        sa.Column("other_fixed_manwon", sa.Integer(), nullable=True),
        sa.Column("open_days", sa.Integer(), nullable=True),
        sa.Column("target_daily_units", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_briefs_user_id", "direct_briefs", ["user_id"], unique=True)

    op.create_table(
        "direct_brief_disclosures",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("brief_id", sa.String(32), sa.ForeignKey("direct_briefs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brief_id", "owner_user_id", name="uq_direct_brief_disclosure"),
    )
    op.create_index("ix_direct_brief_disclosures_brief_id", "direct_brief_disclosures", ["brief_id"])
    op.create_index("ix_direct_brief_disclosures_owner_user_id", "direct_brief_disclosures", ["owner_user_id"])

    op.create_table(
        "direct_offers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("inquiry_id", sa.String(32), sa.ForeignKey("direct_inquiries.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("proposer_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rent_manwon", sa.Integer(), nullable=True),
        sa.Column("deposit_manwon", sa.Integer(), nullable=True),
        sa.Column("rent_free_months", sa.Integer(), nullable=True),
        sa.Column("term_months", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("popup_days", sa.Integer(), nullable=True),
        sa.Column("popup_daily_manwon", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_offers_inquiry_id", "direct_offers", ["inquiry_id"])


def downgrade() -> None:
    op.drop_table("direct_offers")
    op.drop_table("direct_brief_disclosures")
    op.drop_table("direct_briefs")
    # SQLite 는 칼럼을 바로 못 지운다 — batch 로 표를 다시 만든다(Postgres 에서는 그냥 ALTER)
    with op.batch_alter_table("direct_inquiries") as batch:
        batch.drop_column("contract_path")
        batch.drop_column("initiated_by")
    with op.batch_alter_table("direct_listings") as batch:
        batch.drop_column("water_ok")
        batch.drop_column("power_kw")
        batch.drop_column("exhaust_ok")
