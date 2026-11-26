/**
 * Posting 「메뉴 설정」(2026-11-10 사용자 요청) — 대표 메뉴의 판매가 · 원가 · 판매 비중으로 평균 객단가와 원가율을 내고,
 * 하루 몇 개를 팔아야 본전인지 계산한다. 기본값을 만들지 않는다(입력이 다 차야 계산 — `areaBep` 과 같은 원칙).
 * 손익분기 식은 `areaBep.calculateAreaBep` 와 같다: BEP 월매출 = (임대료 + 기타 고정비) ÷ (1 − 원가율).
 *
 * 2026-11-26 사용자 요청 — 재료값(메뉴 1개 원가를 재료로 계산) · 장비값(월 감가상각으로 고정비에 더함) · 하루 영업 시간 ·
 * 가맹점 로열티(매출의 %)를 더했다: BEP 월매출 = (임대료 + 고정비 + 장비 감가상각) ÷ (1 − 원가율 − 로열티율).
 * 업종 평균은 `GET /ai/menu-benchmarks` 가 출처와 함께 주고, 화면은 누를 때만 빈칸에 넣는다(여기서 값을 만들지 않는다).
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

/** 하루 손익분기 판매 개수. rent · otherFixed 는 만원, avgPrice 는 원, royaltyRate 는 매출 대비 비율(가맹점 로열티 · 없으면 0).
 *  범위를 벗어나면(원가율 + 로열티율 ≥ 1 포함) null */
export function menuBep(i: { rent: number; otherFixed: number; avgPrice: number; costRate: number; days: number; royaltyRate?: number }) {
  const royalty = i.royaltyRate ?? 0;
  if (![i.rent, i.otherFixed, i.avgPrice, i.costRate, i.days, royalty].every(Number.isFinite)
    || i.rent < 0 || i.otherFixed < 0 || i.avgPrice <= 0 || i.costRate < 0 || royalty < 0 || i.costRate + royalty >= 1
    || !Number.isInteger(i.days) || i.days < 1 || i.days > 31) return null;
  const breakEvenRevenue = (i.rent + i.otherFixed) / (1 - i.costRate - royalty);
  // 나눗셈 오차(80.0000001 → 81)로 하루 한 개가 더 붙지 않게 아주 작은 여유를 두고 올린다
  return { breakEvenRevenue, dailySales: Math.ceil((breakEvenRevenue * 10000) / i.avgPrice / i.days - 1e-9) };
}

/** 추정 월매출(만원)을 이 객단가로 나눈 하루 판매 개수 — 상권 평균 매출 기준이지 내 메뉴의 수요가 아니다 */
export const dailyFromRevenue = (monthRevManwon: number, avgPrice: number, days: number) =>
  Math.round((monthRevManwon * 10000) / avgPrice / days);

/* ── 재료값 — 메뉴 1개 원가를 재료로 계산(2026-11-26) ───────────────────────── */

/** 재료 한 줄 — 산 값(원) · 산 양 · 메뉴 1개에 쓰는 양(산 양과 같은 단위: g · ml · 개) */
export interface IngredientRow { name: string; price: string; pack: string; use: string }
export const emptyIngredient = (): IngredientRow => ({ name: "", price: "", pack: "", use: "" });

/** 메뉴 1개에 드는 이 재료 값(원) = 산 값 × 쓰는 양 ÷ 산 양. 하나라도 비었거나 산 양이 0 이하면 null */
export function ingredientCost(r: IngredientRow): number | null {
  const price = num(r.price), pack = num(r.pack), use = num(r.use);
  if (![price, pack, use].every(Number.isFinite) || price < 0 || pack <= 0 || use < 0) return null;
  return (price * use) / pack;
}

/** 계산되는 재료만 더한 메뉴 1개 재료값(원). 계산되는 줄이 없으면 null */
export function ingredientsTotal(rows: IngredientRow[]): { total: number; n: number } | null {
  const costs = rows.map(ingredientCost).filter((c): c is number => c !== null);
  return costs.length ? { total: costs.reduce((a, b) => a + b, 0), n: costs.length } : null;
}

/* ── 장비값 — 구입가를 쓸 햇수로 나눈 월 감가상각(2026-11-26) ────────────────── */

/** 장비 한 줄 — 구입가(만원) · 쓸 햇수(년) */
export interface EquipmentRow { name: string; price: string; years: string }
export const emptyEquipment = (): EquipmentRow => ({ name: "", price: "", years: "" });

/** 장비값 합(만원)과 월 감가상각(만원) = Σ 구입가 ÷ (햇수 × 12). 구입가 > 0 · 햇수 1~30 인 줄만 쓴다 — 쓸 줄이 없으면 null */
export function equipmentPlan(rows: EquipmentRow[]): { total: number; monthly: number; n: number } | null {
  const used = rows.map((r) => ({ price: num(r.price), years: num(r.years) }))
    .filter((r) => Number.isFinite(r.price) && Number.isFinite(r.years) && r.price > 0 && r.years >= 1 && r.years <= 30);
  if (!used.length) return null;
  return { total: used.reduce((t, r) => t + r.price, 0), monthly: used.reduce((t, r) => t + r.price / (r.years * 12), 0), n: used.length };
}

/** 영업 시간 1시간에 팔아야 하는 개수(올림). 영업 시간이 0 초과 24 이하가 아니면 null */
export function perHour(dailySales: number, hours: number): number | null {
  if (!Number.isFinite(dailySales) || !Number.isFinite(hours) || dailySales < 0 || hours <= 0 || hours > 24) return null;
  return Math.ceil(dailySales / hours - 1e-9);
}

/* ── 업종 → 메뉴 기준값 업종 키(GET /ai/menu-benchmarks 의 categories[].key) ─────────── */

// 세부 업종을 골랐으면 그 키를 쓰고, 아니면 업종 입력 낱말로 맞춘다. 순서가 중요하다(「베이커리 카페」는 제과 · 「카페·디저트」는 커피).
// 못 맞추면 null — 화면이 업종을 고르게 한다(「음식점」처럼 넓은 말은 일부러 맞추지 않는다).
const MENU_WORDS: [string, RegExp][] = [
  ["cafe_bakery", /베이커리|제과|빵|케이크|도넛/],
  ["cafe_coffee", /카페|커피|음료|디저트/],
  ["restaurant_chicken", /치킨|닭강정/],
  ["restaurant_fastfood", /피자|햄버거|버거|샌드위치|패스트푸드|토스트/],
  ["restaurant_snack", /분식|김밥|떡볶이/],
  ["restaurant_chinese", /중식|중국|짜장|짬뽕|마라/],
  ["bar_beer", /호프|맥주|비어|펍/],
  ["bar_cooking", /주점|술집|포차|이자카야|와인/],
  ["restaurant_japanese", /일식|초밥|스시|라멘|돈까스|돈가스|우동/],
  ["restaurant_western", /양식|파스타|스테이크|브런치|이탈리안/],
  ["restaurant_korean", /한식|백반|국밥|찌개|고기|삼겹|갈비|냉면|칼국수|한정식|해장국|족발|보쌈/],
];

export function menuCategoryOf(industry: string | null | undefined, detailKey: string | null | undefined, known: string[]): string | null {
  if (detailKey && known.includes(detailKey)) return detailKey;
  const text = (industry ?? "").trim();
  if (!text) return null;
  const hit = MENU_WORDS.find(([key, re]) => known.includes(key) && re.test(text));
  return hit ? hit[0] : null;
}
