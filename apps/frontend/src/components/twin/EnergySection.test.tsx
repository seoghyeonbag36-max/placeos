/** 월별 가스 사용량 — 값 있는 달만 막대 · 빠진 달은 0 이 아니라 「자료 없음」 · 활용신청 전이면 사유와 신청 링크. */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import EnergySection from "@/components/twin/EnergySection";
import { installFetchStub } from "@/test/fetchStub";
import { monthSpan } from "@/lib/twinEnergy";

const BASE = { kind: "gas", source: "건물에너지", apply_url: "https://www.data.go.kr/data/15135963/openapi.do", unit: null, fields: ["useQty", "useYm"] };
afterEach(cleanup);

function mount(body: unknown) {
  const stub = installFetchStub([{ match: /\/api\/v1\/buildings\/b1\/energy\?kind=gas/, body }]);
  render(<EnergySection buildingId="b1" />);
  return stub;
}

describe("EnergySection", () => {
  it("값 있는 달만 막대로 · 빠진 달은 자료 없음 · 표로 보기", async () => {
    const stub = mount({ ...BASE, status: "ok", window: ["202601", "202604"], query: "monthly",
      months: [{ ym: "202601", qty: 1500, n: 1 }, { ym: "202602", qty: 0, n: 1 }, { ym: "202604", qty: 300.5, n: 2 }] });
    expect((await screen.findAllByText("2026.04")).length).toBeGreaterThan(0);
    expect(stub.urls()).toEqual(["GET /api/v1/buildings/b1/energy?kind=gas"]);
    expect(document.querySelectorAll(".twin3d-energy-bar").length).toBe(2);       // 0 인 달은 막대 없음(높이 0) · 빠진 달도 없음
    expect(document.querySelectorAll(".twin3d-energy-gap").length).toBe(1);       // 2026.03 — 기록 없음 눈금
    expect(screen.getByRole("img", { name: /월별 가스 사용량 막대/ })).toBeTruthy();
    expect(screen.getAllByText("자료 없음").length).toBe(1);                      // 표의 2026.03
    expect(screen.getByText(/단위는 원천 명세 확인 필요/)).toBeTruthy();
    expect(screen.getByText(/공실 판정에는 쓰지 않았습니다/)).toBeTruthy();
    fireEvent.mouseEnter(document.querySelectorAll(".twin3d-energy-chart rect")[2]);
    expect(document.querySelector(".twin3d-energy [aria-live]")?.textContent).toBe("2026.03 · 자료 없음");
  });

  it("활용신청 전(거절)이면 사유와 신청 링크", async () => {
    mount({ ...BASE, status: "refused", error: "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", months: [], window: null });
    const link = await screen.findByRole("link", { name: /건물에너지정보 서비스 활용신청/ });
    expect(link.getAttribute("href")).toBe("https://www.data.go.kr/data/15135963/openapi.do");
    expect(screen.getByText(/SERVICE_KEY_IS_NOT_REGISTERED_ERROR/)).toBeTruthy();
  });

  it("기록이 하나도 없으면 「안 썼다」가 아니라 자료 없음", async () => {
    mount({ ...BASE, status: "ok", months: [], window: ["202505", "202610"] });
    expect(await screen.findByText(/기록이 없다는 것이 「가스를 안 썼다」는 뜻은 아닙니다/)).toBeTruthy();
  });

  it("monthSpan — 기간의 모든 달 · 해 넘김", () => {
    expect(monthSpan(["202511", "202602"])).toEqual(["202511", "202512", "202601", "202602"]);
    expect(monthSpan(["202602", "202511"])).toEqual(["202511", "202512", "202601", "202602"]);
  });
});
