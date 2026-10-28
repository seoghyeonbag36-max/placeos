/** 옛 거점 보드(#board)의 3-Tier — 실측 재료가 없는 전략은 「자료 부족」이다 (2026-10-28 사용자 결정 (b)).
 *
 * 서버는 재료가 없는 tier 를 `available: false` · 숫자 null 로 내려보낸다(가락·불광의 고급화 · 고양·파주의 세 tier).
 * 여기서 못 박는 것:
 *   1. 자료 부족 전략에는 숫자를 그리지 않고(「null백만」·NaN 금지) 「자료 부족」 + 사유를 싣는다
 *   2. 회수 불가 문구는 계산한 전략으로만 판정한다 — 「세 전략 모두」가 아니라 「계산한 전략(…) 모두」
 *   3. 추천이 하나도 없는 거점 카드는 「고급화 0 · 가성비 0 · 공장제 0」 대신 「추천 없음」이다
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import PageDashboard from "@/pages/PageDashboard";
import type { TierScenario } from "@/lib/api";
import { district, postings } from "@/test/fixtures";
import { installFetchStub } from "@/test/fetchStub";

vi.mock("@/lib/naverMap", () => ({
  loadNaverMaps: () => Promise.reject(new Error("지도 SDK 없음(테스트)")),
  describeNaverMapError: (e: unknown) => String(e),
}));

const HUB = "garak";
const DETAIL = {
  id: HUB, name: HUB, sub: "테스트 상권", gu: "송파구", type: "생활",
  center: [37.49, 127.11], zoom: 16, poi: [], zones: [], units: [], events: [], insta: [],
};
const WHY = "이 상권에는 이 가격대 업종(일식·양식·중식)의 매출 표본이 모자라 계산하지 않았어요.";
const NONE: Partial<TierScenario> = {
  available: false, unavailable_reason: WHY, invest_mn: null, month_cost: null, month_rev: null,
  month_net: null, roi_months: null, viable: false, recommended: false, basis: null,
};

async function openHub(scenarios: (s: Record<string, TierScenario>) => Record<string, TierScenario>,
  tierMix = { premium: 0, value: 0, factory: 2 }) {
  const units = postings(HUB, 1).map((u) => ({ ...u, scenarios: scenarios(u.scenarios) }));
  installFetchStub([
    { match: /\/commercial-districts$/, body: [district(HUB, { tier_mix: tierMix })] },
    { match: new RegExp(`/commercial-districts/${HUB}$`), body: DETAIL },
    { match: new RegExp(`/commercial-districts/${HUB}/postings$`), body: units },
    { match: new RegExp(`/marketing/${HUB}$`), body: { district_id: HUB, events: [], events_source: "seed", online_contents: [], source: "seed", ha_findings: [] } },
  ]);
  render(<PageDashboard />);
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(HUB) }));
}

describe("PageDashboard — 자료 부족 전략 (2026-10-28 (b))", () => {
  it("자료 부족 전략은 숫자 없이 「자료 부족」과 사유를 싣고, 계산한 전략은 그대로 그린다", { timeout: 20000 }, async () => {
    await openHub((s) => ({ ...s, premium: { ...s.premium, ...NONE } }));
    expect(await screen.findByText(WHY)).toBeTruthy();
    expect(screen.getAllByText("자료 부족").length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/null백만|NaN/);
    expect(screen.getAllByText("14개월").length).toBe(2);       // 계산한 가성비·공장제만 회수기간이 있다
  });

  it("계산한 전략이 모두 회수 불가면 「계산한 전략(…) 모두」라고 쓴다 — 자료 부족 전략은 판정에서 뺀다", { timeout: 20000 }, async () => {
    await openHub((s) => ({
      premium: { ...s.premium, ...NONE },
      value: { ...s.value, viable: false, month_net: -50, roi_months: 99, recommended: false },
      factory: { ...s.factory, viable: false, month_net: -10, roi_months: 99, recommended: false },
    }));
    expect(await screen.findByText(/계산한 전략\(value·factory\) 모두/)).toBeTruthy();
    expect(screen.queryByText(/세 전략 모두/)).toBeNull();
  });

  it("추천이 하나도 없는 거점 카드는 0 셋 대신 「추천 없음」이다", { timeout: 20000 }, async () => {
    installFetchStub([
      { match: /\/commercial-districts$/, body: [district(HUB, { tier_mix: { premium: 0, value: 0, factory: 0 } })] },
    ]);
    render(<PageDashboard />);
    expect(await screen.findByText("추천 없음")).toBeTruthy();
  });
});
