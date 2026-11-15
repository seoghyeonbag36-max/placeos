/** 입점 점검 카드 — 다섯 갈래 이름 · 열린 항목 · 출처 · 단정 금지(허가됨·입점 가능) · 자료 실패 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { UseCheck } from "@/lib/api";
import { installFetchStub } from "@/test/fetchStub";
import { UseCheckCard } from "./UseCheckCard";
import { USE_CHECK_LABEL } from "./useCheckLabels";

const body = (over: Partial<UseCheck> = {}): UseCheck => ({
  pnu: "1144012400105710017", industry: "restaurant", industry_label: "음식점", act: "일반음식점",
  regulation_status: "use_change_needed", headline: "대장상 용도 변경 필요 — 지금 대장 용도로는 이 업종의 건축법 분류와 다릅니다.",
  checks: [
    { item: "필지 용도지역", status: "ok", reason: "제3종일반주거지역(포함)", source: "V-World", source_date: "2026-11-06", estimated: false },
    { item: "대장 층 용도", status: "blocked", reason: "대장 용도 「소매점」(제1종 근린생활시설) — 용도변경이 필요합니다.", source: "건축물대장", source_date: "실시간 조회 2026-11-15", estimated: false },
  ],
  note: "허가 판정이 아닙니다.", sources: [{ name: "토지이음 토지이용계획 열람", url: "https://www.eum.go.kr/web/ar/lu/luLandDet.jsp" }],
  permission: null, ledger_live_status: "ok", ...over,
});

describe("UseCheckCard", () => {
  it("판정 이름 · 열린 항목 · 출처를 보이고, 허가를 단정하지 않는다", async () => {
    const api = installFetchStub([{ match: /\/buildings\/1144012400105710017-1\/use-check\?/, body: body() }]);
    render(<UseCheckCard buildingId="1144012400105710017-1" districtId="hongdae" floor={1} areaM2={282} purps="소매점" industryKey="restaurant" />);
    expect(await screen.findByText("대장상 용도 변경 필요")).toBeTruthy();
    expect(screen.getAllByText(/소매점/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "토지이음 토지이용계획 열람" })).toBeTruthy();
    expect(screen.getByText(/허가 판정이 아니에요/)).toBeTruthy();
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/허가됨|입점 가능/);
    const url = api.calls.find((c) => c.url.includes("/use-check"))!.url;
    expect(url).toContain("district=hongdae");
    expect(url).toContain("floor=1");
    expect(url).toContain("industry=restaurant");
    expect(url).toContain("area_m2=282");
    expect(url).toContain(`purps=${encodeURIComponent("소매점")}`);
  });

  it("다섯 갈래 이름은 단정하지 않는다", () => {
    for (const label of Object.values(USE_CHECK_LABEL)) expect(label).not.toMatch(/허가됨|입점 가능/);
  });

  it("자료를 못 받으면 지어내지 않고 다시 시도를 준다", async () => {
    installFetchStub([]);
    render(<UseCheckCard buildingId="B9" districtId="hongdae" floor={2} areaM2={null} purps={null} industryKey="cafe" />);
    expect(await screen.findByText(/입점 점검 자료를 불러오지 못했어요/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeTruthy();
  });
});
