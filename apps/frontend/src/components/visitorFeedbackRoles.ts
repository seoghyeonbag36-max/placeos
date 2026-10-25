import type { VisitorFeedbackCategory, VisitorFeedbackRole } from "@/lib/api";
import form from "./visitorFeedbackForm.json";

/** 의견 창의 입장·질문·선택지(2026-10-25). 원본은 visitorFeedbackForm.json 하나이고,
 *  서버는 같은 키·라벨을 app/schemas/visitor_feedback.py 에 두고 검증한다.
 *  어긋나면 apps/backend/tests/test_visitor_feedback.py 의 대조 테스트가 운다.
 *  ⚠ 입장·질문·선택지의 key 는 바꾸거나 지우지 말고 더하기만 한다 — 서버가 모르는 키를 422 로 막아서,
 *    배포 직후 열려 있던 옛 탭의 제출이 통째로 실패한다. 라벨(label·title·hint)은 바꿔도 된다. */
export interface FeedbackOption { key: string; label: string }
export interface FeedbackQuestion { key: string; label: string; options: FeedbackOption[] }
export interface FeedbackRole { key: VisitorFeedbackRole; label: string; sub: string; title: string; hint: string; questions: FeedbackQuestion[] }

export const FEEDBACK_CATEGORIES = form.categories as { key: VisitorFeedbackCategory; label: string }[];
export const FEEDBACK_ROLES = form.roles as FeedbackRole[];

export const roleOf = (key: string | null | undefined) => FEEDBACK_ROLES.find(r => r.key === key);
export const categoryLabel = (key: string) => FEEDBACK_CATEGORIES.find(c => c.key === key)?.label ?? key;

/** 저장된 선택 응답을 「질문 답」 문장들로 푼다. 모르는 키는 그대로 보여 준다. */
export function answerLines(role: string | null, answers: Record<string, string> | null): string[] {
  const questions = roleOf(role)?.questions ?? [];
  return Object.entries(answers ?? {}).map(([key, value]) => {
    const q = questions.find(item => item.key === key);
    return `${q?.label ?? key} ${q?.options.find(o => o.key === value)?.label ?? value}`;
  });
}
