import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import PpppReport from "./PpppReport";

it("선택 자리와 계산 출처를 보고서에 담고 없는 성과를 만들지 않는다", async () => {
  render(<PpppReport handoff={{ districtId: "test", districtName: "테스트 상권", unitId: "test",
    unitName: "선택 건물", address: "테스트로 10", area: 30, floor: "1F", rent: 200,
    lat: 37, lng: 127, industry: "한식", strategy: null, inputsSource: { area: "seed", rent: "rone" } }} />);
  fireEvent.click(screen.getByRole("button", { name: "PPPP 결과 보고서 만들기" }));
  expect(screen.getByRole("article", { name: "PPPP 보고서 미리보기" }).textContent).toContain("테스트로 10");
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
