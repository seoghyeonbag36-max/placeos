/** 옛 거점 보드(#board) 카드의 공실률 — 색 띠가 아니라 점 + 숫자 (2026-11-25).
 *
 * 왼쪽 4px 색 띠는 값을 색으로만 말했다(색을 못 보는 사람·흑백 인쇄에선 읽을 수 없고, 숫자는 어디에도 없었다).
 * 여기서 못 박는 것:
 *   1. 실측이 있으면 「공실률 N.N%」 숫자와 색 점을 함께 그린다 — 카드에 색 띠(borderLeftColor)는 없다
 *   2. 실측이 없으면 0% 가 아니라 「공실률 실측 없음」이고 점도 그리지 않는다(없는 값을 색으로 칠하지 않는다)
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import PageDashboard from "@/pages/PageDashboard";
import { district } from "@/test/fixtures";
import { installFetchStub } from "@/test/fetchStub";

vi.mock("@/lib/naverMap", () => ({
  loadNaverMaps: () => Promise.reject(new Error("지도 SDK 없음(테스트)")),
  describeNaverMapError: (e: unknown) => String(e),
}));

function cardOf(hub: string): HTMLElement {
  const card = screen.getAllByRole("button").find((b) => b.className.includes("dcard") && b.textContent?.includes(hub));
  if (!card) throw new Error(`${hub} 카드를 못 찾았다`);
  return card;
}

describe("PageDashboard 카드 — 공실률은 점 + 숫자 (2026-11-25)", () => {
  it("실측이 있으면 숫자와 색 점을 함께 그리고, 카드에 색 띠는 없다", { timeout: 20000 }, async () => {
    installFetchStub([{ match: /\/commercial-districts$/, body: [district("garak", { vacancy_rate: 18.46 })] }]);
    render(<PageDashboard />);
    expect(await screen.findByText("공실률 18.5%")).toBeTruthy();
    const card = cardOf("garak");
    expect(card.style.borderLeftColor).toBe("");
    const dot = card.querySelector<HTMLElement>(".vdot");
    expect(dot).toBeTruthy();
    expect(dot!.style.background).not.toBe("");
    expect(dot!.getAttribute("aria-hidden")).toBe("true");
  });

  it("실측이 없으면 0% 가 아니라 「실측 없음」이고 점도 없다", { timeout: 20000 }, async () => {
    installFetchStub([{ match: /\/commercial-districts$/, body: [district("garak", { vacancy_rate: null })] }]);
    render(<PageDashboard />);
    const absent = await screen.findByText("공실률 실측 없음");
    expect(absent.className).toContain("value-absent");
    expect(cardOf("garak").querySelector(".vdot")).toBeNull();
    expect(document.body.textContent).not.toMatch(/공실률 0(\.0)?%/);
  });
});
