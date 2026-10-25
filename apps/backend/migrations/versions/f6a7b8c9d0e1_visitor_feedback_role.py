"""방문자 의견에 입장(role)과 선택형 응답(answers) 칸 — 2026-10-25.

둘 다 비워 둘 수 있는 칸을 더하기만 한다. 그래서 이 리비전을 먼저 적용해도 옛 코드는 그대로 돈다.
⚠ 순서: 프로덕션(Neon)에 이 리비전을 **배포보다 먼저** 적용한다. 새 코드가 먼저 나가면 없는 칸에 쓰려다
   의견 저장이 전부 실패한다(배포는 자동, 마이그레이션은 수동 — docs/deploy-cloud-run.md).
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("visitor_feedback", sa.Column("role", sa.String(20), nullable=True))
    op.add_column("visitor_feedback", sa.Column("answers", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("visitor_feedback") as batch:
        batch.drop_column("answers")
        batch.drop_column("role")
