/**
 * 흐름(화면설계서 5판 · 2026-10-12) — 사용자가 고른 답 한 벌.
 *
 * ## 왜 따로 두나
 * 5판은 「한 화면 한 질문」이라 답이 화면 24개에 흩어진다. 화면끼리 props 로 넘기면 새로고침·
 * 뒤로가기·주소 직접 열기에서 앞 답이 사라진다. 그래서 답은 **고르는 순간 여기에 쓰고**(§2-3),
 * 화면은 여기서 읽는다.
 *
 * ## 저장
 * 이 브라우저의 localStorage 한 키. 로그인 없이 끝까지 가는 흐름이라(C5) 서버에 먼저 쓰지 않는다.
 * 로그인하면 목적·업종·상권만 계정의 「내 사업」(/auth/workspace)으로 옮긴다(FlowApp).
 * 저장이 막혀도(사생활 보호 창) 이번 방문 동안은 메모리 값으로 돈다.
 *
 * ## 답을 바꾸면 그 뒤만 비운다(§2-3)
 * 업종을 바꾸면 상권·자리·비용·검증을, 상권을 바꾸면 자리·비용을 비운다. 앞 답은 남긴다 —
 * `setGoal` · `setIndustry` · `setDistrict` · `setSpace` 가 그 규칙의 유일한 자리다.
 */
import type { BusinessGoal, BusinessState } from "@/lib/businessProfile";
import type { ValidationMode } from "@/lib/api";

/** 권리금 답 — 없음(0, 관측) · 모름(null, 0 전제) · 금액(만원) */
export type PremiumAnswer = { kind: "none" } | { kind: "unknown" } | { kind: "amount"; manwon: number };

/** 예산 점검 입력 — 만원. null = 미확인(모름), 0 = 확인된 무료 */
export interface CostAnswers {
  budget: number | null;
  deposit: number | null;
  rent: number | null;
  maintenance: number | null;
  premium: number | null;
  fitout: number | null;
  equipment: number | null;
  /** 그 밖의 월 고정비(통신·보험·렌탈) — 서버가 이 칸이 비면 총액을 내지 않는다 */
  otherMonthly: number | null;
  reserveMonths: number;
}

/** 검증 예산 구간 — Q13 */
export type TestBudget = "under100" | "100to300" | "300to1000" | "unknown";

export interface FlowState {
  v: 1;
  goal: BusinessGoal | null;
  /** `GET /ai/industries` 의 key. 바꾸기면 **지금** 업종 */
  industryKey: string | null;
  /** 기타 — 직접 적은 업종 */
  customIndustry: string | null;
  /** 바꾸기·옮기기의 지금 가게 상권 */
  homeDistrictId: string | null;
  /** 바꾸기: 바꿔 볼 업종 */
  targetIndustryKey: string | null;
  /** 보는 상권 */
  districtId: string | null;
  /** 월세 상한(만원) — null = 다 보기 */
  rentCap: number | null;
  rentCapAnswered: boolean;
  /** 고른 빈 자리(층) — `vfu-…` */
  spaceId: string | null;
  premium: PremiumAnswer | null;
  /** R5 에서 고른 가격대(premium/value/factory) */
  tier: string | null;
  costs: CostAnswers;
  mode: ValidationMode | null;
  item: string | null;
  runDays: number | null;
  testBudget: TestBudget | null;
  /** 마지막으로 연 흐름 주소 — 홈의 「이어서」 */
  lastPath: string | null;
}

export const FLOW_KEY = "placeos.flow.v1";

export const emptyCosts = (): CostAnswers => ({
  budget: null, deposit: null, rent: null, maintenance: null, premium: null, fitout: null, equipment: null, otherMonthly: null,
  reserveMonths: 3,
});

export const emptyFlow = (): FlowState => ({
  v: 1, goal: null, industryKey: null, customIndustry: null, homeDistrictId: null, targetIndustryKey: null,
  districtId: null, rentCap: null, rentCapAnswered: false, spaceId: null, premium: null, tier: null,
  costs: emptyCosts(), mode: null, item: null, runDays: null, testBudget: null, lastPath: null,
});

let memory: FlowState | null = null;

const isGoal = (v: unknown): v is BusinessGoal => v === "start" || v === "pivot" || v === "move";
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : null);

/** 저장된 값을 읽는다. 모양이 깨진 칸은 버리고 나머지는 살린다 — 한 칸 때문에 전부 잃지 않게. */
export function loadFlow(): FlowState {
  let raw: string | null = null;
  try { raw = window.localStorage.getItem(FLOW_KEY); } catch { return memory ?? emptyFlow(); }
  if (!raw) return memory ?? emptyFlow();
  try {
    const v = JSON.parse(raw);
    const base = emptyFlow();
    const c = v?.costs ?? {};
    const premium = v?.premium;
    return {
      ...base,
      goal: isGoal(v?.goal) ? v.goal : null,
      industryKey: str(v?.industryKey),
      customIndustry: str(v?.customIndustry),
      homeDistrictId: str(v?.homeDistrictId),
      targetIndustryKey: str(v?.targetIndustryKey),
      districtId: str(v?.districtId),
      rentCap: num(v?.rentCap),
      rentCapAnswered: v?.rentCapAnswered === true,
      spaceId: str(v?.spaceId),
      premium: premium?.kind === "none" || premium?.kind === "unknown" ? { kind: premium.kind }
        : premium?.kind === "amount" && num(premium.manwon) != null ? { kind: "amount", manwon: premium.manwon } : null,
      tier: str(v?.tier),
      costs: {
        budget: num(c.budget), deposit: num(c.deposit), rent: num(c.rent), maintenance: num(c.maintenance),
        premium: num(c.premium), fitout: num(c.fitout), equipment: num(c.equipment), otherMonthly: num(c.otherMonthly),
        reserveMonths: num(c.reserveMonths) ?? 3,
      },
      mode: ["popup", "soft_open", "mvp", "actual_open"].includes(v?.mode) ? v.mode : null,
      item: str(v?.item),
      runDays: num(v?.runDays),
      testBudget: ["under100", "100to300", "300to1000", "unknown"].includes(v?.testBudget) ? v.testBudget : null,
      lastPath: str(v?.lastPath),
    };
  } catch {
    return emptyFlow();
  }
}

