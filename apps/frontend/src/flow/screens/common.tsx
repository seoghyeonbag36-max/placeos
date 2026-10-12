/** 흐름 화면들이 함께 쓰는 작은 도우미 — 업종 이름 · 캡션 · 앞 답 확인 */
import { useEffect } from "react";
import type { BusinessGoal } from "@/lib/businessProfile";
import type { DistrictSummary, IndustryOption } from "@/lib/api";
import { useFlow } from "../context";
import { useFlowData, useLoad } from "../data";
import { replace } from "../route";
import type { FlowState } from "../state";

export const GOAL_LABEL: Record<BusinessGoal, string> = { start: "새 가게", pivot: "업종 바꾸기", move: "상권 옮기기" };

/** 업종 타일의 그림 — 장식이다(이름이 읽힌다). 모르는 key 는 가게 그림 */
export const INDUSTRY_EMOJI: Record<string, string> = {
  cafe: "☕", restaurant: "🍚", bar: "🍺", beauty: "💇", clinic: "🏥", pharmacy: "💊", convenience: "🏪",
  fashion: "👕", education: "📚", fitness: "🏋️", lodging: "🛏️", culture: "🎨", other: "✏️",
};

/** 상권 순위를 낼 수 있는 업종인가 — 모델 라벨이 있고 서빙 어휘 안(사유 없음) */
export const hasRanking = (o: IndustryOption | null | undefined) => !!o && !!o.model_label && !o.fit_unavailable_reason;

export function useIndustries() {
  const data = useFlowData();
  return useLoad("industries", data.industries);
}

export function useDistricts() {
  const data = useFlowData();
  return useLoad("districts", data.districts);
}

/** key → 업종. 기타면 직접 적은 이름으로 가짜 항목을 만든다(순위·본전 계산 없음) */
export function industryOf(key: string | null, custom: string | null, list: IndustryOption[] | null): IndustryOption | null {
  if (!key) return null;
  if (key === "other") return custom ? { key: "other", label: custom, input: custom, model_label: null, fit_unavailable_reason: "직접 적은 업종" } : null;
  return list?.find((i) => i.key === key) ?? null;
}

/** 지금 보는 업종 — 바꾸기면 바꿀 업종, 아니면 할 업종 */
export function useWorkIndustry(): IndustryOption | null {
  const { state } = useFlow();
  const list = useIndustries();
  const key = state.goal === "pivot" ? state.targetIndustryKey : state.industryKey;
  const custom = state.goal === "pivot" ? null : state.customIndustry;
  return industryOf(key, custom, list.status === "ready" ? list.data : null);
}

/** 상권 이름 — 목록이 아직 없으면 null */
export function useDistrictName(id: string | null): string | null {
  const ds = useDistricts();
  if (!id || ds.status !== "ready") return null;
  return ds.data.find((d) => d.id === id)?.name ?? null;
}

export const districtById = (list: DistrictSummary[], id: string | null) => (id ? list.find((d) => d.id === id) ?? null : null);

/**
 * 필요한 앞 답이 없으면 그 질문으로 돌려보낸다(§2-3) — 주소로 바로 열었거나 앞 답을 바꿔 뒤가 비었을 때.
 * `ok` 가 false 면 `to` 로 바꿔치기하고, 화면은 아무것도 그리지 않는다(호출부가 `if (!ok) return null`).
 */
export function useNeed(ok: boolean, to: string): boolean {
  useEffect(() => { if (!ok) replace(to); }, [ok, to]);
  return ok;
}

/** 흐름 첫 질문까지 무엇이 비었나 — 순서대로 첫 빈 곳 */
export function firstMissing(s: FlowState): string | null {
  if (!s.goal) return "/start";
  if (!s.industryKey) return "/industry";
  if (s.goal !== "start" && !s.homeDistrictId) return "/home-district";
  return null;
}

/** 검색칸이 거르는 규칙 — 이름·구 부분 일치, 공백 무시 */
export const matches = (d: DistrictSummary, q: string) => {
  const k = q.replace(/\s+/g, "");
  return !k || d.name.replace(/\s+/g, "").includes(k) || d.gu.includes(k);
};
