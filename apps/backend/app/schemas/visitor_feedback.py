"""방문자 의견 입력과 관리자 응답 계약."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VisitorRole = Literal["start", "owner", "dev", "design", "other"]

# 의견 창의 입장·질문·선택지(2026-10-25). 화면 쪽 원본은 apps/frontend/src/components/visitorFeedbackForm.json 이고,
# 여기는 같은 키·라벨의 사본이다 — 검증과 알림 메일이 쓴다. 어긋나면 tests/test_visitor_feedback.py 의 대조 테스트가 운다.
# 입장은 방문자가 스스로 고른 값이라 확인되지 않는다. 창업자·파일럿 수로 옮겨 적지 않는다.
# ⚠ key 는 바꾸거나 지우지 말고 더하기만 한다 — 모르는 키는 422 라, 배포 직후 열려 있던 옛 탭의 제출이 통째로 실패한다.
CATEGORY_LABELS: dict[str, str] = {"review": "후기", "bug": "오류 제보", "suggestion": "개선 요청"}
_FOUND = {"label": "오늘 찾던 답을 얻었나요?", "options": {"yes": "얻었어요", "partly": "일부만", "no": "못 얻었어요"}}
VISITOR_ROLES: dict[str, dict] = {
    "start": {"label": "창업 준비 중", "questions": {
        "stage": {"label": "지금 어느 단계예요?", "options": {
            "industry_set": "업종만 정했어요", "comparing_areas": "동네 후보를 봐요",
            "touring_listings": "매물 보러 다녀요", "about_to_sign": "계약 직전이에요"}},
        "found": _FOUND}},
    "owner": {"label": "가게 운영 중", "questions": {
        "plan": {"label": "무엇을 고민 중이세요?", "options": {
            "change_industry": "업종 변경", "relocate": "다른 동네로 이전", "undecided": "아직 못 정했어요"}},
        "found": _FOUND}},
    "dev": {"label": "개발자", "questions": {
        "issue": {"label": "무엇이 문제였나요?", "options": {
            "slow": "느려요", "error": "오류·멈춤", "map": "지도·거리뷰", "data": "숫자가 이상해요", "other": "기타"}}}},
    "design": {"label": "디자이너", "questions": {
        "first_screen": {"label": "첫 화면에서 할 일을 바로 알았나요?", "options": {
            "clear": "바로 알았어요", "hesitated": "잠깐 헤맸어요", "unclear": "몰랐어요"}},
        "blocker": {"label": "가장 걸린 것은?", "options": {
            "wording": "어려운 단어", "too_much": "정보가 많음", "next_button": "다음 버튼", "mobile": "모바일", "other": "기타"}}}},
    "other": {"label": "기타", "questions": {}},
}


def answer_lines(role: str | None, answers: dict[str, str] | None) -> list[str]:
    """저장된 선택 응답을 「질문: 답」 줄로 푼다(알림 메일용). 모르는 키는 그대로 둔다."""
    questions = VISITOR_ROLES.get(role or "", {}).get("questions", {})
    lines = []
    for key, value in (answers or {}).items():
        q = questions.get(key, {})
        lines.append(f"{q.get('label', key)} {q.get('options', {}).get(value, value)}")
    return lines


class VisitorFeedbackIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    # role 은 2026-10-25 이전 화면(열려 있던 탭의 옛 번들)이 보내지 않으므로 비워 둘 수 있다.
    role: VisitorRole | None = None
    category: Literal["review", "bug", "suggestion"]
    message: str = Field(min_length=1, max_length=2000)
    page: str = Field(min_length=1, max_length=500, pattern=r"^/[^?]*$")
    answers: dict[str, str] | None = None
    contact: str | None = Field(default=None, min_length=1, max_length=320)

    @field_validator("answers")
    @classmethod
    def _empty_answers_are_none(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        return value or None

    @model_validator(mode="after")
    def _answers_belong_to_role(self) -> "VisitorFeedbackIn":
        """선택 응답은 그 입장의 질문·선택지 안에서만 받는다 — 자유 서술이 이 칸으로 새지 않게."""
        if self.answers is None:
            return self
        if self.role is None:
            raise ValueError("선택 응답은 입장과 함께 보낸다")
        questions = VISITOR_ROLES[self.role]["questions"]
        for key, value in self.answers.items():
            if value not in questions.get(key, {}).get("options", {}):
                raise ValueError(f"고를 수 없는 응답: {key}={value}")
        return self


class VisitorFeedbackSaved(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime

class VisitorFeedbackOut(VisitorFeedbackSaved):
    role: str | None
    category: str
    message: str
    answers: dict[str, str] | None
    page: str
    contact: str | None
    status: str
    notification_status: str

class VisitorFeedbackStatus(BaseModel):
    status: Literal["received", "reviewing", "completed"]
