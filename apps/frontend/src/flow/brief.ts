/**
 * 입점 희망서 화면들이 함께 쓰는 순수 함수(2026-11-21 · docs/decision-founder-brief-2026-11-21.md).
 * 필수 칸 규칙은 서버(services/direct_briefs.missing_required)와 같다 — 화면 검사는 안내용이고 서버가 최종 판정이다.
 * ⛔ 신용 점수·등급을 만들지 않는다 — 이 파일에도 점수 계산이 없다.
 */
import type { DirectBriefInput, DirectBriefSelf, DirectFitStatus, DirectFloorBand, DirectBusinessStage } from "@/lib/api";
import type { FlowState } from "./state";

export interface BriefDraft {
  industry_key: string; area_min: string; area_max: string; floor_bands: DirectFloorBand[];
  needs_exhaust: boolean; needs_water: boolean; power_kw_min: string; rent_cap: string; deposit_cap: string;
  /** `YYYY-MM` — 달 단위로 묻고 서버에는 그달 1일로 보낸다 */
  desired_month: string; district_ids: string[]; popup_first: boolean; accept_invites: boolean;
  summary: string; business_stage: DirectBusinessStage | ""; funding_total: string; funding_own: string;
  unit_price: string; variable_cost_pct: string; other_fixed: string; open_days: string; target_daily: string;
}

export const emptyBriefDraft = (): BriefDraft => ({
  industry_key: "", area_min: "", area_max: "", floor_bands: [], needs_exhaust: false, needs_water: false, power_kw_min: "",
  rent_cap: "", deposit_cap: "", desired_month: "", district_ids: [], popup_first: false, accept_invites: true,
  summary: "", business_stage: "", funding_total: "", funding_own: "",
  unit_price: "", variable_cost_pct: "", other_fixed: "", open_days: "", target_daily: "",
});

const s = (v: number | null | undefined) => (v == null ? "" : String(v));

/** 흐름에서 이미 답한 것(업종·상권·월세 상한·예산)으로 첫 초안을 채운다 — 창업자가 다시 적지 않게 */
export function draftFromFlow(state: FlowState): BriefDraft {
  const d = emptyBriefDraft();
  const industry = state.goal === "pivot" ? state.targetIndustryKey : state.industryKey;
  if (industry && industry !== "other") d.industry_key = industry;
  const districts = [state.districtId, state.goal === "move" ? state.homeDistrictId : null].filter((x): x is string => !!x);
  d.district_ids = Array.from(new Set(districts)).slice(0, 3);
  if (state.rentCap != null) d.rent_cap = String(state.rentCap);
  if (state.costs.deposit != null) d.deposit_cap = String(state.costs.deposit);
  return d;
}

export function draftFromServer(b: DirectBriefSelf): BriefDraft {
  return {
    industry_key: b.industry_key, area_min: s(b.area_min_m2), area_max: s(b.area_max_m2), floor_bands: b.floor_bands,
    needs_exhaust: b.needs_exhaust, needs_water: b.needs_water, power_kw_min: s(b.power_kw_min), rent_cap: s(b.rent_cap_manwon),
    deposit_cap: s(b.deposit_cap_manwon), desired_month: b.desired_start ?? "", district_ids: b.districts.map((x) => x.id),
    popup_first: b.popup_first, accept_invites: b.accept_invites, summary: b.summary, business_stage: b.business_stage,
    funding_total: s(b.funding_total_manwon), funding_own: s(b.funding_own_manwon), unit_price: s(b.private.unit_price_won),
    variable_cost_pct: s(b.private.variable_cost_pct), other_fixed: s(b.private.other_fixed_manwon), open_days: s(b.private.open_days),
    target_daily: s(b.private.target_daily_units),
  };
}

const int = (v: string): number | null => {
  const n = Number(String(v).replace(/[^\d]/g, ""));
  return v.trim() && Number.isFinite(n) ? Math.trunc(n) : null;
};
const num = (v: string): number | null => {
  const n = Number(String(v).replace(/[^\d.]/g, ""));
  return v.trim() && Number.isFinite(n) ? n : null;
};

/** 빈 필수 칸의 키 — 서버 REQUIRED_LABELS 의 키와 같다 */
export function briefMissing(d: BriefDraft): string[] {
  const miss: string[] = [];
  const lo = num(d.area_min);
  const hi = num(d.area_max);
  if (!d.industry_key) miss.push("industry_key");
  if (!(lo && hi)) miss.push("area");
  if (d.floor_bands.length === 0) miss.push("floor_bands");
  if (!int(d.rent_cap)) miss.push("rent_cap");
  if (int(d.deposit_cap) == null) miss.push("deposit_cap");
  if (!/^\d{4}-\d{2}$/.test(d.desired_month)) miss.push("desired_month");
  if (d.district_ids.length === 0) miss.push("district_ids");
  return miss;
}

/** 서버 키(desired_start)와 화면 키(desired_month)가 다른 칸 하나를 맞춘다 */
export const serverMissingKey = (k: string) => (k === "desired_month" ? "desired_start" : k);

/** 최소 > 최대 같은 앞뒤 어긋남 — 서버도 422 로 막는다 */
export function briefPairProblems(d: BriefDraft): string[] {
  const out: string[] = [];
  const lo = num(d.area_min);
  const hi = num(d.area_max);
  if (lo != null && hi != null && lo > hi) out.push("필요 면적은 작은 값부터 적어 주세요(최소 ≤ 최대).");
  const total = int(d.funding_total);
  const own = int(d.funding_own);
  if (total != null && own != null && own > total) out.push("자기 자금이 총 창업 자금보다 클 수 없어요.");
  return out;
}

export const briefToInput = (d: BriefDraft): DirectBriefInput => ({
  industry_key: d.industry_key || null, area_min_m2: num(d.area_min), area_max_m2: num(d.area_max), floor_bands: d.floor_bands,
  needs_exhaust: d.needs_exhaust, needs_water: d.needs_water, power_kw_min: int(d.power_kw_min), rent_cap_manwon: int(d.rent_cap),
  deposit_cap_manwon: int(d.deposit_cap), desired_start: /^\d{4}-\d{2}$/.test(d.desired_month) ? `${d.desired_month}-01` : null,
  district_ids: d.district_ids.slice(0, 3), popup_first: d.popup_first, accept_invites: d.accept_invites,
  summary: d.summary.trim(), business_stage: d.business_stage, funding_total_manwon: int(d.funding_total),
  funding_own_manwon: int(d.funding_own), unit_price_won: int(d.unit_price), variable_cost_pct: num(d.variable_cost_pct),
  other_fixed_manwon: int(d.other_fixed), open_days: int(d.open_days), target_daily_units: int(d.target_daily),
});

/** 조건표 칸의 이름표 — 점수가 아니라 상태 */
export const FIT_LABEL: Record<DirectFitStatus, string> = { ok: "맞아요", gap: "차이 있어요", unknown: "모름", info: "참고" };

export const manwon = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("ko-KR")}만원`);
export const areaRange = (lo: number | null, hi: number | null) =>
  lo == null || hi == null ? "—" : `${lo.toLocaleString("ko-KR")}~${hi.toLocaleString("ko-KR")}㎡`;
