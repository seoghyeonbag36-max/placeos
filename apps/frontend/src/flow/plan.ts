/** 검증 방식 이름 · 만든 검증 계획 보관(탭 저장소 — 새로고침해도 AI 를 다시 부르지 않게) */
import type { ProgramBriefInput, ProgramPlan, ValidationMode } from "@/lib/api";

export const MODES: { value: ValidationMode; title: string; desc: string }[] = [
  { value: "popup", title: "팝업스토어", desc: "며칠~몇 주 빈 자리를 빌려 팔아 봐요" },
  { value: "soft_open", title: "가오픈", desc: "작게 열고 손님 반응을 봐요" },
  { value: "mvp", title: "사전 예약", desc: "가게 없이 예약·주문부터 받아 봐요" },
  { value: "actual_open", title: "바로 창업", desc: "정식으로 열고 기록하며 확인해요" },
];
export const modeTitle = (m: string | null | undefined) => MODES.find((x) => x.value === m)?.title ?? "검증";

const PLAN_KEY = "placeos.flow.plan.v1";
interface PlanCache { brief: ProgramBriefInput; plan: ProgramPlan; at: string }
export function loadPlan(): PlanCache | null {
  try { const raw = window.sessionStorage.getItem(PLAN_KEY); return raw ? JSON.parse(raw) as PlanCache : null; } catch { return null; }
}
export function storePlan(p: PlanCache) {
  try { window.sessionStorage.setItem(PLAN_KEY, JSON.stringify(p)); } catch { /* 이번 화면에서만 보인다 */ }
}
export function clearPlan() {
  try { window.sessionStorage.removeItem(PLAN_KEY); } catch { /* 지울 것이 없다 */ }
}
