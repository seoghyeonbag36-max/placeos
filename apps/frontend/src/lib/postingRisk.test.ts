import { describe, expect, it } from "vitest";
import type { SimulateResult, TierScenario } from "@/lib/api";
import { postingRisks, riskVerdict } from "./postingRisk";

const tier = (key: string, over: Partial<TierScenario> = {}): TierScenario => ({
  tier: key, name: key, sub: "", invest_mn: 80, month_cost: 1200, month_rev: 1800, month_net: 600, roi_months: 14,
  recommended: false, viable: true, basis: "kosis-opex+measured-revenue", ...over,
});
const result = (over: Partial<SimulateResult> = {}): SimulateResult => ({
  district_id: "d", unit_id: "u", industry_type: "카페",
  scenarios: { premium: tier("premium"), value: tier("value"), factory: tier("factory") },
  source: "fallback-3tier", source_note: null,
  inputs_source: { area: "user_input", rent: "contract", prem: "contract", foot: "flpop", floor: "flr_ouln" },
  inputs_quarter: "2026Q2", unviable_note: null, ...over,
});
const titles = (r: SimulateResult, o = {}) => postingRisks(r, { industry: "카페", ...o }).map((i) => `${i.level}:${i.title}`);

describe("위험 확인 — 계산 결과와 입력 출처로만 가른다", () => {
  it("결과가 없으면 아무것도 말하지 않는다", () => {
    expect(postingRisks(null)).toEqual([]);
  });

  it("입력을 모두 넣고 회수되는 자리는 탈락 · 확인 필요가 없다(투자비 계수 참고만)", () => {
    const items = postingRisks(result(), { industry: "카페" });
    expect(riskVerdict(items)).toMatchObject({ fails: 0, checks: 0, tone: "ok", text: "걸리는 것 없음" });
    expect(items.map((i) => i.title)).toEqual(["투자비는 업종 평균 계수다"]);
  });

  it("권리금 전제 · 시세 월세 · 대장 면적 · 1층 가정은 확인 필요다", () => {
    const r = result({ inputs_source: { area: "gold-ledger", rent: "rone", prem: "absent", foot: "none", floor: "assumed_1f" } });
    const t = titles(r);
    expect(t).toContain("check:권리금을 넣지 않았다 — 0원으로 계산");
    expect(t).toContain("check:월세는 시세 기반 추정이다");
    expect(t).toContain("check:면적은 건축물대장 기준이다");
    expect(t).toContain("check:층은 1층으로 가정했다");
    expect(t).toContain("info:유동인구 자료가 없다");
    expect(riskVerdict(postingRisks(r, { industry: "카페" })).text).toBe("탈락 사유 없음 · 확인 필요 4건");
  });

  it("고른 전략이 회수 불가면 탈락, 고르지 않은 전략은 참고다", () => {
    const r = result({ scenarios: { premium: tier("premium", { month_net: -50, viable: false }), value: tier("value"), factory: tier("factory") } });
    expect(titles(r)).toContain("info:고급화 월 순익 -50만원 — 회수 불가");
    expect(titles(r, { strategy: "premium" })).toContain("fail:고급화 월 순익 -50만원 — 회수 불가");
  });

  it("계산한 가격대가 모두 회수 불가면 탈락이고, 자료 부족 가격대는 참고로만 센다", () => {
    const r = result({
      unviable_note: "세 전략 모두 회수 불가",
      scenarios: {
        premium: tier("premium", { available: false, unavailable_reason: "표본 부족", invest_mn: null, month_net: null, roi_months: null, viable: false }),
        value: tier("value", { month_net: -10, viable: false }), factory: tier("factory", { month_net: 0, viable: false }),
      },
    });
    const items = postingRisks(r, { industry: "카페" });
    expect(items.find((i) => i.level === "fail")).toMatchObject({ title: "계산한 가격대가 모두 회수 불가", detail: "세 전략 모두 회수 불가" });
    expect(items.find((i) => i.title.startsWith("고급화 자료 부족"))?.level).toBe("info");
    expect(riskVerdict(items).tone).toBe("fail");
  });

  it("회수 1개월 미만은 투자비 계수 탓일 수 있어 확인 필요다(2026-10-28 점검)", () => {
    const r = result({ scenarios: { premium: tier("premium"), value: tier("value", { roi_months: 0.8 }), factory: tier("factory", { roi_months: 0.6 }) } });
    expect(titles(r)).toContain("check:회수 1개월 미만 — 가성비 · 기능중심");
  });

  it("업종을 비우면 자리 기본 업종으로 계산했다고 알린다", () => {
    expect(titles(result(), { industry: "" })).toContain("info:업종을 비워 자리 기본 업종으로 계산했다");
  });
});
