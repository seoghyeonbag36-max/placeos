/**
 * 창업자 확인 계산 — Page · Posting 보강(2026-11-12 사용자 요청 · 「지금 가능」 N2 · N3 · N4 · N6 · N8).
 *
 * 값을 지어내지 않는다. 판정 근거는 셋뿐이다.
 *  ① 건축물대장 기재값(층 용도 `purps` · 사용승인일 `use_apr`) — 지금 실제 용도 · 상태와 다를 수 있다
 *  ② 법령 수치(건축법 시행령 별표1 · 건축법 §19 · 상가건물 임대차보호법 시행령) — 기준일과 「원문 · 관할 확인」을 함께 보인다
 *  ③ 서버 계산 결과(월매출 · 월비용 · 투자비) — 그 비율을 그대로 쓴다
 * 법률 · 세무 자문이 아니다. 화면은 늘 「관할 구청 · 원문 확인」 문구를 붙인다.
 */
import type { BuildingHistoryRow, TierScenario } from "@/lib/api";

/* ── N2 층 용도로 본 음식점 영업 ─────────────────────────────────────────── */

export type FloorUseGroup = "food" | "neigh" | "other" | "unknown";
export interface FloorUseCheck {
  group: FloorUseGroup;
  /** 짧은 판정 — 배지 글자 */
  badge: string;
  /** 음식점(휴게 · 일반)을 하려면 무엇이 필요한가 */
  food: string;
}

/** 근린생활시설군으로 읽는 층 용도 문자열(건축법 시행령 별표1 제3 · 4호에 드는 이름들 — 대장 기재 문자열 기준 근사) */
const NEIGH_KW = ["근린생활", "소매점", "의원", "학원", "미용", "이(미)용", "이용원", "사진관", "기원", "당구장", "체력단련", "상점",
  "수리점", "탁구장", "안마", "세탁", "독서실", "노래연습", "인터넷컴퓨터", "게임", "볼링", "골프연습", "표구", "금융업소", "부동산중개",
  "출판사", "직업훈련", "교습소", "공연장", "종교집회", "제조업소", "동물병원", "조산원", "산후조리", "의료기기", "테니스", "에어로빅",
  "무도", "장의사", "단란주점", "사무소"];
/** 휴게음식점이 제1종 근린생활시설로 남는 바닥면적 상한(같은 건축물 · 해당 용도 합계) — 건축법 시행령 별표1 제3호나목 */
export const CAFE_1ST_CLASS_MAX_M2 = 300;

export function floorUseCheck(purps: string | null | undefined, areaM2?: number | null): FloorUseCheck {
  const p = (purps ?? "").trim();
  if (!p) return { group: "unknown", badge: "용도 미상", food: "대장에 층 용도가 없어 판단하지 않았어요 — 구청 건축과에서 확인하세요." };
  if (p.includes("일반음식점")) return { group: "food", badge: "음식점 용도", food: "대장 용도가 일반음식점이에요 — 음식점 영업신고 가능성이 높아요." };
  if (p.includes("음식점") || p.includes("제과점")) {
    return { group: "food", badge: "음식점 용도",
      food: `대장 용도가 ${p}이에요 — 카페 · 제과는 바로 가능성이 높고, 일반음식점(술 판매 등)은 제2종 근린생활시설로 대장 기재변경이 필요해요.` };
  }
  if (NEIGH_KW.some((k) => p.includes(k))) {
    const big = areaM2 != null && areaM2 >= CAFE_1ST_CLASS_MAX_M2;
    return { group: "neigh", badge: "기재변경 필요",
      food: `근린생활시설(${p})이라 같은 시설군이에요 — 음식점을 하려면 건축물대장 기재내용 변경을 신청해요(허가 · 신고 아님).`
        + (big ? ` 이 층은 ${Math.round(areaM2!)}㎡라 휴게음식점도 제2종 근린생활시설 기준이에요(300㎡ 이상).` : "") };
  }
  return { group: "other", badge: "허가 · 신고 필요",
    food: `대장 용도가 ${p}이에요 — 근린생활시설이 아니라 음식점으로 쓰려면 용도변경 허가나 신고가 필요해요(시설군 이동).` };
}

/* ── N8 건물 연식 ─────────────────────────────────────────────────────────── */

/** 사용승인일(YYYYMMDD) → 연식(년). 날짜 꼴이 아니면 null */
export function buildingAge(useApr: string | null | undefined, today: Date = new Date()): number | null {
  const m = /^(\d{4})(\d{2})(\d{2})$/.exec(useApr ?? "");
  if (!m) return null;
  const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
  let age = today.getFullYear() - y;
  if (today.getMonth() + 1 < mo || (today.getMonth() + 1 === mo && today.getDate() < d)) age -= 1;
  return age >= 0 ? age : null;
}
export const aprText = (useApr: string) => `${useApr.slice(0, 4)}.${useApr.slice(4, 6)}.${useApr.slice(6, 8)}`;

