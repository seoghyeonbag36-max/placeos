import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import PpppReport from "./PpppReport";

it("선택 자리와 계산 출처를 보고서에 담고 없는 성과를 만들지 않는다", async () => {
  render(<PpppReport handoff={{ districtId: "test", districtName: "테스트 상권", unitId: "test",
    unitName: "선택 건물", address: "테스트로 10", area: 30, floor: "1F", rent: 200,
    lat: 37, lng: 127, industry: "한식", strategy: null, inputsSource: { area: "seed", rent: "rone" } }} />);
  fireEvent.click(screen.getByRole("button", { name: "상권 분석 보고서 만들기" }));
  expect(screen.getByRole("article", { name: "상권 분석 보고서 미리보기" }).textContent).toContain("테스트로 10");
  expect(screen.getByText("seed")).toBeTruthy();
  expect(screen.getAllByText(/자료 미입력 · 판단 보류/).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "인쇄·PDF 저장" })).toBeTruthy();
  const printButton = screen.getByRole("button", { name: "인쇄·PDF 저장" }) as HTMLButtonElement;
  await waitFor(() => expect(printButton.disabled).toBe(false));
  const write = vi.fn(); const print = vi.fn();
  const popup = vi.spyOn(window, "open").mockReturnValue({ document: { write, close: vi.fn() }, focus: vi.fn(), print } as unknown as Window);
  fireEvent.click(printButton);
  expect(write.mock.calls[0][0]).toContain("<!doctype html>");
  expect(write.mock.calls[0][0]).toContain("테스트로 10");
  expect(print).toHaveBeenCalledOnce();
  popup.mockRestore();
});

it("(2026-11-07 Program 리뉴얼) 네트워킹 메모와 담은 지원 공고를 사용자 입력·원문 확인 전제로 싣는다", () => {
  localStorage.setItem("placeos.program.network.test", JSON.stringify({ checked: ["상인회나 상점가 모임이 있나요?"], memo: "월 회비 있음" }));
  localStorage.setItem("placeos.program.support.test", JSON.stringify([
    { id: "ks-1", title: "예비창업 사업화 지원", source_label: "K-Startup", org: "창업진흥원", end: "2026-11-30", url: "https://www.k-startup.go.kr/x" },
  ]));
  try {
    render(<PpppReport districtId="test" />);
    fireEvent.click(screen.getByRole("button", { name: "상권 분석 보고서 만들기" }));
    const article = screen.getByRole("article", { name: "상권 분석 보고서 미리보기" });
    expect(article.textContent).toContain("확인함 · 상인회나 상점가 모임이 있나요?");
    expect(article.textContent).toContain("월 회비 있음");
    expect(article.textContent).toContain("들은 말은 확인된 사실이 아닙니다");
    expect(article.textContent).toContain("예비창업 사업화 지원 · K-Startup · 창업진흥원");
    expect(article.textContent).toContain("자격·선정·금액은 원문에서 확인합니다");
  } finally {
    localStorage.clear();
  }
});
