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
