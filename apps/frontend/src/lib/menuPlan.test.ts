import { describe, expect, it } from "vitest";
import { dailyFromRevenue, equipmentPlan, ingredientCost, ingredientsTotal, menuBep, menuCategoryOf, menuMix, menuRowsFromBenchmark, mergeIntoBlanks, perHour } from "./menuPlan";

const row = (price: string, cost: string, share = "") => ({ name: "", price, cost, share });

describe("메뉴 설정 — 객단가 · 원가율 · 하루 손익분기 판매", () => {
  it("판매 비중이 모두 있으면 가중 평균, 하나라도 비면 단순 평균이다", () => {
    expect(menuMix([row("5000", "1500", "75"), row("9000", "3000", "25")])).toMatchObject({ n: 2, avgPrice: 6000, avgCost: 1875, weighted: true });
    expect(menuMix([row("5000", "1500", "75"), row("9000", "3000")])).toMatchObject({ avgPrice: 7000, avgCost: 2250, weighted: false });
  });

  it("판매가가 없거나 원가가 판매가 이상인 줄은 쓰지 않는다 — 쓸 줄이 없으면 null", () => {
    expect(menuMix([row("", ""), row("3000", "3000"), row("0", "0")])).toBeNull();
    expect(menuMix([row("4000", "1000"), row("3000", "3500")])).toMatchObject({ n: 1, avgPrice: 4000, costRate: 0.25 });
  });

  it("BEP 월매출 = (임대료 + 기타 고정비) ÷ (1 − 원가율), 하루 판매는 올림이다", () => {
    const r = menuBep({ rent: 300, otherFixed: 400, avgPrice: 5000, costRate: 0.3, days: 25 })!;
    expect(r.breakEvenRevenue).toBeCloseTo(1000);
    expect(r.dailySales).toBe(80);
    expect(menuBep({ rent: 300, otherFixed: 0, avgPrice: 5000, costRate: 1, days: 25 })).toBeNull();
    expect(menuBep({ rent: 300, otherFixed: 0, avgPrice: 5000, costRate: 0.3, days: 0 })).toBeNull();
  });

  it("추정 월매출을 객단가로 나눈 하루 판매 개수", () => {
    expect(dailyFromRevenue(1000, 5000, 25)).toBe(80);
  });

  it("가맹점 로열티는 분모에서 뺀다 — BEP = (임대료 + 고정비) ÷ (1 − 원가율 − 로열티율), 합이 1 이상이면 계산하지 않는다", () => {
    const r = menuBep({ rent: 300, otherFixed: 300, avgPrice: 5000, costRate: 0.3, days: 25, royaltyRate: 0.1 })!;
    expect(r.breakEvenRevenue).toBeCloseTo(1000);
    expect(r.dailySales).toBe(80);
    expect(menuBep({ rent: 300, otherFixed: 0, avgPrice: 5000, costRate: 0.6, days: 25, royaltyRate: 0.4 })).toBeNull();
    expect(menuBep({ rent: 300, otherFixed: 0, avgPrice: 5000, costRate: 0.3, days: 25, royaltyRate: -0.1 })).toBeNull();
  });
});

