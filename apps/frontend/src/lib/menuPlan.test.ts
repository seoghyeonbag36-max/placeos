import { describe, expect, it } from "vitest";
import { dailyFromRevenue, menuBep, menuMix } from "./menuPlan";

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
});