/* ── N3 상가건물 임대차보호법 — 환산보증금 ────────────────────────────────── */

/** 서울특별시 환산보증금 기준(만원) — 상가건물 임대차보호법 시행령(2019-04 개정 이후). 사이트 범위가 서울이라 서울 값만 쓴다 */
export const SEOUL_LEASE_LIMIT_MANWON = 90000;
export interface LeaseCheck { converted: number; limit: number; within: boolean }
/** 환산보증금 = 보증금 + 월세 × 100(만원). 둘 다 있어야 판정한다 */
export function leaseCheck(depositManwon: number | null | undefined, rentManwon: number | null | undefined): LeaseCheck | null {
  if (depositManwon == null || rentManwon == null || !Number.isFinite(depositManwon) || !Number.isFinite(rentManwon)) return null;
  if (depositManwon < 0 || rentManwon <= 0) return null;
  const converted = Math.round(depositManwon + rentManwon * 100);
  return { converted, limit: SEOUL_LEASE_LIMIT_MANWON, within: converted <= SEOUL_LEASE_LIMIT_MANWON };
}
export const eok = (manwon: number) => {
  const e = Math.floor(manwon / 10000), r = Math.round(manwon % 10000);
  return e ? `${e}억${r ? ` ${r.toLocaleString("ko-KR")}만원` : "원"}` : `${r.toLocaleString("ko-KR")}만원`;
};

/* ── N4 자리 영업 이력 요약 ───────────────────────────────────────────────── */

export interface HistorySummary {
  /** 거쳐 간 업소 수(지번 단위) */
  total: number;
  closed: number;
  /** 2000년 이후 열고 닫은 곳의 영업 기간(년) 중앙값 — 닫은 곳만 센다(생존율이 아니다) */
  medianYears: number | null;
  /** 그중 3년 안에 닫은 곳 */
  within3y: number;
  /** 같은 업종(인허가 업종 문자열에 키워드가 든) 이력 수 */
  sameIndustry: number;
}
const ymd = (s: string | null | undefined) => (/^\d{8}$/.test(s ?? "") ? s! : null);
const years = (a: string, b: string) => (Number(b.slice(0, 4)) - Number(a.slice(0, 4))) + (Number(b.slice(4, 6)) - Number(a.slice(4, 6))) / 12;

export function historySummary(rows: BuildingHistoryRow[], industryKeyword?: string | null): HistorySummary {
  const spans = rows.flatMap((r) => {
    const s = ymd(r.start_date), e = ymd(r.end_date);
    return s && e && s >= "20000101" && e >= s ? [years(s, e)] : [];
  }).sort((a, b) => a - b);
  const mid = spans.length ? (spans.length % 2 ? spans[(spans.length - 1) / 2] : (spans[spans.length / 2 - 1] + spans[spans.length / 2]) / 2) : null;
  const kw = (industryKeyword ?? "").trim();
  return {
    total: rows.length,
    closed: rows.filter((r) => ymd(r.end_date)).length,
    medianYears: mid == null ? null : Math.round(mid * 10) / 10,
    within3y: spans.filter((y) => y <= 3).length,
    sameIndustry: kw ? rows.filter((r) => (r.industry_type ?? "").includes(kw) || (r.business_name ?? "").includes(kw)).length : 0,
  };
}

/* ── N6 민감도 — 매출이 덜 나오거나 월세가 오르면 ─────────────────────────── */

export interface SensitivityRow { label: string; monthNet: number; roiMonths: number | null }
/**
 * 서버 계산의 구조를 그대로 쓴다: 월비용 = 월세 + 매출 × 비임차 비용률 → 비용률 = (월비용 − 월세) ÷ 월매출.
 * 매출이 k 배면 월 순익 = k·매출 − 월세 − 비용률·k·매출. 회수기간 = 투자비(백만원) × 100 ÷ 월 순익.
 */
export function sensitivity(s: TierScenario, rentManwon: number): SensitivityRow[] | null {
  const rev = s.month_rev, cost = s.month_cost, inv = s.invest_mn;
  if (rev == null || cost == null || inv == null || rev <= 0 || !Number.isFinite(rentManwon)) return null;
  const rate = Math.max(0, (cost - rentManwon) / rev);
  const row = (label: string, k: number, rent: number): SensitivityRow => {
    const net = Math.round(k * rev - rent - rate * k * rev);
    return { label, monthNet: net, roiMonths: net > 0 ? Math.round((inv * 100 / net) * 10) / 10 : null };
  };
  return [
    row("지금 계산", 1, rentManwon),
    row("매출 10% 덜", 0.9, rentManwon),
    row("매출 20% 덜", 0.8, rentManwon),
    row("매출 30% 덜", 0.7, rentManwon),
    row("월세 5% 올림", 1, rentManwon * 1.05),
  ];
}
