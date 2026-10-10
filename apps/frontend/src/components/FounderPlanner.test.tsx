import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FounderPlanner from "./FounderPlanner";
import { assessFounderCosts } from "@/lib/api";

vi.mock("@/lib/api", () => ({ assessFounderCosts: vi.fn() }));
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn();
  HTMLDialogElement.prototype.close = vi.fn();
  vi.mocked(assessFounderCosts).mockReset();
});

describe("창업 후보 준비", () => {
  it("선택 없이는 후보를 만들지 않는다", () => {
    render(<FounderPlanner />);
    fireEvent.click(screen.getByText("입점 준비 · 0/3"));
    expect((screen.getByText("지도에서 건물을 선택해 입점 검토로 이동하세요") as HTMLButtonElement).disabled).toBe(true);
  });
  it("미입력 비용을 null로 보내고 결과와 문의 초안을 표시한다", async () => {
    vi.mocked(assessFounderCosts).mockResolvedValue({ source: "user_input", currency: "KRW", known_initial: 0,
      known_monthly: 100, required_cash: null, budget_remaining: null, missing_fields: ["deposit"], status: "incomplete", note: "직접 입력" });
    render(<FounderPlanner selection={{ districtId: "garosugil", buildingId: "building-1", buildingName: "후보 건물" }} />);
    fireEvent.click(screen.getByText("입점 준비 · 0/3"));
    fireEvent.click(screen.getByText("후보 건물 후보 담기"));
    fireEvent.change(screen.getByLabelText("월세 (원)"), { target: { value: "100" } });
    fireEvent.click(screen.getByText("비용 검토"));
    await waitFor(() => expect(assessFounderCosts).toHaveBeenCalled());
    expect(vi.mocked(assessFounderCosts).mock.calls[0][0].deposit).toBeNull();
    expect(vi.mocked(assessFounderCosts).mock.calls[0][0].rent).toBe(100);
    expect(await screen.findByText(/총 필요자금은 계산하지 않았습니다/)).toBeTruthy();
    expect((screen.getByLabelText("문의 초안") as HTMLTextAreaElement).value).toContain("보증금: 미확인");
    fireEvent.change(screen.getByLabelText("월세 (원)"), { target: { value: "200" } });
    expect(screen.queryByText(/총 필요자금은 계산하지 않았습니다/)).toBeNull();
  });
  it("같은 건물은 중복으로 담지 않는다", () => {
    render(<FounderPlanner selection={{ districtId: "garosugil", buildingId: "b1", buildingName: "건물" }} />);
    fireEvent.click(screen.getByText("입점 준비 · 0/3"));
    fireEvent.click(screen.getByText("건물 후보 담기"));
    fireEvent.click(screen.getByText("건물 후보 담기"));
    expect(screen.getByText("입점 준비 · 1/3")).toBeTruthy();
  });
});
