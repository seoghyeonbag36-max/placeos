"""직거래 연결 층 — 건물주 직접 등록 매물 · 소유자 확인 · 문의/메시지 · 신고 · 정액 상품 신청 (2026-11-18).

models/direct.py 와 칼럼·인덱스·FK 가 정확히 같아야 한다(tests/test_migration.py 의 alembic check).
⚠ 프로덕션(Neon)에는 배포와 따로 수동으로 올린다 — 사용자가 그 턴에 명시할 때만.
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_listings",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("poster_relation", sa.String(16), nullable=False),
        sa.Column("district_id", sa.String(64), nullable=True),
        sa.Column("building_id", sa.String(64), nullable=True),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("unit_label", sa.String(50), nullable=False),
        sa.Column("area_m2", sa.Float(), nullable=False),
        sa.Column("use_type", sa.String(40), nullable=False),
        sa.Column("ledger_use", sa.String(60), nullable=False),
        sa.Column("deal_type", sa.String(16), nullable=False),
        sa.Column("deposit_manwon", sa.Integer(), nullable=False),
        sa.Column("monthly_rent_manwon", sa.Integer(), nullable=False),
        sa.Column("maintenance_manwon", sa.Integer(), nullable=False),
        sa.Column("rent_free_months", sa.Integer(), nullable=False),
        sa.Column("min_term_months", sa.Integer(), nullable=True),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("vacant_since", sa.Date(), nullable=True),
        sa.Column("popup_min_days", sa.Integer(), nullable=True),
        sa.Column("popup_max_days", sa.Integer(), nullable=True),
        sa.Column("popup_daily_manwon", sa.Integer(), nullable=True),
        sa.Column("preferred_industries", sa.JSON(), nullable=False),
        sa.Column("excluded_industries", sa.JSON(), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("promoted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_listings_owner_user_id", "direct_listings", ["owner_user_id"])
    op.create_index("ix_direct_listings_district_id", "direct_listings", ["district_id"])

    op.create_table(
        "direct_listing_verifications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("listing_id", sa.String(32), sa.ForeignKey("direct_listings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("submitted_by", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation", sa.String(16), nullable=False),
        sa.Column("registry_number", sa.String(32), nullable=False),
        sa.Column("owner_name", sa.String(100), nullable=False),
        sa.Column("delegation_note", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewer_note", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_listing_verifications_listing_id", "direct_listing_verifications", ["listing_id"])

    op.create_table(
        "direct_inquiries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("listing_id", sa.String(32), sa.ForeignKey("direct_listings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("founder_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("industry_key", sa.String(32), nullable=False),
        sa.Column("visit_slots", sa.JSON(), nullable=False),
        sa.Column("confirmed_slot", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("outcome_by", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_direct_inquiries_listing_id", "direct_inquiries", ["listing_id"])
    op.create_index("ix_direct_inquiries_founder_user_id", "direct_inquiries", ["founder_user_id"])
    op.create_index("ix_direct_inquiries_owner_user_id", "direct_inquiries", ["owner_user_id"])

    op.create_table(
        "direct_messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("inquiry_id", sa.String(32), sa.ForeignKey("direct_inquiries.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("sender_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_direct_messages_inquiry_id", "direct_messages", ["inquiry_id"])

    op.create_table(
        "direct_listing_reports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("listing_id", sa.String(32), sa.ForeignKey("direct_listings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("reporter_user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_direct_listing_reports_listing_id", "direct_listing_reports", ["listing_id"])

    op.create_table(
        "purchase_intents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product", sa.String(40), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("amount_krw", sa.Integer(), nullable=True),
        sa.Column("depositor_name", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_purchase_intents_user_id", "purchase_intents", ["user_id"])


def downgrade() -> None:
    op.drop_table("purchase_intents")
    op.drop_table("direct_listing_reports")
    op.drop_table("direct_messages")
    op.drop_table("direct_inquiries")
    op.drop_table("direct_listing_verifications")
    op.drop_table("direct_listings")