describe("메뉴 설정 — 재료값 · 장비값 · 영업 시간 (2026-11-26)", () => {
  const ing = (price: string, pack: string, use: string) => ({ name: "", price, pack, use });
  it("재료 1개 값 = 산 값 × 쓰는 양 ÷ 산 양 · 비었거나 산 양이 0이면 그 줄은 빼고 더한다", () => {
    expect(ingredientCost(ing("25000", "1000", "20"))).toBe(500);
    expect(ingredientCost(ing("25000", "0", "20"))).toBeNull();
    expect(ingredientCost(ing("", "1000", "20"))).toBeNull();
    expect(ingredientsTotal([ing("25000", "1000", "20"), ing("12000", "100", "1"), ing("", "", "")])).toEqual({ total: 620, n: 2 });
    expect(ingredientsTotal([ing("", "", "")])).toBeNull();
  });

  it("장비값 월 감가상각 = 구입가 ÷ (햇수 × 12) — 햇수 1~30 · 구입가 > 0 인 줄만", () => {
    const e = (price: string, years: string) => ({ name: "", price, years });
    expect(equipmentPlan([e("1200", "5"), e("600", "5"), e("100", "0"), e("", "")])).toEqual({ total: 1800, monthly: 30, n: 2 });
    expect(equipmentPlan([e("100", "31")])).toBeNull();
  });

  it("영업 시간 1시간에 팔 개수는 올림 · 0 시간이나 24 시간 초과는 계산하지 않는다", () => {
    expect(perHour(80, 10)).toBe(8);
    expect(perHour(81, 10)).toBe(9);
    expect(perHour(80, 0)).toBeNull();
    expect(perHour(80, 25)).toBeNull();
  });

  it("업종 → 기준값 업종: 세부 업종이 먼저 · 낱말은 순서대로(베이커리 카페는 제과) · 넓은 말(음식점)은 맞추지 않는다", () => {
    const known = ["restaurant_korean", "cafe_coffee", "cafe_bakery", "bar_beer", "bar_cooking", "restaurant_chicken"];
    expect(menuCategoryOf("카페", "bar_beer", known)).toBe("bar_beer");
    expect(menuCategoryOf("카페·디저트", "", known)).toBe("cafe_coffee");
    expect(menuCategoryOf("베이커리 카페", null, known)).toBe("cafe_bakery");
    expect(menuCategoryOf("수제 맥주 펍", null, known)).toBe("bar_beer");
    expect(menuCategoryOf("돼지고기 구이", null, known)).toBe("restaurant_korean");
    expect(menuCategoryOf("음식점", null, known)).toBeNull();
    expect(menuCategoryOf("치킨", null, ["cafe_coffee"])).toBeNull();          // 기준값에 없는 업종이면 고르지 않는다
    expect(menuCategoryOf("", "", known)).toBeNull();
  });
});

describe("메뉴 설정 — 업종 평균에서 채우기 (2026-11-26)", () => {
  it("대표메뉴 → 메뉴 줄: 원가 = 판매가 × 식재료비 비율, 비중 = 응답 수 비중(합 100 · 최대 나머지)", () => {
    const rows = menuRowsFromBenchmark([{ name: "커피", n: 530, price: 4118 }, { name: "음료", n: 73, price: 5017 },
      { name: "차류", n: 52, price: 4868 }, { name: "빵", n: 0, price: 6000 }], 39.1, 4);
    expect(rows.map((r) => r.name)).toEqual(["커피", "음료", "차류"]);                 // 응답 0 인 메뉴는 뺀다
    expect(rows[0]).toEqual({ name: "커피", price: "4118", cost: "1610", share: "81" });
    expect(rows.reduce((t, r) => t + Number(r.share), 0)).toBe(100);
    expect(menuRowsFromBenchmark([{ name: "a", n: 1, price: 1000 }], 100, 4)).toEqual([]);   // 비율이 범위 밖이면 만들지 않는다
    expect(menuRowsFromBenchmark([], 40, 4)).toEqual([]);
  });

  it("빈 줄에 먼저 채우고 모자라면 붙인다 · 이미 적은 줄과 같은 이름은 건드리지 않는다 · 최대 줄 수", () => {
    type R = { name: string };
    const blank = (r: R) => !r.name;
    const key = (r: R) => r.name;
    expect(mergeIntoBlanks<R>([{ name: "커피" }, { name: "" }], [{ name: "커피" }, { name: "음료" }, { name: "빵" }], blank, key, 8))
      .toEqual([{ name: "커피" }, { name: "음료" }, { name: "빵" }]);
    expect(mergeIntoBlanks<R>([{ name: "a" }], [{ name: "b" }, { name: "c" }], blank, key, 2)).toEqual([{ name: "a" }, { name: "b" }]);
  });
});
