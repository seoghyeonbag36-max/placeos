import { describe, expect, it } from "vitest";
import type { IndustryEconomics } from "@/lib/api";
import { breakEvenDaily } from "./breakEven";

const econ = (assumptions: Record<string, number>, bev: number | null, status: "calculated" | "needs_inputs" = "calculated") =>
  ({ detail_key: "x", label: "x", status, required_inputs: [], input_fields: [], assumptions, provenance: {},
     source: "user_input_scenario", note: "", monthly_revenue: null, monthly_cost: null, monthly_surplus: null,
     break_even_revenue: bev, payback_months: null }) as IndustryEconomics;

describe("breakEvenDaily — 목표선은 Posting 손익분기에서만", () => {
  it("판매 업종은 반품률을 빼고 하루 구매 건수로 올림한다", () => {
    const r = breakEvenDaily(econ({ transactions: 100, days: 25, price: 1, return_rate: 0.2, rent: 300, fixed_cost: 200,
      variable_cost_rate: 0.4, investment: 5000 }, 900));
    expect(r?.count).toBe(45);                // 900 ÷ (1 × 25 × 0.8) = 45
    expect(r?.unit).toBe("구매");
    expect(r?.basis).toContain("반품률");
  });

  it("좌석·예약 업종은 단가 × 영업일로 나눈다", () => {
    const r = breakEvenDaily(econ({ capacity: 20, cycles: 3, utilization: 0.5, days: 26, price: 0.9 }, 3314));
    expect(r?.count).toBe(Math.ceil(3314 / (0.9 * 26)));
    expect(r?.unit).toBe("유료 이용");
  });

  it("객실 업종은 판매일로 나눈다", () => {
    expect(breakEvenDaily(econ({ capacity: 12, utilization: 0.6, days: 30, price: 10 }, 1500))).toEqual(
      expect.objectContaining({ count: 5, unit: "판매 객실" }));   // 1500 ÷ (10 × 30) = 5
  });

  it("월 이용료 업종·계산 전·손익분기 없음은 목표선을 만들지 않는다", () => {
    expect(breakEvenDaily(econ({ capacity: 30, utilization: 0.8, price: 25 }, 1000))).toBeNull();   // 수강·회원 — 영업일 없음
    expect(breakEvenDaily(econ({ transactions: 10, days: 25, price: 1 }, 900, "needs_inputs"))).toBeNull();
    expect(breakEvenDaily(econ({ transactions: 10, days: 25, price: 1 }, null))).toBeNull();
    expect(breakEvenDaily(null)).toBeNull();
  });
});