export function saveFlow(state: FlowState): void {
  memory = state;
  try { window.localStorage.setItem(FLOW_KEY, JSON.stringify(state)); } catch { /* 메모리 값으로 돈다 */ }
}

export function clearFlow(): void {
  memory = null;
  try { window.localStorage.removeItem(FLOW_KEY); } catch { /* 지울 것이 없다 */ }
}

/* ── 답 바꾸기 — 그 뒤만 비운다(§2-3) ─────────────────────────────────────── */

const clearSpaceOn = (s: FlowState): FlowState => ({
  ...s, spaceId: null, premium: null, tier: null, costs: { ...emptyCosts(), budget: s.costs.budget },
});
const clearDistrictOn = (s: FlowState): FlowState => ({ ...clearSpaceOn(s), districtId: null, rentCap: null, rentCapAnswered: false });
const clearValidateOn = (s: FlowState): FlowState => ({ ...s, mode: null, item: null, runDays: null, testBudget: null });

export function setGoal(s: FlowState, goal: BusinessGoal): FlowState {
  if (s.goal === goal) return s;
  return clearValidateOn(clearDistrictOn({ ...s, goal, industryKey: null, customIndustry: null, homeDistrictId: null, targetIndustryKey: null }));
}

export function setIndustry(s: FlowState, industryKey: string, customIndustry: string | null = null): FlowState {
  if (s.industryKey === industryKey && s.customIndustry === customIndustry) return s;
  const keepHome = s.goal !== "start";
  return clearValidateOn(clearDistrictOn({ ...s, industryKey, customIndustry, targetIndustryKey: null,
    homeDistrictId: keepHome ? s.homeDistrictId : null }));
}

export function setHomeDistrict(s: FlowState, id: string): FlowState {
  if (s.homeDistrictId === id) return s;
  // 옮기기·바꾸기는 지금 상권이 순위의 기준이다 — 보는 상권 뒤를 비운다
  return clearDistrictOn({ ...s, homeDistrictId: id });
}

export function setDistrict(s: FlowState, id: string): FlowState {
  if (s.districtId === id) return s;
  return { ...clearDistrictOn(s), districtId: id };
}

export function setSpace(s: FlowState, spaceId: string): FlowState {
  if (s.spaceId === spaceId) return s;
  return { ...clearSpaceOn(s), spaceId };
}

/** 검증 계획이 쓸 업종 — 바꾸기는 바꿀 업종, 그 밖은 할 업종(lib/businessProfile.workIndustryKey 와 같은 규칙) */
export const workKey = (s: FlowState): string | null => (s.goal === "pivot" ? s.targetIndustryKey : s.industryKey);

/** 검증 예산 구간 → 브리프의 한 쌍(원). 서버는 반쪽만 오면 422 다 */
export const TEST_BUDGET_RANGE: Record<TestBudget, [number, number] | null> = {
  under100: [100_000, 1_000_000],
  "100to300": [1_000_000, 3_000_000],
  "300to1000": [3_000_000, 10_000_000],
  unknown: null,
};

/** 흐름 답 → 계정의 「내 사업」. 목적·업종이 없으면 옮길 것이 없다 */
export function flowToBusiness(s: FlowState): BusinessState {
  if (!s.goal || !s.industryKey) return { status: "unset" };
  if (s.goal !== "start" && !s.homeDistrictId) return { status: "unset" };
  return {
    status: "set",
    profile: {
      goal: s.goal, industryKey: s.industryKey,
      homeDistrictId: s.goal === "start" ? null : s.homeDistrictId,
      ...(s.goal === "pivot" ? { targetIndustryKey: s.targetIndustryKey } : {}),
      ...(s.industryKey === "other" && s.customIndustry ? { customIndustry: s.customIndustry } : {}),
    },
  };
}

/** 계정의 「내 사업」 → 흐름(흐름이 비어 있을 때만 쓴다 — 로그인한 사람이 다른 기기에서 이어 갈 때) */
export function businessToFlow(b: BusinessState, base: FlowState = emptyFlow()): FlowState {
  if (b.status !== "set") return base;
  const p = b.profile;
  return {
    ...base, goal: p.goal, industryKey: p.industryKey, customIndustry: p.customIndustry ?? null,
    homeDistrictId: p.homeDistrictId, targetIndustryKey: p.targetIndustryKey ?? null,
    districtId: p.goal === "start" ? null : p.homeDistrictId,
  };
}
