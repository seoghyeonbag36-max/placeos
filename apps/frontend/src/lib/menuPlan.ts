/**
 * Posting 「메뉴 설정」(2026-11-10 사용자 요청) — 대표 메뉴의 판매가 · 원가 · 판매 비중으로 평균 객단가와 원가율을 내고,
 * 하루 몇 개를 팔아야 본전인지 계산한다. 기본값을 만들지 않는다(입력이 다 차야 계산 — `areaBep` 과 같은 원칙).
 * 손익분기 식은 `areaBep.calculateAreaBep` 와 같다: BEP 월매출 = (임대료 + 기타 고정비) ÷ (1 − 원가율).
 */
export interface MenuRow { name: string; price: string; cost: string; share: string }
export const emptyMenuRow = (): MenuRow => ({ name: "", price: "", cost: "", share: "" });

const num = (s: string) => (s.trim() === "" ? NaN : Number(s));

/** 판매가 > 0 · 0 ≤ 원가 < 판매가 인 줄만 쓴다. 비중은 쓸 줄 **모두**에 0보다 큰 값이 있을 때만 가중한다(아니면 단순 평균). */
export function menuMix(rows: MenuRow[]): { n: number; avgPrice: number; avgCost: number; costRate: number; weighted: boolean } | null {
  const used = rows.map((r) => ({ price: num(r.price), cost: num(r.cost), share: num(r.share) }))
    .filter((r) => Number.isFinite(r.price) && Number.isFinite(r.cost) && r.price > 0 && r.cost >= 0 && r.cost < r.price);
  if (!used.length) return null;
  const weighted = used.every((r) => Number.isFinite(r.share) && r.share > 0);
  const w = used.map((r) => (weighted ? r.share : 1)), total = w.reduce((a, b) => a + b, 0);
  const avgPrice = used.reduce((t, r, i) => t + r.price * w[i], 0) / total;
  const avgCost = used.reduce((t, r, i) => t + r.cost * w[i], 0) / total;
  return { n: used.length, avgPrice, avgCost, costRate: avgCost / avgPrice, weighted };
}

/** 하루 손익분기 판매 개수. rent · otherFixed 는 만원, avgPrice 는 원. 범위를 벗어나면 null */
export function menuBep(i: { rent: number; otherFixed: number; avgPrice: number; costRate: number; days: number }) {
  if (![i.rent, i.otherFixed, i.avgPrice, i.costRate, i.days].every(Number.isFinite)
    || i.rent < 0 || i.otherFixed < 0 || i.avgPrice <= 0 || i.costRate < 0 || i.costRate >= 1
    || !Number.isInteger(i.days) || i.days < 1 || i.days > 31) return null;
  const breakEvenRevenue = (i.rent + i.otherFixed) / (1 - i.costRate);
  // 나눗셈 오차(80.0000001 → 81)로 하루 한 개가 더 붙지 않게 아주 작은 여유를 두고 올린다
  return { breakEvenRevenue, dailySales: Math.ceil((breakEvenRevenue * 10000) / i.avgPrice / i.days - 1e-9) };
}

/** 추정 월매출(만원)을 이 객단가로 나눈 하루 판매 개수 — 상권 평균 매출 기준이지 내 메뉴의 수요가 아니다 */
export const dailyFromRevenue = (monthRevManwon: number, avgPrice: number, days: number) =>
  Math.round((monthRevManwon * 10000) / avgPrice / days);

/* ── 인건비 도우미(2026-11-12 사용자 요청 · N7) ─────────────────────────────── */

/** 2026년 최저임금 시간급(원) — 고용노동부 고시 제2025-47호(2026-01-01 ~ 12-31). 해마다 바꾼다 */
export const MIN_WAGE_2026 = 10320;
/** 한 달 평균 주 수 — 365 ÷ 7 ÷ 12. 주 40시간 + 주휴 8시간이면 월 209시간이 된다(고시의 월 환산 기준) */
const WEEKS_PER_MONTH = 365 / 7 / 12;

/**
 * 월 인건비(만원). 주 15시간 이상이면 주휴시간(주 근무시간 ÷ 40 × 8, 최대 8)을 더해 유급시간을 센다.
 * 4대보험 사업주 부담분 · 퇴직금 · 연장 · 야간 가산은 넣지 않는다(화면이 그렇다고 밝힌다).
 */
export function laborMonthly(i: { people: number; weeklyHours: number; wage: number }): { manwon: number; paidHoursPerPerson: number } | null {
  if (![i.people, i.weeklyHours, i.wage].every(Number.isFinite) || i.people <= 0 || i.weeklyHours <= 0 || i.weeklyHours > 52 || i.wage <= 0) return null;
  const holiday = i.weeklyHours >= 15 ? Math.min(i.weeklyHours, 40) / 40 * 8 : 0;
  // 월 유급시간은 정수 시간으로 반올림한다 — 고시의 월 환산(주 40시간 → 209시간)과 같은 방식
  const paid = Math.round((i.weeklyHours + holiday) * WEEKS_PER_MONTH);
  return { manwon: Math.round(i.people * i.wage * paid / 10000), paidHoursPerPerson: paid };
}
