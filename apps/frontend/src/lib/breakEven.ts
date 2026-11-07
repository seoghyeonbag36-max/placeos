import type { IndustryEconomics } from "@/lib/api";

/** 가설 검증 목표선(2026-11-07 리뉴얼) — Posting 세부 업종 계산에서 하루 손익분기 건수를 끌어낸다.
 *
 *  목표선을 지어내지 않는다: 예전 규칙 스텁의 「일 60명」·「전환율 8%」는 그 자리의 본전과 무관했다.
 *  여기서는 창업자가 넣은 단가·영업일·비용으로 서버(services/industry_detail)가 낸 월 손익분기 매출을
 *  하루 건수로 나눌 뿐이다. 단위는 모두 만원이다(단가·임대료·고정비 → 손익분기 매출).
 *
 *  하루 건수로 바꿀 수 있는 업종 군만 계산한다:
 *    판매(transactions 칸)          월 손익분기 ÷ (객단가 × 영업일 × (1 − 반품률))  → 하루 구매
 *    좌석·예약(cycles 칸)           월 손익분기 ÷ (단가 × 영업일)                  → 하루 유료 이용
 *    객실(capacity·days, cycles 없음) 월 손익분기 ÷ (1박 단가 × 판매일)             → 하루 판매 객실
 *  월 단위 이용료(수강·회원)·회차(티켓)·대관·수수료 업종은 하루 건수가 뜻이 없어 null 이다. */
export interface BreakEvenDaily { count: number; unit: string; basis: string }

const fmt = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });

export function breakEvenDaily(economics?: IndustryEconomics | null): BreakEvenDaily | null {
  if (!economics || economics.status !== "calculated" || economics.break_even_revenue == null) return null;
  const a = economics.assumptions ?? {};
  const bev = economics.break_even_revenue;
  const price = a.price;
  const days = a.days;
  if (!(bev > 0) || !(price > 0) || !(days > 0)) return null;
  let denom: number;
  let unit: string;
  let basis: string;
  if ("transactions" in a) {
    const keep = 1 - (a.return_rate ?? 0);
    if (!(keep > 0)) return null;
    denom = price * days * keep;
    unit = "구매";
    basis = `월 손익분기 ${fmt(bev)}만원 ÷ (객단가 ${fmt(price)}만원 × 영업일 ${fmt(days)}일 × (1 − 반품률 ${fmt(a.return_rate ?? 0)}))`;
  } else if ("cycles" in a) {
    denom = price * days;
    unit = "유료 이용";
    basis = `월 손익분기 ${fmt(bev)}만원 ÷ (단가 ${fmt(price)}만원 × 영업일 ${fmt(days)}일)`;
  } else if ("capacity" in a && !("cycles" in a)) {
    denom = price * days;
    unit = "판매 객실";
    basis = `월 손익분기 ${fmt(bev)}만원 ÷ (1박 단가 ${fmt(price)}만원 × 판매일 ${fmt(days)}일)`;
  } else {
    return null;
  }
  const count = Math.ceil(bev / denom);
  return Number.isFinite(count) && count > 0 ? { count, unit, basis } : null;
}
